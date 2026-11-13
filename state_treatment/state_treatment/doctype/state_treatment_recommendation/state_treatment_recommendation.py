import hashlib
import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cint, flt, formatdate, getdate, now_datetime, nowdate

from state_treatment.patient_link import get_patient_national_id
from state_treatment.utils import get_protocol_item_price


APPROVED_STATUS = "Approved for Disbursement"
COMPLETED_STATUS = "Treatment Completed"


class StateTreatmentRecommendation(Document):
    def autoname(self):
        self.name = make_autoname(
            "STR-{0}-.#####".format(self.recommendation_year or nowdate()[:4])
        )

    def validate(self):
        self.fill_national_id()
        self.calculate_total()
        self.validate_treatment_doses()
        self.validate_procedure_done()
        self.sync_dose_schedule()
        self.complete_treatment_if_done()
        self.update_dose_summary()

    def fill_national_id(self):
        """Copy the patient's national ID when this is empty, or when the patient changes."""
        if not self.patient:
            return
        if self.national_id and not self.has_value_changed("patient"):
            return
        self.national_id = get_patient_national_id(self.patient)

    def validate_treatment_doses(self):
        previous_doc = self.get_doc_before_save()
        previous_rows = {
            row.name: row
            for row in (previous_doc.treatment_doses if previous_doc else [])
        }
        roles = set(frappe.get_roles())
        is_pharmacist = "Treatment Pharmacist" in roles
        is_system_manager = "System Manager" in roles

        if is_pharmacist and not is_system_manager:
            if not previous_doc:
                frappe.throw(_("Treatment Pharmacists can only update existing recommendations."))

            for field in self.meta.fields:
                if field.fieldname == "treatment_doses":
                    continue
                if field.fieldtype == "Table":
                    # Child rows are compared as plain data. Comparing the row
                    # objects directly would always differ.
                    changed = self._table_snapshot(self.get(field.fieldname)) != self._table_snapshot(
                        previous_doc.get(field.fieldname)
                    )
                else:
                    changed = self.get(field.fieldname) != previous_doc.get(field.fieldname)
                if changed:
                    frappe.throw(_("Treatment Pharmacists can only update dose dispensing."))

            current_rows = {row.name: row for row in self.treatment_doses}
            if set(current_rows) != set(previous_rows):
                frappe.throw(_("Treatment Pharmacists cannot add or remove dose schedule rows."))

            for row_name, row in current_rows.items():
                previous_row = previous_rows[row_name]
                for fieldname in (
                    "item", "medicine_name", "dose", "scheduled_date",
                    "protocol_item", "schedule_version", "regimen_signature",
                ):
                    if row.get(fieldname) != previous_row.get(fieldname):
                        frappe.throw(_("Treatment Pharmacists can only update dose dispensing."))
                if cint(previous_row.dispensed) and not cint(row.dispensed):
                    frappe.throw(_("A dispensed dose cannot be reverted."))

        for row in self.treatment_doses:
            previous_row = previous_rows.get(row.name)
            if not previous_row:
                if row.dispensed or row.dispensed_by or row.dispensed_on:
                    frappe.throw(_("New doses cannot be marked as dispensed before they are saved."))
                row.dispensed = 0
                continue

            if cint(row.dispensed) != cint(previous_row.dispensed):
                if not (is_pharmacist or is_system_manager):
                    frappe.throw(_("Only a Treatment Pharmacist can mark a dose as dispensed."))
                if row.dispensed:
                    row.dispensed_by = frappe.session.user
                    row.dispensed_on = now_datetime()
                else:
                    row.dispensed_by = None
                    row.dispensed_on = None
            else:
                row.dispensed_by = previous_row.dispensed_by
                row.dispensed_on = previous_row.dispensed_on

    def sync_dose_schedule(self):
        """Build the dose schedule from the medicine rows in Protocol Items.

        Draft: the schedule follows the current medicines. Undispensed doses of
        a changed or removed regimen are dropped; dispensed doses are kept.
        Approved: a changed regimen is appended as a new version, so history is
        never rewritten.
        """
        if self._is_pharmacist_only():
            return  # pharmacists record dispensing only and do not change the schedule

        approved = self.status in (APPROVED_STATUS, COMPLETED_STATUS)

        latest = {}
        for dose in self.treatment_doses:
            protocol_item = dose.get("protocol_item")
            if not protocol_item:
                continue
            version = cint(dose.get("schedule_version"))
            if version >= latest.get(protocol_item, {}).get("version", 0):
                latest[protocol_item] = {
                    "version": version,
                    "signature": dose.get("regimen_signature"),
                }

        wanted = {}
        for row in self.protocol_items:
            plan = self._medicine_plan(row)
            if not plan:
                continue
            if not plan["first_date"]:
                if approved:
                    frappe.throw(
                        _("Set the first dose date for medicine {0} before final approval.").format(
                            plan["medicine_name"]
                        )
                    )
                continue  # draft: the schedule waits for the first dose date
            wanted[row.name] = plan

        stale = {
            protocol_item for protocol_item, current in latest.items()
            if protocol_item not in wanted or wanted[protocol_item]["signature"] != current["signature"]
        }
        if stale and not approved:
            self.set("treatment_doses", [
                dose for dose in self.treatment_doses
                if not (dose.get("protocol_item") in stale and not cint(dose.dispensed))
            ])

        for protocol_item, plan in wanted.items():
            current = latest.get(protocol_item)
            if current and current["signature"] == plan["signature"]:
                continue

            version = (current["version"] if current else 0) + 1
            for dose_number in range(plan["dose_count"]):
                self.append(
                    "treatment_doses",
                    {
                        "item": plan["item"],
                        "medicine_name": plan["medicine_name"],
                        "dose": _("Dose {0} of {1}").format(dose_number + 1, plan["dose_count"]),
                        "scheduled_date": plan["first_date"] + timedelta(days=plan["interval"] * dose_number),
                        "dispensed": 0,
                        "protocol_item": protocol_item,
                        "schedule_version": version,
                        "regimen_signature": plan["signature"],
                    },
                )

    @staticmethod
    def _medicine_plan(row):
        """Schedule inputs for a medicine row in Protocol Items, or None for a procedure."""
        if not row.item:
            return None
        protocol = frappe.db.get_value(
            "Item",
            row.item,
            ["protocol_treatment_type", "medicine_name", "number_of_doses", "dose_interval_days"],
            as_dict=True,
        )
        if not protocol or protocol.protocol_treatment_type != "Medicine":
            return None

        dose_count = cint(protocol.number_of_doses)
        interval = flt(protocol.dose_interval_days)
        if dose_count <= 0 or interval < 0:
            frappe.throw(_("Medicine {0} has an invalid dose protocol.").format(row.item))

        medicine_name = protocol.medicine_name or row.item
        first_date = getdate(row.first_dose_date) if row.first_dose_date else None
        snapshot = {
            "protocol_item": row.name,
            "item": row.item,
            "medicine_name": medicine_name,
            "number_of_doses": dose_count,
            "dose_interval_days": interval,
            "first_dose_date": str(first_date) if first_date else None,
        }
        signature = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "item": row.item,
            "medicine_name": medicine_name,
            "dose_count": dose_count,
            "interval": interval,
            "first_date": first_date,
            "signature": signature,
        }

    @staticmethod
    def _is_pharmacist_only():
        roles = set(frappe.get_roles())
        return "Treatment Pharmacist" in roles and "System Manager" not in roles

    def update_dose_summary(self):
        if self.status not in (APPROVED_STATUS, COMPLETED_STATUS):
            self.dose_summary = ""
            return

        current_medicines = {}
        for row in self.protocol_items:
            if not row.item:
                continue
            protocol = frappe.db.get_value(
                "Item", row.item, ["protocol_treatment_type", "medicine_name"], as_dict=True
            )
            if protocol and protocol.protocol_treatment_type == "Medicine":
                current_medicines[row.name] = protocol.medicine_name or row.item

        latest_versions = {}
        for dose in self.treatment_doses:
            protocol_item = dose.get("protocol_item")
            if protocol_item in current_medicines:
                latest_versions[protocol_item] = max(
                    latest_versions.get(protocol_item, 0), cint(dose.get("schedule_version"))
                )

        summaries = []
        for protocol_item, medicine_name in current_medicines.items():
            version = latest_versions.get(protocol_item)
            if not version:
                continue
            rows = [
                dose for dose in self.treatment_doses
                if dose.get("protocol_item") == protocol_item
                and cint(dose.get("schedule_version")) == version
            ]
            dispensed = sum(cint(dose.dispensed) for dose in rows)
            summaries.append(
                _("{0}: dispensed {1} of {2}, remaining {3}").format(
                    medicine_name, dispensed, len(rows), len(rows) - dispensed
                )
            )
        for row in self.protocol_items:
            if row.item and row.treatment_type == "Procedure":
                if cint(row.procedure_done):
                    summaries.append(_("{0}: performed on {1}").format(
                        row.item_name or row.item, formatdate(row.procedure_done_on)))
                else:
                    summaries.append(_("{0}: not performed yet").format(row.item_name or row.item))
        self.dose_summary = "\n".join(summaries)

    def calculate_total(self):
        total = 0.0
        previous_doc = self.get_doc_before_save()
        previous_rows = {
            row.name: row for row in (previous_doc.protocol_items if previous_doc else [])
        }

        for row in self.protocol_items:
            if not row.item:
                continue

            if not self._has_protocol_catalog():
                frappe.throw(_("Import the authorized protocol catalog before adding treatment items."))

            item = frappe.db.get_value(
                "Item",
                row.item,
                [
                    "item_name", "official_protocol_code", "duration_days", "decision_sequence",
                    "protocol_treatment_type", "medicine_name", "number_of_doses",
                    "dose_interval_days",
                ],
                as_dict=True,
            )
            if not item or not item.official_protocol_code:
                frappe.throw(_("Item {0} is not part of the treatment protocol catalog.").format(row.item))

            previous_row = previous_rows.get(row.name)
            if previous_row and previous_row.item == row.item:
                rate = previous_row.rate
            else:
                rate = get_protocol_item_price(row.item)
                if not rate:
                    frappe.throw(_("No current price exists for protocol item {0} in the State-funded price list.").format(row.item))

            row.item_name = item.item_name
            row.official_protocol_code = item.official_protocol_code
            row.duration_days = item.duration_days or 0
            row.decision_sequence = item.decision_sequence
            row.treatment_type = item.protocol_treatment_type
            row.medicine_name = item.medicine_name
            row.number_of_doses = cint(item.number_of_doses)
            row.dose_interval_days = flt(item.dose_interval_days)
            row.rate = flt(rate)
            total += flt(row.rate)
        self.total_amount = total

    def validate_procedure_done(self):
        """A Medical Reviewer marks a procedure as done once; the date and user are recorded."""
        previous_doc = self.get_doc_before_save()
        previous_rows = {
            row.name: row for row in (previous_doc.protocol_items if previous_doc else [])
        }
        roles = set(frappe.get_roles())
        can_mark = bool({"Medical Reviewer", "System Manager"} & roles)

        for row in self.protocol_items:
            previous_row = previous_rows.get(row.name)
            done = cint(row.procedure_done)
            if not previous_row:
                if done:
                    frappe.throw(_("Procedures cannot be marked as done before they are saved."))
                continue

            if done == cint(previous_row.procedure_done):
                row.procedure_done_by = previous_row.procedure_done_by
                row.procedure_done_on = previous_row.procedure_done_on
                continue

            if row.treatment_type != "Procedure":
                frappe.throw(_("Only procedure items can be marked as done."))
            if not can_mark:
                frappe.throw(_("Only a Medical Reviewer can mark a procedure as done."))
            if not done:
                frappe.throw(_("A completed procedure cannot be reverted."))
            row.procedure_done_by = frappe.session.user
            row.procedure_done_on = now_datetime()

    def complete_treatment_if_done(self):
        """Move an approved request to Treatment Completed once every dose is dispensed and every procedure is done."""
        if self.status == APPROVED_STATUS and self._treatment_is_finished():
            self.status = COMPLETED_STATUS

    def _treatment_is_finished(self):
        active = [row for row in self.protocol_items if row.item]
        if not active:
            return False
        for row in active:
            if row.treatment_type == "Procedure":
                if not cint(row.procedure_done):
                    return False
            elif row.treatment_type == "Medicine":
                doses = self._latest_doses(row.name)
                if not doses or any(not cint(dose.dispensed) for dose in doses):
                    return False
            else:
                return False
        return True

    def _latest_doses(self, protocol_item):
        rows = [dose for dose in self.treatment_doses if dose.get("protocol_item") == protocol_item]
        if not rows:
            return []
        latest = max(cint(dose.get("schedule_version")) for dose in rows)
        return [dose for dose in rows if cint(dose.get("schedule_version")) == latest]

    @staticmethod
    def _table_snapshot(rows):
        """Child rows as plain dicts, without Frappe's bookkeeping columns."""
        skip = {"creation", "modified", "modified_by", "owner", "docstatus", "idx",
                "parent", "parentfield", "parenttype"}
        return [
            {k: v for k, v in row.as_dict().items() if k not in skip}
            for row in (rows or [])
        ]

    @staticmethod
    def _has_protocol_catalog():
        return frappe.get_meta("Item").has_field("official_protocol_code")

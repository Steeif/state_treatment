import hashlib
import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from state_treatment.utils import get_protocol_item_price


APPROVED_STATUS = "Approved for Disbursement"


class StateTreatmentRecommendation(Document):
    def autoname(self):
        self.name = make_autoname(
            "STR-{0}-.#####".format(self.recommendation_year or nowdate()[:4])
        )

    def validate(self):
        self.calculate_total()
        self.validate_treatment_doses()
        self.generate_approved_doses()
        self.update_dose_summary()

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
                if field.fieldname != "treatment_doses" and self.get(field.fieldname) != previous_doc.get(field.fieldname):
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

    def generate_approved_doses(self):
        """Append a dose schedule when an order is finally approved; never rewrite history."""
        if self.status != APPROVED_STATUS:
            return

        schedules = {}
        for dose in self.treatment_doses:
            protocol_item = dose.get("protocol_item")
            if not protocol_item:
                continue
            version = cint(dose.get("schedule_version"))
            schedule = schedules.setdefault(protocol_item, {"version": 0, "signature": None})
            if version >= schedule["version"]:
                schedule["version"] = version
                schedule["signature"] = dose.get("regimen_signature")

        for row in self.protocol_items:
            if not row.item:
                continue

            protocol = frappe.db.get_value(
                "Item",
                row.item,
                [
                    "protocol_treatment_type", "medicine_name", "number_of_doses",
                    "dose_interval_days",
                ],
                as_dict=True,
            )
            if not protocol or protocol.protocol_treatment_type != "Medicine":
                continue

            dose_count = cint(protocol.number_of_doses)
            interval = flt(protocol.dose_interval_days)
            if not row.first_dose_date:
                frappe.throw(
                    _("Set the first dose date for medicine {0} before final approval.").format(
                        protocol.medicine_name or row.item
                    )
                )
            if dose_count <= 0 or interval < 0:
                frappe.throw(_("Medicine {0} has an invalid dose protocol.").format(row.item))

            snapshot = {
                "protocol_item": row.name,
                "item": row.item,
                "medicine_name": protocol.medicine_name or row.item,
                "number_of_doses": dose_count,
                "dose_interval_days": interval,
                "first_dose_date": str(getdate(row.first_dose_date)),
            }
            signature = hashlib.sha256(
                json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            current_schedule = schedules.get(row.name)
            if current_schedule and current_schedule["signature"] == signature:
                continue

            version = (current_schedule["version"] if current_schedule else 0) + 1
            first_date = getdate(row.first_dose_date)
            for dose_number in range(dose_count):
                scheduled_date = first_date + timedelta(days=interval * dose_number)
                self.append(
                    "treatment_doses",
                    {
                        "item": row.item,
                        "medicine_name": protocol.medicine_name or row.item,
                        "dose": _("Dose {0} of {1}").format(dose_number + 1, dose_count),
                        "scheduled_date": scheduled_date,
                        "dispensed": 0,
                        "protocol_item": row.name,
                        "schedule_version": version,
                        "regimen_signature": signature,
                    },
                )
            schedules[row.name] = {"version": version, "signature": signature}

    def update_dose_summary(self):
        if self.status != APPROVED_STATUS:
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

    @staticmethod
    def _has_protocol_catalog():
        return frappe.get_meta("Item").has_field("official_protocol_code")

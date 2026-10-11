import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import cint, flt, now_datetime, nowdate

from state_treatment.utils import get_protocol_item_price


class StateTreatmentRecommendation(Document):
    def autoname(self):
        self.name = make_autoname(
            "STR-{0}-.#####".format(self.recommendation_year or nowdate()[:4])
        )

    def validate(self):
        self.calculate_total()
        self.validate_treatment_doses()

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
                for fieldname in ("item", "dose", "scheduled_date"):
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
                ["item_name", "official_protocol_code", "duration_days", "decision_sequence"],
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
            row.rate = flt(rate)
            total += flt(row.rate)
        self.total_amount = total

    @staticmethod
    def _has_protocol_catalog():
        return frappe.get_meta("Item").has_field("official_protocol_code")

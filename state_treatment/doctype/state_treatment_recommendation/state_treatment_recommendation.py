import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, nowdate

from state_treatment.utils import get_protocol_item_price


class StateTreatmentRecommendation(Document):
    def autoname(self):
        self.name = make_autoname(
            "STR-{0}-.#####".format(self.recommendation_year or nowdate()[:4])
        )

    def validate(self):
        self.calculate_total()

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

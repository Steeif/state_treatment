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
        for row in self.protocol_items:
            if row.item and not row.rate:
                row.rate = get_protocol_item_price(row.item) or 0
            total += flt(row.rate)
        self.total_amount = total

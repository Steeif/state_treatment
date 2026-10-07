import frappe
from frappe import _
from frappe.utils import flt


def validate_sales_invoice(doc, method=None):
    recommendation_name = doc.get("state_treatment_recommendation")
    if not recommendation_name:
        return

    reco = frappe.get_doc("State Treatment Recommendation", recommendation_name)

    # 1) recommendation must be fully approved
    if reco.status != "Approved for Disbursement":
        frappe.throw(_(
            "Sales Invoice cannot be booked against recommendation {0} "
            "unless its status is 'Approved for Disbursement' (current: {1})."
        ).format(reco.name, reco.status))

    # 2) every invoice item must belong to the recommendation's protocol items
    allowed_items = {d.item for d in reco.protocol_items}
    for item in doc.get("items") or []:
        if item.item_code not in allowed_items:
            frappe.throw(_(
                "Item {0} is not part of the approved protocol items of "
                "recommendation {1}."
            ).format(item.item_code, reco.name))

    # 3) (optional guard) invoice total must not exceed the approved total
    invoice_total = flt(doc.grand_total or doc.rounded_total)
    if invoice_total and reco.total_amount and invoice_total > reco.total_amount:
        frappe.throw(_(
            "Invoice total {0} exceeds the approved recommendation total {1}."
        ).format(invoice_total, reco.total_amount))

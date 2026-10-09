import frappe
from frappe import _


def validate_sales_invoice(doc, method=None):
    recommendation_name = doc.get("state_treatment_recommendation")
    if not recommendation_name:
        return

    reco = frappe.get_doc("State Treatment Recommendation", recommendation_name)

    # Draft invoices may be prepared before the recommendation is approved.
    if reco.status != "Approved for Disbursement":
        frappe.throw(_(
            "Sales Invoice cannot be booked against recommendation {0} "
            "unless its status is 'Approved for Disbursement' (current: {1})."
        ).format(reco.name, reco.status))

    allowed_items = {d.item for d in reco.protocol_items}
    for item in doc.get("items") or []:
        if item.item_code not in allowed_items:
            frappe.throw(_(
                "Item {0} is not part of the approved protocol items of "
                "recommendation {1}."
            ).format(item.item_code, reco.name))

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from state_treatment.settings import get_state_price_list


def get_protocol_item_price(item_code):
    """Return the State price list rate for a protocol item, or 0 when it is not priced.

    Reads Item Price directly. ERPNext's get_item_price needs a larger args dict
    (batch_no and more) that differs between ERPNext versions, and sync_protocol_price
    stores protocol prices without a UOM, so a direct match is enough.
    """
    rows = frappe.db.sql(
        """
        select price_list_rate
        from `tabItem Price`
        where item_code = %(item_code)s
          and price_list = %(price_list)s
          and (valid_from is null or valid_from <= %(today)s)
          and (valid_upto is null or valid_upto >= %(today)s)
        order by valid_from desc, modified desc
        limit 1
        """,
        {
            "item_code": item_code,
            "price_list": get_state_price_list(),
            "today": nowdate(),
        },
    )
    return flt(rows[0][0]) if rows else 0


@frappe.whitelist()
def get_protocol_item_details(item_code):
    """Called from the client when a protocol item is picked in the child table."""
    if not frappe.get_meta("Item").has_field("official_protocol_code"):
        frappe.throw(_("Import the authorized protocol catalog before adding treatment items."))

    item = frappe.db.get_value(
        "Item",
        item_code,
        [
            "item_name", "duration_days", "decision_sequence", "official_protocol_code",
            "protocol_treatment_type", "medicine_name", "number_of_doses",
            "dose_interval_days",
        ],
        as_dict=True,
    ) or {}
    if not item.get("official_protocol_code"):
        frappe.throw(_("Selected item is not part of the treatment protocol catalog."))

    return {
        "item_name": item.get("item_name"),
        "duration_days": item.get("duration_days") or 0,
        "decision_sequence": item.get("decision_sequence"),
        "official_protocol_code": item.get("official_protocol_code"),
        "treatment_type": item.get("protocol_treatment_type"),
        "medicine_name": item.get("medicine_name"),
        "number_of_doses": item.get("number_of_doses") or 0,
        "dose_interval_days": item.get("dose_interval_days") or 0,
        "price": get_protocol_item_price(item_code),
    }

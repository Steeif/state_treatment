import frappe

STATE_PRICE_LIST = "نفقة الدولة"  # State-funded price list


def get_protocol_item_price(item_code):
    """Return the currently valid ERPNext price for a protocol item."""
    from erpnext.stock.get_item_details import get_item_price

    uom = frappe.db.get_value("Item", item_code, "stock_uom")
    prices = get_item_price(
        {
            "price_list": STATE_PRICE_LIST,
            "uom": uom,
            "transaction_date": frappe.utils.nowdate(),
        },
        item_code,
    )
    return prices[0][1] if prices else 0


@frappe.whitelist()
def get_protocol_item_details(item_code):
    """Called from the client when a protocol item is picked in the child table."""
    if not frappe.get_meta("Item").has_field("official_protocol_code"):
        frappe.throw("Import the authorized protocol catalog before adding treatment items.")

    item = frappe.db.get_value(
        "Item",
        item_code,
        ["item_name", "duration_days", "decision_sequence", "official_protocol_code"],
        as_dict=True,
    ) or {}
    if not item.get("official_protocol_code"):
        frappe.throw("Selected item is not part of the treatment protocol catalog.")

    return {
        "item_name": item.get("item_name"),
        "duration_days": item.get("duration_days") or 0,
        "decision_sequence": item.get("decision_sequence"),
        "official_protocol_code": item.get("official_protocol_code"),
        "price": get_protocol_item_price(item_code),
    }

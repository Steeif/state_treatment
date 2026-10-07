import frappe

STATE_PRICE_LIST = "نفقة الدولة"  # State-funded price list


def get_protocol_item_price(item_code):
    """Return the price of `item_code` from the "نفقة الدولة" price list.

    Tries ERPNext's get_item_price first (respects valid_from/upto, UOM, etc.).
    If it is unavailable or returns nothing, falls back to a direct query on
    the Item Price table by item_code + price_list.
    """
    price = None
    try:
        from erpnext.stock.get_item_details import get_item_price as erpnext_get_item_price

        args = {
            "price_list": STATE_PRICE_LIST,
            "uom": None,
            "transaction_date": frappe.utils.nowdate(),
        }
        result = erpnext_get_item_price(args, item_code)
        if result:
            # result is a list of (name, price_list_rate) tuples
            price = result[0][1]
    except Exception:
        price = None

    if not price:
        price = frappe.db.get_value(
            "Item Price",
            {"item_code": item_code, "price_list": STATE_PRICE_LIST},
            "price_list_rate",
        )

    return price or 0


@frappe.whitelist()
def get_protocol_item_details(item_code):
    """Called from the client when a protocol item is picked in the child table."""
    item = frappe.db.get_value(
        "Item",
        item_code,
        ["item_name", "duration_days", "decision_sequence", "official_protocol_code"],
        as_dict=True,
    ) or {}
    return {
        "item_name": item.get("item_name"),
        "duration_days": item.get("duration_days") or 0,
        "decision_sequence": item.get("decision_sequence"),
        "official_protocol_code": item.get("official_protocol_code"),
        "price": get_protocol_item_price(item_code),
    }

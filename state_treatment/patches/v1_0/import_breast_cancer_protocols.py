"""Import master data: 133 breast-cancer treatment protocol items.

Creates (idempotently):
- 4 Custom Fields on Item
- Price List "نفقة الدولة"
- Item Group "سرطان بالثدي (مبادرة)"
- one Item per protocol row  (item_code = "{protocol_code}-{serial}",
  official code kept in Item.official_protocol_code)
- one Item Price per Item on the "نفقة الدولة" price list
"""
import json
import os

import frappe

PRICE_LIST = "نفقة الدولة"
DIAGNOSIS_GROUP = "سرطان بالثدي (مبادرة)"

ITEM_CUSTOM_FIELDS = {
    "Item": [
        dict(fieldname="official_protocol_code", label="Official Protocol Code",
             fieldtype="Data", insert_after="item_code"),
        dict(fieldname="duration_days", label="Duration (Days)",
             fieldtype="Int", insert_after="official_protocol_code"),
        dict(fieldname="decision_sequence", label="Decision Sequence",
             fieldtype="Int", insert_after="duration_days"),
        dict(fieldname="diagnosis_group", label="Diagnosis Group",
             fieldtype="Data", insert_after="item_group", in_standard_filter=1),
    ]
}


def execute():
    data_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "data", "breast_cancer_protocols.json",
    )
    with open(data_path, encoding="utf-8") as f:
        rows = json.load(f)

    ensure_custom_fields()
    ensure_price_list()
    ensure_item_group()
    for row in rows:
        import_item(row)


def ensure_custom_fields():
    try:
        from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
        create_custom_fields(ITEM_CUSTOM_FIELDS, ignore_validate=True)
    except Exception:
        # fallback: create one by one
        for dt, fields in ITEM_CUSTOM_FIELDS.items():
            for f in fields:
                if not frappe.db.exists("Custom Field", "{0}-{1}".format(dt, f["fieldname"])):
                    frappe.get_doc(dict(doctype="Custom Field", dt=dt, **f)).insert(ignore_permissions=True)
    frappe.clear_cache(doctype="Item")


def ensure_price_list():
    if not frappe.db.exists("Price List", PRICE_LIST):
        frappe.get_doc(dict(
            doctype="Price List",
            price_list_name=PRICE_LIST,
            enabled=1,
            selling=1,
            buying=0,
            currency="EGP",
        )).insert(ignore_permissions=True)


def ensure_item_group():
    if not frappe.db.exists("Item Group", DIAGNOSIS_GROUP):
        frappe.get_doc(dict(
            doctype="Item Group",
            item_group_name=DIAGNOSIS_GROUP,
            parent_item_group="All Item Groups",
        )).insert(ignore_permissions=True)


def import_item(row):
    item_code = "{0}-{1}".format(row["protocol_code"], row["serial"])
    amount = row["amount_egp"]

    if frappe.db.exists("Item", item_code):
        upsert_price(item_code, amount)
        return

    item = frappe.get_doc(dict(
        doctype="Item",
        item_code=item_code,
        item_name=row["procedure_name"],
        item_group=DIAGNOSIS_GROUP,
        stock_uom="Nos",
        is_stock_item=0,
        is_sales_item=1,
        is_purchase_item=0,
        include_item_in_manufacturing=0,
        official_protocol_code=row["protocol_code"],
        duration_days=row["duration_days"],
        decision_sequence=row["decision_sequence"],
        diagnosis_group=row["diagnosis_group"],
    ))
    item.insert(ignore_permissions=True)
    upsert_price(item_code, amount)


def upsert_price(item_code, amount):
    name = frappe.db.get_value(
        "Item Price", {"item_code": item_code, "price_list": PRICE_LIST}, "name")
    if name:
        frappe.db.set_value("Item Price", name, "price_list_rate", amount)
    else:
        frappe.get_doc(dict(
            doctype="Item Price",
            item_code=item_code,
            price_list=PRICE_LIST,
            price_list_rate=amount,
        )).insert(ignore_permissions=True)

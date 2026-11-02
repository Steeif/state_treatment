"""Import authorized breast-cancer protocol master data from a private file.

Creates (idempotently):
- protocol fields on Item
- Price List "نفقة الدولة"
- Item Group "سرطان بالثدي (مبادرة)"
- one Item per protocol row  (item_code = "{protocol_code}-{serial}",
  official code kept in Item.official_protocol_code)
- one Item Price per Item on the "نفقة الدولة" price list
"""
import json
import math
import os

import frappe
from frappe import _
from state_treatment.item_protocol import ensure_item_protocol_fields

PRICE_LIST = "نفقة الدولة"

def execute(file_path=None):
    """Import protocol data explicitly after install; never run as a migration patch."""
    data_path = file_path or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "data",
        "breast_cancer_protocols.json",
    )
    data_path = os.path.abspath(data_path)
    if not os.path.isfile(data_path):
        frappe.throw(_("Protocol data file was not found: {0}").format(data_path))

    with open(data_path, encoding="utf-8") as f:
        rows = json.load(f)
    validate_rows(rows)

    ensure_custom_fields()
    ensure_price_list()
    ensure_item_group(rows[0]["diagnosis_group"])
    for row in rows:
        import_item(row)


def validate_rows(rows):
    if not isinstance(rows, list) or not rows:
        frappe.throw(_("Protocol data must be a non-empty JSON array."))

    serials = set()
    item_codes = set()
    diagnosis_group = rows[0].get("diagnosis_group") if isinstance(rows[0], dict) else None
    required = ("serial", "protocol_code", "diagnosis_group", "procedure_name", "amount_egp", "duration_days")
    for row in rows:
        if not isinstance(row, dict):
            frappe.throw(_("Each protocol row must be a JSON object."))
        missing = [key for key in required if key not in row or row[key] is None]
        if missing:
            frappe.throw(_("Protocol row is missing required fields: {0}").format(", ".join(missing)))
        if row["serial"] in serials:
            frappe.throw(_("Protocol serial {0} appears more than once.").format(row["serial"]))
        serials.add(row["serial"])
        if isinstance(row["serial"], bool) or not isinstance(row["serial"], int) or row["serial"] < 1:
            frappe.throw(_("Protocol serials must be positive integers."))
        item_code = "{0}-{1}".format(row["protocol_code"], row["serial"])
        if item_code in item_codes:
            frappe.throw(_("Generated item code {0} is not unique.").format(item_code))
        item_codes.add(item_code)
        if row["diagnosis_group"] != diagnosis_group:
            frappe.throw(_("All protocol rows must use the same diagnosis group."))
        if not row["diagnosis_group"]:
            frappe.throw(_("Diagnosis group is required in every protocol row."))
        if not row["protocol_code"] or not row["procedure_name"]:
            frappe.throw(_("Protocol code and procedure name are required for row {0}.").format(row["serial"]))
        amount = row["amount_egp"]
        duration = row["duration_days"]
        if (isinstance(amount, bool) or not isinstance(amount, (int, float))
                or not math.isfinite(amount) or amount < 0):
            frappe.throw(_("Amount must be a non-negative number in row {0}.").format(row["serial"]))
        if isinstance(duration, bool) or not isinstance(duration, int) or duration < 0:
            frappe.throw(_("Duration must be a non-negative integer in row {0}.").format(row["serial"]))


def ensure_custom_fields():
    ensure_item_protocol_fields()


def ensure_price_list():
    if frappe.db.exists("Price List", PRICE_LIST):
        details = frappe.db.get_value("Price List", PRICE_LIST, ["currency", "enabled", "selling"], as_dict=True)
        currency = details.currency
        if currency != "EGP":
            frappe.throw(_("The State-funded price list must use EGP; current currency is {0}.").format(currency))
        if not details.enabled or not details.selling:
            frappe.throw(_("The State-funded price list must be enabled for selling."))
    else:
        frappe.get_doc(dict(
            doctype="Price List",
            price_list_name=PRICE_LIST,
            enabled=1,
            selling=1,
            buying=0,
            currency="EGP",
        )).insert(ignore_permissions=True)


def ensure_item_group(diagnosis_group):
    if not frappe.db.exists("Item Group", diagnosis_group):
        frappe.get_doc(dict(
            doctype="Item Group",
            item_group_name=diagnosis_group,
            parent_item_group="All Item Groups",
        )).insert(ignore_permissions=True)


def import_item(row):
    item_code = "{0}-{1}".format(row["protocol_code"], row["serial"])
    amount = row["amount_egp"]

    if frappe.db.exists("Item", item_code):
        existing_code = frappe.db.get_value("Item", item_code, "official_protocol_code")
        if existing_code != row["protocol_code"]:
            frappe.throw(_("Item code {0} is already used by a different protocol.").format(item_code))
        frappe.db.set_value("Item", item_code, {
            "item_name": row["procedure_name"],
            "item_group": row["diagnosis_group"],
            "official_protocol_code": row["protocol_code"],
            "is_protocol": 1,
            "protocol_treatment_type": "Procedure",
            "protocol_serial": row["serial"],
            "internal_protocol_code": "{0}-PROC-{1:05d}".format(row["protocol_code"], row["serial"]),
            "protocol_price": amount,
            "duration_days": row["duration_days"],
            "decision_sequence": row.get("decision_sequence"),
            "diagnosis_group": row["diagnosis_group"],
        })
        upsert_price(item_code, amount)
        return

    item = frappe.get_doc(dict(
        doctype="Item",
        item_code=item_code,
        item_name=row["procedure_name"],
        item_group=row["diagnosis_group"],
        stock_uom="Nos",
        is_stock_item=0,
        is_sales_item=1,
        is_purchase_item=0,
        include_item_in_manufacturing=0,
        official_protocol_code=row["protocol_code"],
        is_protocol=1,
        protocol_treatment_type="Procedure",
        protocol_serial=row["serial"],
        internal_protocol_code="{0}-PROC-{1:05d}".format(row["protocol_code"], row["serial"]),
        protocol_price=amount,
        duration_days=row["duration_days"],
        decision_sequence=row.get("decision_sequence"),
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

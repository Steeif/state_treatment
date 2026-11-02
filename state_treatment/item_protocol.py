import re

import frappe
from frappe import _
from frappe.model.naming import make_autoname
from frappe.utils import cint, flt


STATE_PRICE_LIST = "نفقة الدولة"

ITEM_CUSTOM_FIELDS = [
    {
        "fieldname": "official_protocol_code",
        "label": "كود الوزارة / Ministry Code",
        "fieldtype": "Data",
        "insert_after": "item_code",
        "depends_on": "eval:doc.is_protocol",
    },
    {
        "fieldname": "is_protocol",
        "label": "بروتوكول / Is Protocol",
        "fieldtype": "Check",
        "default": "0",
        "insert_after": "item_name",
        "in_list_view": 1,
    },
    {
        "fieldname": "protocol_section",
        "label": "بيانات البروتوكول / Protocol Details",
        "fieldtype": "Section Break",
        "insert_after": "is_protocol",
        "depends_on": "eval:doc.is_protocol",
    },
    {
        "fieldname": "protocol_treatment_type",
        "label": "نوع العلاج / Treatment Type",
        "fieldtype": "Select",
        "options": "Medicine\nProcedure",
        "insert_after": "protocol_section",
        "depends_on": "eval:doc.is_protocol",
    },
    {
        "fieldname": "protocol_serial",
        "label": "رقم متسلسل / Serial No.",
        "fieldtype": "Int",
        "insert_after": "protocol_treatment_type",
        "read_only": 1,
        "depends_on": "eval:doc.is_protocol",
    },
    {
        "fieldname": "internal_protocol_code",
        "label": "الكود الداخلي / Internal Protocol Code",
        "fieldtype": "Data",
        "insert_after": "protocol_serial",
        "read_only": 1,
        "depends_on": "eval:doc.is_protocol",
    },
    {
        "fieldname": "duration_days",
        "label": "مدة العلاج بالأيام / Treatment Duration (Days)",
        "fieldtype": "Int",
        "insert_after": "internal_protocol_code",
        "depends_on": 'eval:doc.is_protocol && doc.protocol_treatment_type == "Medicine"',
        "mandatory_depends_on": 'eval:doc.is_protocol && doc.protocol_treatment_type == "Medicine"',
    },
    {
        "fieldname": "decision_sequence",
        "label": "ترتيب القرار / Decision Sequence",
        "fieldtype": "Int",
        "insert_after": "duration_days",
        "depends_on": "eval:doc.is_protocol",
    },
    {
        "fieldname": "protocol_period_per",
        "label": "الفترة لكل / Period Per",
        "fieldtype": "Data",
        "insert_after": "decision_sequence",
        "depends_on": "eval:doc.is_protocol",
    },
    {
        "fieldname": "protocol_price",
        "label": "السعر بالجنيه / Price (EGP)",
        "fieldtype": "Currency",
        "insert_after": "protocol_period_per",
        "depends_on": "eval:doc.is_protocol",
    },
    {
        "fieldname": "protocol_notes",
        "label": "ملاحظات / استكمال / Notes",
        "fieldtype": "Small Text",
        "insert_after": "protocol_price",
        "depends_on": "eval:doc.is_protocol",
    },
    {
        "fieldname": "procedure_section",
        "label": "بيانات الإجراء / Procedure Details",
        "fieldtype": "Section Break",
        "insert_after": "protocol_notes",
        "depends_on": 'eval:doc.is_protocol && doc.protocol_treatment_type == "Procedure"',
    },
    {
        "fieldname": "procedure_schedule",
        "label": "جدول زمني للإجراءات / Procedure Schedule",
        "fieldtype": "Small Text",
        "insert_after": "procedure_section",
        "depends_on": 'eval:doc.is_protocol && doc.protocol_treatment_type == "Procedure"',
    },
    {
        "fieldname": "procedure_time_days",
        "label": "Procedure Time (Unused)",
        "fieldtype": "Int",
        "insert_after": "procedure_schedule",
        "hidden": 1,
    },
    {
        "fieldname": "medicine_section",
        "label": "بيانات الدواء / Medicine Details",
        "fieldtype": "Section Break",
        "insert_after": "procedure_schedule",
        "depends_on": 'eval:doc.is_protocol && doc.protocol_treatment_type == "Medicine"',
    },
    {
        "fieldname": "medicine_name",
        "label": "اسم الدواء / Medicine Name",
        "fieldtype": "Data",
        "insert_after": "medicine_section",
        "depends_on": 'eval:doc.is_protocol && doc.protocol_treatment_type == "Medicine"',
        "mandatory_depends_on": 'eval:doc.is_protocol && doc.protocol_treatment_type == "Medicine"',
    },
    {
        "fieldname": "number_of_doses",
        "label": "عدد الجرعات / Number of Doses",
        "fieldtype": "Int",
        "insert_after": "medicine_name",
        "depends_on": 'eval:doc.is_protocol && doc.protocol_treatment_type == "Medicine"',
    },
    {
        "fieldname": "dose_interval_days",
        "label": "الفترة بين الجرعات بالأيام / Days Between Doses",
        "fieldtype": "Float",
        "insert_after": "number_of_doses",
        "read_only": 1,
        "depends_on": 'eval:doc.is_protocol && doc.protocol_treatment_type == "Medicine"',
    },
    {
        "fieldname": "diagnosis_group",
        "label": "Diagnosis Group",
        "fieldtype": "Data",
        "insert_after": "item_group",
        "in_standard_filter": 1,
    },
]


def ensure_item_protocol_fields():
    """Create/update Item fields and expose the existing protocol catalog."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields(
        {"Item": ITEM_CUSTOM_FIELDS},
        ignore_validate=True,
        update=True,
    )
    frappe.clear_cache(doctype="Item")
    backfill_existing_protocol_items()


def backfill_existing_protocol_items():
    """Keep catalog items created by the existing importer visible as protocols."""
    if not frappe.db.table_exists("Item") or not frappe.db.table_exists("Item Price"):
        return
    if not frappe.db.exists("Price List", STATE_PRICE_LIST):
        return

    items = frappe.get_all(
        "Item",
        filters={"official_protocol_code": ["is", "set"]},
        fields=[
            "name",
            "official_protocol_code",
            "duration_days",
            "decision_sequence",
            "protocol_serial",
            "is_protocol",
            "protocol_treatment_type",
            "internal_protocol_code",
            "protocol_price",
        ],
    )
    for item in items:
        serial = cint(item.protocol_serial)
        if not serial:
            match = re.search(r"-(\d+)$", item.name)
            serial = cint(match.group(1)) if match else 0
        if not serial:
            serial_token = make_autoname("STP-.#####")
            serial = cint(serial_token.rsplit("-", 1)[-1])

        serial_text = str(serial).zfill(5)
        internal_code = f"{item.official_protocol_code}-PROC-{serial_text}"
        values = {
            "is_protocol": 1,
            "protocol_treatment_type": item.protocol_treatment_type or "Procedure",
            "protocol_serial": serial,
            "internal_protocol_code": item.internal_protocol_code or internal_code,
        }
        price = frappe.db.get_value(
            "Item Price",
            {"item_code": item.name, "price_list": STATE_PRICE_LIST},
            "price_list_rate",
        )
        if item.protocol_price is None and price is not None:
            values["protocol_price"] = price
        frappe.db.set_value("Item", item.name, values, update_modified=False)


def validate_protocol_item(doc, method=None):
    if not cint(doc.get("is_protocol")):
        return

    if not doc.get("official_protocol_code"):
        frappe.throw(_("Ministry Code is required for a protocol item."))
    if doc.protocol_treatment_type not in ("Medicine", "Procedure"):
        frappe.throw(_("Select Medicine or Procedure as the treatment type."))

    if not cint(doc.protocol_serial):
        serial_token = make_autoname("STP-.#####")
        doc.protocol_serial = cint(serial_token.rsplit("-", 1)[-1])

    type_code = "MED" if doc.protocol_treatment_type == "Medicine" else "PROC"
    doc.internal_protocol_code = (
        f"{doc.official_protocol_code}-{type_code}-{cint(doc.protocol_serial):05d}"
    )

    if doc.protocol_treatment_type == "Medicine":
        if not doc.get("medicine_name"):
            frappe.throw(_("Medicine name is required for a medicine protocol."))
        doses = cint(doc.number_of_doses)
        duration = flt(doc.duration_days)
        if doses <= 0:
            frappe.throw(_("Number of doses must be greater than zero for a medicine protocol."))
        if duration <= 0:
            frappe.throw(_("Period duration must be greater than zero for a medicine protocol."))
        doc.dose_interval_days = round(duration / doses, 2)


def sync_protocol_price(doc, method=None):
    if not cint(doc.get("is_protocol")) or doc.get("protocol_price") in (None, ""):
        return
    if not frappe.db.exists("Price List", STATE_PRICE_LIST):
        frappe.throw(_("Create the State-funded price list before setting a protocol price."))

    item_price = frappe.db.get_value(
        "Item Price",
        {"item_code": doc.name, "price_list": STATE_PRICE_LIST},
        "name",
    )
    if item_price:
        frappe.db.set_value(
            "Item Price",
            item_price,
            "price_list_rate",
            flt(doc.protocol_price),
        )
    else:
        frappe.get_doc(
            {
                "doctype": "Item Price",
                "item_code": doc.name,
                "price_list": STATE_PRICE_LIST,
                "price_list_rate": flt(doc.protocol_price),
            }
        ).insert(ignore_permissions=True)

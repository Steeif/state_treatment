"""Site-specific values, kept in the State Treatment Settings record."""
import frappe

SETTINGS = "State Treatment Settings"

DEFAULT_PRICE_LIST = "نفقة الدولة"
# Patient custom field "رقم البطاقة" (card number = national ID). It exists on
# client sites only, and this app never creates it. Frappe builds fieldnames by
# replacing spaces with underscores, so the label gives this name.
DEFAULT_NATIONAL_ID_FIELD = "رقم_البطاقة"


def get_state_price_list():
    return frappe.db.get_single_value(SETTINGS, "state_price_list") or DEFAULT_PRICE_LIST


def get_patient_national_id_field():
    return (
        frappe.db.get_single_value(SETTINGS, "patient_national_id_field")
        or DEFAULT_NATIONAL_ID_FIELD
    )


def ensure_price_list(name):
    """Create the State price list (EGP, enabled, for selling) if it does not exist."""
    if frappe.db.exists("Price List", name):
        return
    frappe.get_doc({
        "doctype": "Price List",
        "price_list_name": name,
        "currency": "EGP",
        "enabled": 1,
        "selling": 1,
        "buying": 0,
    }).insert(ignore_permissions=True)


def ensure_settings():
    """Fill in missing settings and create the price list. Runs after every migrate."""
    doc = frappe.get_single(SETTINGS)
    doc.state_price_list = doc.state_price_list or DEFAULT_PRICE_LIST
    doc.patient_national_id_field = doc.patient_national_id_field or DEFAULT_NATIONAL_ID_FIELD
    # Create the price list before saving, because the Link field is validated on save.
    ensure_price_list(doc.state_price_list)
    doc.save(ignore_permissions=True)

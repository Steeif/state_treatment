"""Site-specific values, kept in the State Treatment Settings record."""
import frappe

SETTINGS = "State Treatment Settings"
MAP_FIELD = "patient_field_map"

DEFAULT_PRICE_LIST = "نفقة الدولة"
# Patient custom field "رقم البطاقة" (card number = national ID). It exists on
# client sites only, and this app never creates it. Frappe builds fieldnames by
# replacing spaces with underscores, so the label gives this name.
DEFAULT_NATIONAL_ID_FIELD = "رقم_البطاقة"


def get_state_price_list():
    return frappe.db.get_single_value(SETTINGS, "state_price_list") or DEFAULT_PRICE_LIST


def get_patient_field_map():
    """(request field, Patient fieldname) pairs from State Treatment Settings, in row order."""
    rows = frappe.get_single(SETTINGS).get(MAP_FIELD) or []
    return [(row.form_field, row.patient_field) for row in rows if row.form_field and row.patient_field]


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
    # Create the price list before saving, because the Link field is validated on save.
    ensure_price_list(doc.state_price_list)
    doc.save(ignore_permissions=True)


def seed_default_patient_map():
    """Add the default National ID row when the map is empty.

    Runs once on install and once on existing sites through a patch, so a
    map that an administrator has emptied is not refilled on every migrate.
    """
    doc = frappe.get_single(SETTINGS)
    if doc.get(MAP_FIELD):
        return
    # Sites set up before the map existed kept the National ID field in its own setting.
    legacy = frappe.db.get_single_value(SETTINGS, "patient_national_id_field")
    doc.append(MAP_FIELD, {
        "form_field": "national_id",
        "patient_field": legacy or DEFAULT_NATIONAL_ID_FIELD,
    })
    doc.save(ignore_permissions=True)


def after_install():
    ensure_settings()
    seed_default_patient_map()

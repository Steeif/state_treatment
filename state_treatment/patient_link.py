"""Link Healthcare Patients to their State Treatment Recommendations.

Adds read-only summary fields on Patient, keeps them in sync with the
recommendations, and shows the recommendations on the Patient dashboard.
"""
import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from state_treatment.settings import get_patient_national_id_field

RECOMMENDATION = "State Treatment Recommendation"

PATIENT_CUSTOM_FIELDS = [
    {
        "fieldname": "state_treatment_section",
        "fieldtype": "Section Break",
        "label": "State Treatment",
        "insert_after": "uid",
        "collapsible": 1,
    },
    {
        "fieldname": "latest_state_treatment",
        "fieldtype": "Link",
        "label": "Latest State Treatment Request",
        "options": RECOMMENDATION,
        "insert_after": "state_treatment_section",
        "read_only": 1,
        "no_copy": 1,
    },
    {
        "fieldname": "state_treatment_status",
        "fieldtype": "Data",
        "label": "State Treatment Status",
        "insert_after": "latest_state_treatment",
        "read_only": 1,
        "no_copy": 1,
    },
    {
        "fieldname": "state_treatment_count",
        "fieldtype": "Int",
        "label": "State Treatment Requests",
        "insert_after": "state_treatment_status",
        "default": "0",
        "read_only": 1,
        "no_copy": 1,
    },
]


def ensure_patient_fields():
    """Create the Patient summary fields. Runs after every migrate."""
    if not frappe.db.table_exists("Patient"):
        return
    create_custom_fields({"Patient": PATIENT_CUSTOM_FIELDS}, ignore_validate=True, update=True)
    frappe.clear_cache(doctype="Patient")


def get_patient_national_id(patient):
    """Return the patient's national ID, or None if the site has no such field."""
    fieldname = get_patient_national_id_field()
    if not patient or not frappe.get_meta("Patient").has_field(fieldname):
        return None
    return frappe.db.get_value("Patient", patient, fieldname)


@frappe.whitelist()
def get_patient_national_id_details(patient):
    """Called by the treatment request form when a patient is picked.

    Tells the form whether the configured Patient field exists on this site,
    so a missing field is reported instead of silently leaving the ID blank.
    """
    if not patient or not frappe.has_permission("Patient", "read"):
        frappe.throw(_("You do not have permission to read this patient."))
    fieldname = get_patient_national_id_field()
    field_exists = frappe.get_meta("Patient").has_field(fieldname)
    return {
        "fieldname": fieldname,
        "field_exists": field_exists,
        "national_id": frappe.db.get_value("Patient", patient, fieldname) if field_exists else None,
    }


def get_patient_summary(patient, exclude=None):
    """Return the summary values for a patient, computed from the recommendations."""
    filters = {"patient": patient}
    if exclude:
        filters["name"] = ["!=", exclude]
    rows = frappe.get_all(
        RECOMMENDATION,
        filters=filters,
        fields=["name", "status"],
        order_by="modified desc",
    )
    return {
        "latest_state_treatment": rows[0].name if rows else None,
        "state_treatment_status": rows[0].status if rows else None,
        "state_treatment_count": len(rows),
    }


def refresh_patient_summary(patient, exclude=None):
    if not patient or not frappe.db.exists("Patient", patient):
        return
    frappe.db.set_value(
        "Patient", patient, get_patient_summary(patient, exclude=exclude), update_modified=False
    )


def on_recommendation_update(doc, method=None):
    """Refresh the summary on the current patient and, if it changed, the previous one."""
    patients = {doc.patient}
    before = doc.get_doc_before_save()
    if before and before.patient and before.patient != doc.patient:
        patients.add(before.patient)
    for patient in patients:
        refresh_patient_summary(patient)


def on_recommendation_trash(doc, method=None):
    # The document still exists during on_trash, so leave it out of the count.
    refresh_patient_summary(doc.patient, exclude=doc.name)


def sync_patient_summary(doc, method=None):
    """Patient before_save: replace summary values with current ones.

    Without this, a Patient form opened before a recommendation changed
    would save its stale summary back over the new one.
    """
    if doc.is_new() or not doc.name:
        summary = {
            "latest_state_treatment": None,
            "state_treatment_status": None,
            "state_treatment_count": 0,
        }
    else:
        summary = get_patient_summary(doc.name)
    doc.update(summary)


def backfill_patient_summaries():
    """Bring the summaries up to date for every patient that has a recommendation."""
    if not frappe.db.table_exists(RECOMMENDATION):
        return
    for patient in frappe.get_all(RECOMMENDATION, distinct=True, pluck="patient"):
        refresh_patient_summary(patient)


def get_patient_dashboard_data(data):
    """Hooked into Patient's dashboard so its connections list treatment requests."""
    data.setdefault("transactions", []).append({
        "label": _("State Treatment"),
        "items": [RECOMMENDATION],
    })
    return data

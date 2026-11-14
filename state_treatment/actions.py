"""Form buttons for an approved State Treatment Recommendation.

A Medical Reviewer marks a procedure as done, and a Treatment Pharmacist
dispenses a dose. Both run on the server and check the role here. They save
with ignore_permissions because the workflow allows editing an approved
request only for the General Manager, which would otherwise block them.
The normal validate() chain still runs on every save.
"""

import frappe
from frappe import _
from frappe.utils import cint
from frappe.model.workflow import apply_workflow

from state_treatment.state_treatment.doctype.state_treatment_recommendation.state_treatment_recommendation import (
    APPROVED_STATUS,
    COMPLETED_STATUS,
)

DOCTYPE = "State Treatment Recommendation"
PROCEDURE_ROLES = ("Medical Reviewer", "System Manager")
PHARMACIST_ROLES = ("Treatment Pharmacist", "System Manager")
CLOSE_ROLES = ("General Manager", "System Manager")
CLOSE_ACTION = "Close Treatment"


@frappe.whitelist()
def mark_procedure_done(recommendation, row_name):
    _require_role(PROCEDURE_ROLES, _("Only a Medical Reviewer can mark a procedure as done."))
    doc = _load_approved(recommendation)
    row = _find_row(doc.protocol_items, row_name)
    if row.treatment_type != "Procedure":
        frappe.throw(_("Only procedure items can be marked as done."))
    if cint(row.procedure_done):
        frappe.throw(_("Procedure {0} is already done.").format(row.item_name or row.item))

    row.procedure_done = 1
    doc.save(ignore_permissions=True)
    return {"status": doc.status}


@frappe.whitelist()
def mark_dose_dispensed(recommendation, row_name):
    _require_role(PHARMACIST_ROLES, _("Only a Treatment Pharmacist can mark a dose as dispensed."))
    doc = _load_approved(recommendation)
    dose = _find_row(doc.treatment_doses, row_name)
    if cint(dose.dispensed):
        frappe.throw(_("{0} is already dispensed.").format(dose.dose))
    if cint(dose.schedule_version) < _latest_version(doc.treatment_doses, dose.protocol_item):
        frappe.throw(
            _("{0} belongs to an earlier schedule version and cannot be dispensed.").format(dose.dose)
        )

    dose.dispensed = 1
    doc.save(ignore_permissions=True)
    return {"status": doc.status}


def _require_role(roles, message):
    if not set(roles) & set(frappe.get_roles()):
        frappe.throw(message)


def _load_approved(recommendation):
    doc = frappe.get_doc(DOCTYPE, recommendation)
    doc.check_permission("read")
    if doc.status not in (APPROVED_STATUS, COMPLETED_STATUS):
        frappe.throw(
            _("Actions are only available after the recommendation is approved for disbursement.")
        )
    return doc


def _find_row(rows, row_name):
    for row in rows:
        if row.name == row_name:
            return row
    frappe.throw(_("Row {0} was not found in this recommendation.").format(row_name))


def _latest_version(doses, protocol_item):
    return max(
        (cint(dose.schedule_version) for dose in doses if dose.protocol_item == protocol_item),
        default=0,
    )


@frappe.whitelist()
def close_treatment(recommendation):
    """Move an approved request to Treatment Completed through its workflow transition."""
    _require_role(CLOSE_ROLES, _("Only the General Manager can close a treatment."))
    doc = frappe.get_doc(DOCTYPE, recommendation)
    doc.check_permission("read")
    if not doc.is_treatment_finished():
        frappe.throw(_("Every procedure must be done and every dose dispensed before the treatment can be closed."))
    apply_workflow(doc, CLOSE_ACTION)
    return {"status": doc.status}

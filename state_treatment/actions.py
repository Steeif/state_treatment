"""Buttons on the State Treatment Recommendation form.

Each action checks the role here, then saves through the normal save, so
validate() and the document permissions run on every change. Status changes
happen only in these actions.
"""

import frappe
from frappe import _
from frappe.utils import cint

from state_treatment.state_treatment.doctype.state_treatment_recommendation.state_treatment_recommendation import (
    APPROVED_STATUS,
    COMPLETED_STATUS,
)

DOCTYPE = "State Treatment Recommendation"
DRAFT_STATUS = "Draft"
REJECTED_STATUS = "Rejected"
APPROVE_ROLES = ("General Manager", "System Manager")
PROCEDURE_ROLES = ("Medical Reviewer", "System Manager")
PHARMACIST_ROLES = ("Treatment Pharmacist", "System Manager")
CLOSE_ROLES = ("General Manager", "System Manager")


@frappe.whitelist()
def approve_for_disbursement(recommendation):
    _require_role(APPROVE_ROLES, _("Only the General Manager can approve a request for disbursement."))
    doc = _load_draft(recommendation)
    if not cint(doc.hospital_file_reviewed):
        frappe.throw(_("Tick File Reviewed at Hospital before approving for disbursement."))
    doc.status = APPROVED_STATUS
    doc.save()
    return {"status": doc.status}


@frappe.whitelist()
def reject_recommendation(recommendation):
    _require_role(APPROVE_ROLES, _("Only the General Manager can reject a request."))
    doc = _load_draft(recommendation)
    doc.status = REJECTED_STATUS
    doc.save()
    return {"status": doc.status}


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
    doc.save()
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
    doc.save()
    return {"status": doc.status}


@frappe.whitelist()
def close_treatment(recommendation):
    _require_role(CLOSE_ROLES, _("Only the General Manager can close a treatment."))
    doc = frappe.get_doc(DOCTYPE, recommendation)
    doc.check_permission("write")
    if doc.status != APPROVED_STATUS:
        frappe.throw(_("Only an approved request can be closed."))
    if not doc.is_treatment_finished():
        frappe.throw(_("Every procedure must be done and every dose dispensed before the treatment can be closed."))
    doc.status = COMPLETED_STATUS
    doc.save()
    return {"status": doc.status}


def _require_role(roles, message):
    if not set(roles) & set(frappe.get_roles()):
        frappe.throw(message)


def _load_draft(recommendation):
    doc = frappe.get_doc(DOCTYPE, recommendation)
    doc.check_permission("write")
    if doc.status != DRAFT_STATUS:
        frappe.throw(_("Only a draft request can be approved or rejected."))
    return doc


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

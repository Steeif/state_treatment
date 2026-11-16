"""Remove the approval workflow and move requests out of the stages it had.

The buttons on the request form replace the workflow. A request that was under
committee review or recommendation-approved goes back to Draft, and the General
Manager approves it again. Nothing could be dispensed in those stages.
"""
import frappe

WORKFLOW = "State Treatment Recommendation Workflow"
REMOVED_STATUSES = ("Under Committee Review", "Recommendation Approved")


def execute():
    if frappe.db.exists("Workflow", WORKFLOW):
        frappe.delete_doc("Workflow", WORKFLOW, ignore_permissions=True, force=1)
    frappe.db.sql(
        "UPDATE `tabState Treatment Recommendation` SET status = 'Draft' WHERE status IN (%s, %s)",
        REMOVED_STATUSES,
    )

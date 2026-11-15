import frappe


def execute():
    """Move requests out of the two removed workflow states.

    Administrative Letter is now a separate record, so those requests go back to
    committee review. File Reviewed at Hospital is now a checkbox, so those requests
    move to Recommendation Approved with the checkbox ticked.
    Runs after the doctype sync, so the checkbox column exists.
    """
    frappe.db.sql(
        """
        update `tabState Treatment Recommendation`
        set status = 'Under Committee Review'
        where status = 'Administrative Letter'
        """
    )
    frappe.db.sql(
        """
        update `tabState Treatment Recommendation`
        set status = 'Recommendation Approved', hospital_file_reviewed = 1
        where status = 'File Reviewed at Hospital'
        """
    )

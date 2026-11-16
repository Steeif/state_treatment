import os

import frappe

SQL_DIR = os.path.join(os.path.dirname(__file__), "report_sql")
MODULE = "State Treatment"
REQUEST = "State Treatment Recommendation"

MANAGEMENT = ["General Manager", "System Manager"]
REVIEW = ["General Manager", "Medical Reviewer", "Admin Reviewer", "System Manager"]

REPORTS = [
    {"name": "الطلبات حسب الحالة", "file": "requests_by_status.sql", "roles": REVIEW + ["Treatment Accountant"]},
    {"name": "المبالغ حسب الحالة", "file": "amounts_by_status.sql", "roles": MANAGEMENT + ["Treatment Accountant"]},
    {"name": "الجرعات المستحقة", "file": "due_doses.sql",
     "roles": ["General Manager", "Treatment Pharmacist", "System Manager"]},
    {"name": "الإجراءات المعلقة", "file": "pending_procedures.sql",
     "roles": ["General Manager", "Medical Reviewer", "System Manager"]},
    {"name": "المواعيد القادمة", "file": "upcoming_appointments.sql", "roles": REVIEW},
]


def ensure_reports():
    """Create or update the query reports from report_sql/*.sql.

    Runs after every migrate. The repository files are the source of truth, so the
    stored SQL and roles are replaced on each migrate.
    """
    for spec in REPORTS:
        with open(os.path.join(SQL_DIR, spec["file"]), encoding="utf-8") as f:
            query = f.read().strip()

        values = {
            "report_name": spec["name"],
            "ref_doctype": REQUEST,
            "report_type": "Query Report",
            "is_standard": "Yes",
            "module": MODULE,
            "query": query,
            "roles": [{"role": role} for role in spec["roles"]],
        }
        if frappe.db.exists("Report", spec["name"]):
            doc = frappe.get_doc("Report", spec["name"])
            doc.update(values)
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc(dict(values, doctype="Report"))
            doc.insert(ignore_permissions=True)

app_name = "state_treatment"
app_title = "State Treatment"
app_publisher = "State Treatment"
app_description = "State-funded treatment recommendations"
app_email = ""
app_license = "MIT"
required_apps = ["erpnext", "healthcare"]

doc_events = {
    "Sales Invoice": {
        "before_submit": "state_treatment.sales_invoice.validate_sales_invoice",
    }
}

fixtures = [
    {"dt": "Custom Field", "filters": [["name", "in", ["Sales Invoice-state_treatment_recommendation"]]]},
    {"dt": "Role", "filters": [["name", "in", ["Admin Reviewer", "Medical Reviewer", "General Manager"]]]},
    {"dt": "Workflow", "filters": [["name", "=", "State Treatment Recommendation Workflow"]]},
    {"dt": "Print Format", "filters": [["name", "=", "Recommendation Official Form"]]},
]

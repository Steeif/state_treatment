app_name = "state_treatment"
app_title = "State Treatment"
app_publisher = "State Treatment"
app_description = "State-funded treatment recommendations"
app_email = ""
app_license = "MIT"
required_apps = ["erpnext", "healthcare"]

after_migrate = ["state_treatment.item_protocol.ensure_item_protocol_fields"]

doctype_js = {
    "Item": "public/js/item.js",
}

doc_events = {
    "Item": {
        "before_validate": "state_treatment.item_protocol.validate_protocol_item",
        "after_insert": "state_treatment.item_protocol.sync_protocol_price",
        "on_update": "state_treatment.item_protocol.sync_protocol_price",
    },
    "Sales Invoice": {
        "before_submit": "state_treatment.sales_invoice.validate_sales_invoice",
    }
}

fixtures = [
    {"dt": "Custom Field", "filters": [["name", "in", ["Sales Invoice-state_treatment_recommendation"]]]},
    {"dt": "Role", "filters": [["name", "in", ["Admin Reviewer", "Medical Reviewer", "General Manager", "Treatment Pharmacist"]]]},
    {"dt": "Workflow", "filters": [["name", "=", "State Treatment Recommendation Workflow"]]},
    {"dt": "Print Format", "filters": [["name", "=", "Recommendation Official Form"]]},
]

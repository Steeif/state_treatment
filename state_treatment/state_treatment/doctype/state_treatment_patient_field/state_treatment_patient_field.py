import frappe
from frappe import _
from frappe.model.document import Document

RECOMMENDATION = "State Treatment Recommendation"
# Request fields that can never be filled from the Patient.
NOT_MAPPABLE_FIELDNAMES = {"patient", "status"}
NOT_MAPPABLE_FIELDTYPES = {
    "Section Break", "Column Break", "Tab Break", "Table", "Table MultiSelect", "Button", "HTML",
}


class StateTreatmentPatientField(Document):
    def validate(self):
        field = frappe.get_meta(RECOMMENDATION).get_field(self.form_field)
        if (
            not field
            or field.fieldtype in NOT_MAPPABLE_FIELDTYPES
            or self.form_field in NOT_MAPPABLE_FIELDNAMES
        ):
            frappe.throw(_("{0} is not a field that can be filled from the Patient.").format(self.form_field))

frappe.ui.form.on("State Treatment Recommendation", {
    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            frm.set_df_property("status", "read_only", 1);
        }

        const grid = frm.fields_dict.treatment_doses && frm.fields_dict.treatment_doses.grid;
        if (grid) {
            const roles = frappe.user_roles || [];
            const is_pharmacist = roles.includes("Treatment Pharmacist");
            const is_system_manager = roles.includes("System Manager");
            const can_dispense = is_pharmacist || is_system_manager;

            grid.update_docfield_property("dispensed", "read_only", !can_dispense);
            if (is_pharmacist && !is_system_manager) {
                ["item", "medicine_name", "dose", "scheduled_date", "protocol_item", "schedule_version", "regimen_signature"].forEach((fieldname) => {
                    grid.update_docfield_property(fieldname, "read_only", 1);
                });
                grid.cannot_add_rows = true;
                grid.cannot_delete_rows = true;
            }
            grid.refresh();
        }
    },
});

frappe.ui.form.on("Recommendation Protocol Item", {
    item(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item) {
            ["item_name", "duration_days", "decision_sequence", "official_protocol_code", "treatment_type", "medicine_name", "number_of_doses", "dose_interval_days"].forEach((field) => {
                frappe.model.set_value(cdt, cdn, field, null);
            });
            frappe.model.set_value(cdt, cdn, "rate", 0);
            frappe.model.set_value(cdt, cdn, "first_dose_date", null);
            recalc_total(frm);
            return;
        }
        frappe.call({
            method: "state_treatment.utils.get_protocol_item_details",
            args: { item_code: row.item },
            callback(r) {
                if (!r.message || locals[cdt][cdn].item !== row.item) { return; }
                const d = r.message;
                ["item_name", "rate", "duration_days", "decision_sequence", "official_protocol_code", "treatment_type", "medicine_name", "number_of_doses", "dose_interval_days"].forEach((field) => {
                    frappe.model.set_value(cdt, cdn, field, d[field] || (field === "rate" ? 0 : null));
                });
                if (d.treatment_type !== "Medicine") {
                    frappe.model.set_value(cdt, cdn, "first_dose_date", null);
                }
                recalc_total(frm);
            },
        });
    },

    rate(frm) {
        recalc_total(frm);
    },

    protocol_items_remove(frm) {
        recalc_total(frm);
    },
});

function recalc_total(frm) {
    let total = 0.0;
    (frm.doc.protocol_items || []).forEach((row) => {
        total += flt(row.rate);
    });
    frm.set_value("total_amount", total);
}

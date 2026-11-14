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

        add_treatment_buttons(frm);
    },

    patient(frm) {
        fill_patient_fields(frm);
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

function fill_patient_fields(frm) {
    const patient = frm.doc.patient;
    frappe.call({
        method: "state_treatment.patient_link.get_patient_field_details",
        args: { patient: patient },
        callback(r) {
            // Ignore the answer if another patient was picked while the call was running.
            if (!r.message || frm.doc.patient !== patient) { return; }
            Object.entries(r.message.values).forEach(([fieldname, value]) => {
                frm.set_value(fieldname, value || null);
            });
            r.message.missing.forEach((fieldname) => {
                frappe.msgprint(__(
                    "The Patient doctype has no field {0}. Set the correct fieldname in State Treatment Settings.",
                    [fieldname]
                ));
            });
        },
    });
}

function recalc_total(frm) {
    let total = 0.0;
    (frm.doc.protocol_items || []).forEach((row) => {
        total += flt(row.rate);
    });
    frm.set_value("total_amount", total);
}

function add_treatment_buttons(frm) {
    frm.clear_custom_buttons();
    if (frm.is_new()) {
        return;
    }
    if (!["Approved for Disbursement", "Treatment Completed"].includes(frm.doc.status)) {
        return;
    }

    const roles = frappe.user_roles || [];
    const is_system_manager = roles.includes("System Manager");

    if (roles.includes("Medical Reviewer") || is_system_manager) {
        const pending = (frm.doc.protocol_items || []).filter(
            (row) => row.treatment_type === "Procedure" && !row.procedure_done
        );
        if (pending.length) {
            frm.add_custom_button(
                __("Mark Procedure Done"),
                () => open_procedure_dialog(frm, pending),
                __("Treatment Actions")
            );
        }
    }

    if (roles.includes("Treatment Pharmacist") || is_system_manager) {
        const doses = doses_to_dispense(frm.doc);
        if (doses.length) {
            frm.add_custom_button(
                __("Dispense Dose"),
                () => open_dispense_dialog(frm, doses),
                __("Treatment Actions")
            );
        }
    }

    if (roles.includes("General Manager") || is_system_manager) {
        if (frm.doc.status === "Approved for Disbursement" && treatment_is_finished(frm.doc)) {
            frm.add_custom_button(
                __("Close Treatment"),
                () => close_treatment(frm),
                __("Treatment Actions")
            );
        }
    }
}

function doses_to_dispense(doc) {
    // Only the latest schedule version can be dispensed; older versions are kept for history.
    const doses = doc.treatment_doses || [];
    const latest = {};
    doses.forEach((dose) => {
        const version = Number(dose.schedule_version) || 0;
        if (version > (latest[dose.protocol_item] || 0)) {
            latest[dose.protocol_item] = version;
        }
    });
    return doses
        .filter((dose) => !dose.dispensed && (Number(dose.schedule_version) || 0) === latest[dose.protocol_item])
        .sort((a, b) => (a.scheduled_date || "").localeCompare(b.scheduled_date || "") || a.idx - b.idx);
}

function open_procedure_dialog(frm, procedures) {
    if (frm.is_dirty()) {
        frappe.msgprint(__("Save the form before continuing."));
        return;
    }
    const options = procedures.map((row) => `${row.idx}. ${row.item_name || row.item}`);
    const dialog = new frappe.ui.Dialog({
        title: __("Mark Procedure Done"),
        fields: [{
            fieldname: "procedure",
            label: __("Procedure"),
            fieldtype: "Select",
            options: options.join("\n"),
            default: options[0],
            reqd: 1,
        }],
        primary_action_label: __("Confirm"),
        primary_action(values) {
            const row = procedures[options.indexOf(values.procedure)];
            dialog.hide();
            frappe.confirm(__("This cannot be undone. Continue?"), () => {
                run_treatment_action(
                    frm,
                    "state_treatment.actions.mark_procedure_done",
                    row.name,
                    __("Procedure marked as done.")
                );
            });
        },
    });
    dialog.show();
}

function open_dispense_dialog(frm, doses) {
    if (frm.is_dirty()) {
        frappe.msgprint(__("Save the form before continuing."));
        return;
    }
    const options = doses.map((dose) => (
        `${dose.idx}. ${dose.medicine_name || dose.item} - ${dose.dose} - ${frappe.format(dose.scheduled_date, { fieldtype: "Date" })}`
    ));
    const dialog = new frappe.ui.Dialog({
        title: __("Dispense Dose"),
        fields: [{
            fieldname: "dose",
            label: __("Dose"),
            fieldtype: "Select",
            options: options.join("\n"),
            default: options[0],
            reqd: 1,
        }],
        primary_action_label: __("Confirm"),
        primary_action(values) {
            const dose = doses[options.indexOf(values.dose)];
            dialog.hide();
            frappe.confirm(__("This cannot be undone. Continue?"), () => {
                run_treatment_action(
                    frm,
                    "state_treatment.actions.mark_dose_dispensed",
                    dose.name,
                    __("Dose marked as dispensed.")
                );
            });
        },
    });
    dialog.show();
}

function run_treatment_action(frm, method, row_name, success_message) {
    frappe.call({
        method: method,
        args: { recommendation: frm.doc.name, row_name: row_name },
        freeze: true,
        callback() {
            frappe.show_alert({ message: success_message, indicator: "green" });
            frm.reload_doc();
        },
    });
}

function treatment_is_finished(doc) {
    const rows = (doc.protocol_items || []).filter((row) => row.item);
    if (!rows.length || doses_to_dispense(doc).length) {
        return false;
    }
    return rows.every((row) => {
        if (row.treatment_type === "Procedure") {
            return Boolean(row.procedure_done);
        }
        if (row.treatment_type === "Medicine") {
            return (doc.treatment_doses || []).some((dose) => dose.protocol_item === row.name);
        }
        return false;
    });
}

function close_treatment(frm) {
    if (frm.is_dirty()) {
        frappe.msgprint(__("Save the form before continuing."));
        return;
    }
    frappe.confirm(__("This cannot be undone. Continue?"), () => {
        frappe.call({
            method: "state_treatment.actions.close_treatment",
            args: { recommendation: frm.doc.name },
            freeze: true,
            callback() {
                frappe.show_alert({ message: __("Treatment closed."), indicator: "green" });
                frm.reload_doc();
            },
        });
    });
}

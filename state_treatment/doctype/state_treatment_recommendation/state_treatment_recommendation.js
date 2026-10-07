frappe.ui.form.on("State Treatment Recommendation", {
    refresh(frm) {
        // nothing workflow-specific here; transitions render automatically
        if (frm.doc.docstatus === 0) {
            frm.set_df_property("status", "read_only", 1);
        }
    },
});

frappe.ui.form.on("Recommendation Protocol Item", {
    item(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item) {
            return;
        }
        // fetch name/duration/sequence + price (price can't use fetch_from
        // because it depends on the "نفقة الدولة" price list)
        frappe.call({
            method: "state_treatment.utils.get_protocol_item_details",
            args: { item_code: row.item },
            callback(r) {
                if (!r.message) { return; }
                const d = r.message;
                frappe.model.set_value(cdt, cdn, "item_name", d.item_name);
                frappe.model.set_value(cdt, cdn, "rate", d.price);
                frappe.model.set_value(cdt, cdn, "duration_days", d.duration_days || 0);
                frappe.model.set_value(cdt, cdn, "decision_sequence", d.decision_sequence || null);
                frappe.model.set_value(cdt, cdn, "official_protocol_code", d.official_protocol_code || null);
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

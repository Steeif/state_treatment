frappe.ui.form.on("Item", {
    refresh(frm) {
        update_protocol_code(frm);
        calculate_dose_interval(frm);
    },

    is_protocol(frm) {
        update_protocol_code(frm);
    },

    official_protocol_code(frm) {
        update_protocol_code(frm);
    },

    protocol_treatment_type(frm) {
        update_protocol_code(frm);
        calculate_dose_interval(frm);
    },

    protocol_serial(frm) {
        update_protocol_code(frm);
    },

    duration_days(frm) {
        calculate_dose_interval(frm);
    },

    number_of_doses(frm) {
        calculate_dose_interval(frm);
    },
});

function update_protocol_code(frm) {
    if (!frm.doc.is_protocol || !frm.doc.official_protocol_code || !frm.doc.protocol_serial
        || !["Medicine", "Procedure"].includes(frm.doc.protocol_treatment_type)) {
        if (frm.doc.internal_protocol_code) {
            frm.set_value("internal_protocol_code", "");
        }
        return;
    }

    const type_code = frm.doc.protocol_treatment_type === "Medicine" ? "MED" : "PROC";
    const serial = String(frm.doc.protocol_serial).padStart(5, "0");
    frm.set_value(
        "internal_protocol_code",
        `${frm.doc.official_protocol_code}-${type_code}-${serial}`,
    );
}

function calculate_dose_interval(frm) {
    if (frm.doc.protocol_treatment_type !== "Medicine") {
        return;
    }

    const duration = flt(frm.doc.duration_days);
    const doses = flt(frm.doc.number_of_doses);
    frm.set_value(
        "dose_interval_days",
        duration > 0 && doses > 0 ? Math.round((duration / doses) * 100) / 100 : 0,
    );
}

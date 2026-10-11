frappe.ui.form.on("Administrative Letter", {
	setup(frm) {
		frm.add_fetch("recommendation", "recommendation_no", "request_no");
	},
});

// A Communication with a follow-up can end it here: this also closes its Open ToDos.
frappe.ui.form.on("Communication", {
	refresh(frm) {
		if (frm.doc.__islocal || !frm.doc.follow_up) return;
		frm.add_custom_button(__("End Follow Up"), () => {
			frappe.call({
				method: "rigpl_erpnext.rigpl_erpnext.validations.communication.end_follow_up",
				args: { communication: frm.doc.name },
				freeze: true,
				callback() {
					frm.reload_doc();
				},
			});
		});
	},
});

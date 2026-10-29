// Follow-up ToDos of a Communication (#150): closing asks "Done" or "Remind me later".
frappe.ui.form.on("ToDo", {
	refresh(frm) {
		frm._saved_status = frm.doc.status;
		if (!is_open_follow_up(frm)) return;
		frm.remove_custom_button(__("Close"));
		frm.add_custom_button(__("Close Follow Up"), () => close_follow_up_dialog(frm, "Closed"));
	},
	status(frm) {
		if (!["Closed", "Cancelled"].includes(frm.doc.status)) return;
		if (frm.doc.__islocal || frm.doc.reference_type !== "Communication") return;
		if (["Closed", "Cancelled"].includes(frm._saved_status)) return;
		const status = frm.doc.status;
		frm.set_value("status", frm._saved_status);
		close_follow_up_dialog(frm, status);
	},
});

function is_open_follow_up(frm) {
	return !frm.doc.__islocal && frm.doc.reference_type === "Communication"
		&& !["Closed", "Cancelled"].includes(frm.doc.status);
}

function close_follow_up_dialog(frm, status) {
	const dialog = new frappe.ui.Dialog({
		title: __("Close Follow Up"),
		fields: [
			{
				fieldname: "action", fieldtype: "Select", label: __("Action"), reqd: 1,
				options: [__("Done"), __("Remind me later")].join("\n"), default: __("Done"),
			},
			{
				fieldname: "next_action_date", fieldtype: "Datetime", label: __("Next Action Date"),
				depends_on: `eval:doc.action=="${__("Remind me later")}"`,
				mandatory_depends_on: `eval:doc.action=="${__("Remind me later")}"`,
			},
		],
		primary_action_label: __("Close"),
		primary_action(values) {
			frappe.call({
				method: "rigpl_erpnext.rigpl_erpnext.validations.todo.close_follow_up",
				args: {
					todo: frm.doc.name,
					status: status,
					next_action_date: values.action === __("Remind me later") ? values.next_action_date : null,
				},
				freeze: true,
				callback() {
					dialog.hide();
					frm.reload_doc();
				},
			});
		},
	});
	dialog.show();
}

// Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt


frappe.ui.form.on('BOM Template RIGPL', {
	onload: function(frm){
		frm.set_query("item_template", function(doc) {
			return {
				"filters": {
					"has_variants": 1,
					"disabled": 0,
					"include_item_in_manufacturing": 1
				}
			};
		});
	},
	refresh: function(frm){
		frm.add_custom_button(__("BOM Template Guide"), function() {
			frappe.call({method: "rigpl_erpnext.utils.guide_utils.get_user_guide", args: {guide: "bom_templates"}}).then(r => {
				const dialog = new frappe.ui.Dialog({title: __("How to make a BOM Template"), size: "large",
					fields: [{fieldtype: "HTML", fieldname: "guide"}]});
				dialog.fields_dict.guide.$wrapper.html(r.message);
				dialog.show();
			});
		}, __("Help"));
		if (frm.is_new()) return;
		if (!frm.doc.disabled && frm.perm[0] && frm.perm[0].write) {
			frm.add_custom_button(__("Disable Similar Templates"), () => show_similar_templates(frm));
		}
		const count = (docstatus) => frappe.db.count("Process Sheet", {filters: {bom_template: frm.doc.name, docstatus: docstatus}});
		Promise.all([count(1), frm.doc.disabled ? count(0) : 0]).then(([submitted, drafts]) => {
			let html = `<a class="bt-ps-link">${__("Submitted Process Sheets: {0}", [submitted])}</a>`;
			if (drafts) {
				html += ` <span class="text-danger">${__("Draft Process Sheets on this disabled template: {0}", [drafts])}</span>`;
			}
			frm.dashboard.set_headline(html, drafts ? "red" : "blue");
			frm.layout.message.find(".bt-ps-link").on("click", () => {
				frappe.set_route("List", "Process Sheet", {bom_template: frm.doc.name, docstatus: 1});
			});
		});
	},
});

function show_similar_templates(frm) {
	// The active templates with the same operations as this one, to disable and point to it (#164)
	const esc = frappe.utils.escape_html;
	frappe.call({
		method: "rigpl_erpnext.manufacturing_rigpl.utils.bom_template_merge_utils.get_similar_templates",
		args: {bom_template: frm.doc.name},
		freeze: true,
		freeze_message: __("Checking the items of the similar templates"),
	}).then(r => {
		const rows = r.message || [];
		if (!rows.length) {
			frappe.msgprint(__("No active template has the same operations as {0}.", [frm.doc.name]));
			return;
		}
		let html = `<p>${__("Exact: the same work. Almost: only the numbers in the rules differ. Similar: the same operations. The merge check replays the items of the last 2 years with this template.")}</p>
			<table class="table table-bordered table-condensed"><thead><tr><th></th><th>${__("Template")}</th><th>${__("Match")}</th>
			<th>${__("PS (2 years)")}</th><th>${__("Differences")}</th><th>${__("Merge check")}</th></tr></thead><tbody>`;
		rows.forEach(d => {
			const check = d.merge_failures.length
				? `<span class="text-danger">${__("{0} of {1} items differ", [d.merge_failures.length, d.items_checked])}</span><br>`
					+ d.merge_failures.slice(0, 5).map(f => `${esc(f.item)}: ${f.differences.map(esc).join("; ")}`).join("<br>")
				: `<span class="text-success">${__("{0} items checked, 0 differ", [d.items_checked])}</span>`;
			html += `<tr><td><input type="checkbox" class="bt-similar" data-name="${esc(d.template)}"></td>
				<td><a href="/app/bom-template-rigpl/${encodeURIComponent(d.template)}">${esc(d.template)}</a><br><small>${esc(d.title || "")}</small></td>
				<td>${esc(__(d.kind))}</td><td>${d.process_sheets}</td>
				<td><small>${d.differences.map(esc).join("<br>") || __("None")}</small></td><td><small>${check}</small></td></tr>`;
		});
		html += "</tbody></table>";
		const dialog = new frappe.ui.Dialog({
			title: __("Disable Similar Templates"),
			size: "extra-large",
			fields: [{fieldtype: "HTML", fieldname: "similar"}],
			primary_action_label: __("Disable Selected"),
			primary_action: () => {
				const names = dialog.$wrapper.find(".bt-similar:checked").map((i, el) => $(el).attr("data-name")).get();
				if (!names.length) return;
				const risky = rows.filter(d => names.includes(d.template) && (d.differences.length || d.merge_failures.length));
				const disable = () => frappe.call({
					method: "rigpl_erpnext.manufacturing_rigpl.utils.bom_template_merge_utils.disable_similar_templates",
					args: {bom_template: frm.doc.name, templates: names},
				}).then(res => {
					dialog.hide();
					frappe.show_alert({message: __("Disabled: {0}", [(res.message || []).join(", ")]), indicator: "green"});
				});
				if (risky.length) {
					frappe.confirm(__("{0} have differences from {1}. Their items may get other operations, RM or WIP. Disable them anyway?",
						[risky.map(d => d.template).join(", "), frm.doc.name]), disable);
				} else {
					disable();
				}
			},
		});
		dialog.fields_dict.similar.$wrapper.html(html);
		dialog.show();
	});
}


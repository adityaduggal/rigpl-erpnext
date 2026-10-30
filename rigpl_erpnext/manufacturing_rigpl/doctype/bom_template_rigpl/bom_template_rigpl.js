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
		if (frm.is_new()) return;
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
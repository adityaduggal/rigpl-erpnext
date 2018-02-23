// Copyright (c) 2018, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Book Shipment', {
	refresh: function(frm) {

	}
});

frappe.ui.form.on("Shipment Package Details", "package_weight", function(frm, cdt, cdn) {
// code for calculate total and set on parent field.
	weight = 0;
	packs = 0;
	uom = "";
	$.each(frm.doc.shipment_package_details || [], function(i, d) {
		weight += flt(d.package_weight);
		packs += 1
		uom = d.weight_uom
	});
	frm.set_value("total_weight", weight);
	frm.set_value("weight_uom", uom);
	frm.set_value("total_handling_units", packs);
});
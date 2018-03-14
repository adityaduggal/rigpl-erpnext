// Copyright (c) 2017, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Carrier Tracking', {
	refresh: function(frm) {

	},
	onload: function(frm){
		frm.set_query("carrier_name", function(doc) {
			return {
				"filters": {
					"track_on_shipway": 1
				}
			};
		});
		frm.set_query("from_address", function(doc) {
			return {
				"filters":{
					"is_your_company_address": 1,
				}
			};
		});
		frm.set_query("receiver_document", function(doc) {
			return {
				"filters": [
					['name', 'in', ['Customer']]
				]
			};
		});
		frm.set_query("carrier_name", function(doc) {
			return {
				"filters":{
					"fedex_credentials": 1,
				}
			};
		});
		frm.set_query("document", function(doc) {
			return {
				"filters": [
					['name', 'in', ['Sales Invoice']]
				]
			};
		});
		frm.set_query("shipment_package_details", "weight_uom", function(doc, cdt, cdn) {
			return {
				"filters": [
					['name', 'in', ['Kg']]
				]
			};
		});
	},
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
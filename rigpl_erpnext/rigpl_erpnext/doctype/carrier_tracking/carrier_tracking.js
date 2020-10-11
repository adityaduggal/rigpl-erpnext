// Copyright (c) 2017, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Carrier Tracking', {
	refresh: function(frm) {

	},
	onload: function(frm){
		frm.set_query("carrier_name", function(doc) {
            return{
                query: "rigpl_erpnext.rigpl_erpnext.doctype.carrier_tracking.carrier_tracking.carrier_name_query"
            }
		});
		frm.set_query("from_address", function(doc) {
		    if (frm.is_inward !== 1){
                return {
                    "filters":{
                        "is_your_company_address": 1,
                        "disabled": 0
                    }
                };
		    } else {
		        if (!frm.doc.receiver_document || !frm.doc.receiver_name){
		            frappe.throw(__('Please first select Receiver Document and Receiver Document Name before setting address'));
		        }
                return {
                    query: 'frappe.contacts.doctype.address.address.address_query',
                    filters: {
                        link_doctype: frm.doc.receiver_document,
                        link_name: frm.doc.receiver_name
                    }
                };
		    }
		});
		frm.set_query("to_address", function(doc) {
		    if (frm.is_inward !== 1){
		        if (!frm.doc.receiver_document || !frm.doc.receiver_name){
		            frappe.throw(__('Please first select Receiver Document and Receiver Document Name before setting address'));
		        }
                return {
                    query: 'frappe.contacts.doctype.address.address.address_query',
                    filters: {
                        link_doctype: frm.doc.receiver_document,
                        link_name: frm.doc.receiver_name
                    }
                };
		    } else {
                return {
                    "filters":{
                        "is_your_company_address": 1,
                        "disabled": 0
                    }
                };
		    }
		});
		frm.set_query("receiver_document", function(doc) {
			return {
				"filters": [
					['name', 'in', ['Customer', 'Supplier', 'Employee', 'Sales Partner', 'Company']]
				]
			};
		});
		frm.set_query("document", function(doc) {
			return {
				"filters": [
					['name', 'in', ['Sales Invoice', 'Purchase Order', 'Customer', 'Supplier', 'Company', 'Sales Partner', 'Employee']]
				]
			};
		});
		frm.set_query("contact_person", function(doc){
            if (!frm.doc.receiver_document || !frm.doc.receiver_name){
                frappe.throw(__('Please first select Receiver Document and Receiver Document Name before setting Contact'));
            }
            return {
                query: 'frappe.contacts.doctype.contact.contact.contact_query',
                filters: {
                    link_doctype: frm.doc.receiver_document,
                    link_name: frm.doc.receiver_name
                }
            };
		});
		frm.set_query("weight_uom", "shipment_package_details", function(doc, dt, dn) {
			return {
				"filters": [
					['name', 'in', ['Kg']]
				]
			};
		});
	},
});

frappe.ui.form.on("Shipment Package Details", {
    package_weight: function(frm, dt, dn){
        cur_frm.cscript.update_total_weight(frm.doc)
        cur_frm.cscript.update_total_pkgs(frm.doc)
    }
});

frappe.ui.form.on("Carrier Tracking", {
    document: function(frm){
        frm.doc.receiver_document = frm.doc.document;
        frm.doc.to_address = '';
        frm.doc.document_name = '';
        frm.doc.receiver_name = '';
        frm.doc.contact_person = '';
        frm.refresh_fields();
    },

    document_name: function(frm){
        frm.doc.receiver_name = frm.doc.document_name;
        frm.doc.to_address = '';
        frm.doc.contact_person = '';
        frm.refresh_fields();
    }
})

frappe.ui.form.on("Carrier Tracking", "is_inward", function(frm) {
// code for calculate total and set on parent field.
    frm.doc.from_address = '';
    frm.doc.to_address = '';
    frm.refresh_fields();
	if (frm.doc.is_inward === 1){
		frm.set_query("from_address", function(doc) {
            if (!frm.doc.receiver_document || !frm.doc.receiver_name){
                frappe.throw(__('Please first select Receiver Document and Receiver Document Name before setting address'));
            }
			return {
				query: 'frappe.contacts.doctype.address.address.address_query',
				filters: {
					link_doctype: frm.doc.receiver_document,
					link_name: frm.doc.receiver_name
				}
			};
		});
		frm.set_query("to_address", function(doc) {
			return {
				"filters":{
					"is_your_company_address": 1,
					"disabled": 0
				}
			};
		});
	} else {
		frm.set_query("from_address", function(doc) {
			return {
				"filters":{
					"is_your_company_address": 1,
					"disabled": 0
				}
			};
		});
		frm.set_query("to_address", function(doc) {
            if (!frm.doc.receiver_document || !frm.doc.receiver_name){
                frappe.throw(__('Please first select Receiver Document and Receiver Document Name before setting address'));
            }
			return {
				query: 'frappe.contacts.doctype.address.address.address_query',
				filters: {
					link_doctype: frm.doc.receiver_document,
					link_name: frm.doc.receiver_name
				}
			};
		});
	}
});

cur_frm.cscript.update_total_weight = function(doc){
    var total_wt = 0;
    var wt_uom = "";
    var packages = doc.shipment_package_details || [];
    for (var i in packages){
        total_wt += flt(packages[i].package_weight, 3);
        wt_uom = packages[i].weight_uom
    }
    var doc = locals[doc.doctype][doc.name];
	doc.total_weight = total_wt;
	doc.weight_uom = wt_uom;
	refresh_many(['total_weight','weight_uom']);
}

cur_frm.cscript.update_total_pkgs = function(doc){
    var total_pkgs = 0;
    var packages = doc.shipment_package_details || [];
    for (var i in packages){
        total_pkgs += 1;
    }
    var doc = locals[doc.doctype][doc.name];
	doc.total_handling_units = total_pkgs;
	refresh_many(['total_handling_units']);
}

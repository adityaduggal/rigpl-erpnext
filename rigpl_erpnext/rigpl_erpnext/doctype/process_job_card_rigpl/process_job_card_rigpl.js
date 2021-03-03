// Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on('Process Job Card RIGPL', {
	onload: function(frm){
		frm.set_query("employee", function(doc) {
			return {
				"filters": {
					"status": 'Active'
				}
			};
		});
		frm.set_query("process_sheet", function(doc) {
			return {
				"filters": [
					['status', 'in', ['In Progress', 'Submitted']]
				]
			};
		});
	},
	refresh: function(frm, dt, dn){
	    frm.set_query("salvage_warehouse", "time_logs", function(doc){
	        return {
	            filters: {
	                warehouse_type: "Recoverable Stock",
	                is_group: 0,
	                disabled: 0
	            }
	        }
	    });
	},
	process_sheet: function(frm) {
		if (frm.doc.process_sheet) {
			frappe.call({
				doc: frm.doc,
				method: "get_items_from_process_sheet",
				freeze: true,
				callback: function(r) {
					if (!r.exc) {
						frm.refresh_fields();
					}
				}
			});
		}
	}
});

frappe.ui.form.on('Process Sheet Items', {
    source_warehouse: function(doc){
        console.log("Hello")
    },
});


frappe.ui.form.on('Job Card Time Log', {
	time_logs_remove: function(frm) {
		 cur_frm.cscript.update_total_mins(frm.doc);
		 cur_frm.cscript.update_total_completed_qty(frm.doc);
		 cur_frm.cscript.update_total_rejected_qty(frm.doc);
	},
    rejected_qty: function(frm, dt, dn){
        cur_frm.cscript.update_total_rejected_qty(frm.doc);
    },
    salvage_qty: function(frm, dt, dn){
        cur_frm.cscript.update_total_rejected_qty(frm.doc);
    },
    completed_qty: function(frm, dt, dn){
        cur_frm.cscript.update_total_completed_qty(frm.doc);
    },
    from_time: function(frm, dt, dn){
        var child = locals[dt][dn];
        var diff = Math.floor((moment(child.to_time).diff(moment(child.from_time),"seconds"))/60);
        if (child.from_time > child.to_time){
            frappe.throw("From Time cannot be Greater than To Time")
        } else {
            frappe.model.set_value(dt, dn, "time_in_mins", diff);
        }
        cur_frm.cscript.update_total_mins(frm.doc);
    },
    to_time: function(frm, dt, dn){
        var child = locals[dt][dn];
        var diff = Math.floor((moment(child.to_time).diff(moment(child.from_time),"seconds"))/60);
        if (child.from_time > child.to_time){
            frappe.throw("From Time cannot be Greater than To Time")
        } else {
            frappe.model.set_value(dt, dn, "time_in_mins", diff);
        }
        cur_frm.cscript.update_total_mins(frm.doc);
    },
});

cur_frm.cscript.update_total_completed_qty = function(doc) {
    var tcq =0.0;
	var time_logs = doc.time_logs || [];
	for(var i in time_logs) {
		tcq += flt(time_logs[i].completed_qty, precision("completed_qty", time_logs[i]));
	}
	var doc = locals[doc.doctype][doc.name];
	doc.total_completed_qty = tcq;
	refresh_many(['total_completed_qty','total_time_in_mins']);
}

cur_frm.cscript.update_total_mins = function(doc) {
    var time_in_mins =0.0;
	var time_logs = doc.time_logs || [];
	for(var i in time_logs) {
		time_in_mins += flt(time_logs[i].time_in_mins, precision("time_in_mins", time_logs[i]));
	}
	var doc = locals[doc.doctype][doc.name];
	doc.total_time_in_mins = time_in_mins;
	refresh_many(['total_completed_qty','total_time_in_mins']);
}

cur_frm.cscript.update_total_rejected_qty = function(doc) {
    var tcr =0.0;
	var time_logs = doc.time_logs || [];
	for(var i in time_logs) {
		tcr += flt(flt(time_logs[i].rejected_qty) + flt(time_logs[i].salvage_qty),
		    precision("rejected_qty", time_logs[i]));
	}
	var doc = locals[doc.doctype][doc.name];
	doc.total_rejected_qty = tcr;
	refresh_many(['total_rejected_qty','total_time_in_mins']);
}
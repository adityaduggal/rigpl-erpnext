// Copyright (c) 2019, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

//cur_frm.cscript.refresh = function(doc) {
//	cur_frm.disable_save();
//}
frappe.ui.form.on('IndiaMart Pull Leads', {
	refresh: function(frm) {
		frm.disable_save();
	}
});
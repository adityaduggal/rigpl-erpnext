cur_frm.cscript.custom_validate = function(doc, dt, dn) {
    if (doc.docstatus == 0){
		if (doc.requirement>0) && (doc.requirement % 10000 ===0) {
			msgprint ("Lead shoule be saved");
		else{
			validate = false;
			msgprint("Lead Requirement should be a multiple of 10,000");
			}
		}
	}
}

cur_frm.cscript.custom_validate = function(doc, dt, dn) {
    if (doc.docstatus == 0){
		if (doc.requirement>0){
			validate = false;
			msgprint ("Lead not saved");
		}
	}
}

cur_frm.add_fetch('customer','state_tax_type','charge');
cur_frm.add_fetch('customer','tin_no','tin_no');
cur_frm.add_fetch('customer','excise_number','excise_number');
cur_frm.add_fetch('customer','payment_terms','payment_terms');
cur_frm.add_fetch('item_code','cetsh_number','cetsh_number');
cur_frm.add_fetch('customer','letter_head','letter_head');
cur_frm.add_fetch('address','address_title','shipping_address_title');

cur_frm.cscript.custom_customer = function() {
    cur_frm.script_manager.trigger("charge");
}

cur_frm.cscript.custom_validate = function(doc, dt, dn) {
    if (doc.docstatus == 0){
		if (wn.datetime.get_day_diff(new Date(), wn.datetime.str_to_obj(doc.transaction_date)) > 0 && doc.order_type == "Sales") {
			validated = false;
			msgprint("Sales Order Date cannot be a past date"); // or any other message you want..
		}
	}	
}

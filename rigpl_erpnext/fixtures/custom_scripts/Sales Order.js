cur_frm.add_fetch('customer','payment_terms','payment_terms');
cur_frm.add_fetch('customer','letter_head','letter_head');
cur_frm.add_fetch('shipping_address_name','address_title','shipping_address_title');
cur_frm.add_fetch('shipping_address_name','tin_no','shipping_tin_no');
cur_frm.add_fetch('shipping_address_name','excise_no','shipping_excise_no');
cur_frm.add_fetch('customer_address','excise_no','excise_number');
cur_frm.add_fetch('customer_address','tin_no','tin_no');
cur_frm.add_fetch('taxes_and_charges','letter_head','letter_head');

cur_frm.cscript.custom_validate = function(doc, dt, dn) {
    if (doc.docstatus == 0){
		if (frappe.datetime.get_day_diff(new Date(), frappe.datetime.str_to_obj(doc.transaction_date)) > 0 && doc.order_type == "Sales") {
			validated = false;
			msgprint("Sales Order Date cannot be a past date"); // or any other message you want..
		}
	}	
};
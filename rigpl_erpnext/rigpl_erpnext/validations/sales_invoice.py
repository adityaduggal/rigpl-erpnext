# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe, re
from frappe import msgprint

def validate(doc,method):
	update_fields(doc,method)
	check_gst_rules(doc,method)
	check_delivery_note_rule(doc,method)
	validate_carrier_tracking(doc,method)
	validate_price_list(doc,method)

def on_submit(doc,method):
	create_new_carrier_track(doc,method)
	new_brc_tracking(doc,method)
	update_shipment_booking(doc, method)
	user = frappe.session.user
	query = """SELECT role from `tabUserRole` where parent = '%s' """ %user
	roles = frappe.db.sql(query, as_list=1)
	
	for d in doc.items:
		if d.sales_order is None and d.delivery_note is None and doc.ignore_pricing_rule == 1:
			is_stock_item = frappe.db.get_value('Item', d.item_code, 'is_stock_item')
			if is_stock_item == 1:
				if any("System Manager" in s  for s in roles):
					pass
				else:
					frappe.throw("You are not Authorised to Submit this Transaction \
					ask a System Manager")
		if d.sales_order is not None:
			so = frappe.get_doc("Sales Order", d.sales_order)
			if so.track_trial == 1:
				dnd = frappe.get_doc("Delivery Note Item", d.dn_detail)
				sod = dnd.so_detail
				query = """SELECT tt.name FROM `tabTrial Tracking` tt where \
					tt.prevdoc_detail_docname = '%s' """ % sod
				name = frappe.db.sql(query, as_list=1)
				if name:
					tt = frappe.get_doc("Trial Tracking", name[0][0])
					frappe.db.set(tt, 'invoice_no', doc.name)

def on_cancel(doc,method):
	#Get Carrier Tracking
	ctrack = frappe.db.sql("""SELECT name FROM `tabCarrier Tracking` 
		WHERE document = 'Sales Invoice' 
		AND document_name = '%s'"""%(doc.name), as_list=1)
	if ctrack:
		ctrack_doc = frappe.get_doc("Carrier Tracking", ctrack[0][0])
		if ctrack_doc.docstatus == 1:
			frappe.db.set(ctrack_doc, 'docstatus', 2)

	for d in doc.items:
		if d.sales_order is not None:
			so = frappe.get_doc("Sales Order", d.sales_order)
			if so.track_trial == 1:
				dnd = frappe.get_doc("Delivery Note Item", d.dn_detail)
				sod = dnd.so_detail
				query = """SELECT tt.name FROM `tabTrial Tracking` tt where \
					tt.prevdoc_detail_docname = '%s' """ % sod
				name = frappe.db.sql(query, as_list=1)
				if name:
					tt = frappe.get_doc("Trial Tracking", name[0][0])
					frappe.db.set(tt, 'invoice_no', None)

def validate_price_list(doc,method):
	for d in doc.items:
		if d.so_detail:
			sod_doc = frappe.get_doc("Sales Order Item", d.so_detail)
			d.price_list = sod_doc.price_list 
		else:
			if d.price_list:
				get_pl_rate(d.price_list, d)
			else:
				d.price_list = doc.selling_price_list
				get_pl_rate(d.price_list, d)

def get_pl_rate(price_list, row):
	pl_doc = frappe.get_doc("Price List", row.price_list)
	it_doc = frappe.get_doc("Item", row.item_code)
	if pl_doc.disable_so == 1 and it_doc.is_stock_item == 1:
		frappe.throw("Sales Invoices for {} are Blocked without prior \
			Sales Order".format(row.price_list))
	else:
		item_price = frappe.db.sql("""SELECT price_list_rate, currency FROM `tabItem Price`
			WHERE price_list = '%s' AND selling = 1 
			AND item_code = '%s'"""%(row.price_list, row.item_code), as_list=1)
		if item_price:
			if row.price_list_rate != item_price[0][0] and doc.currency == item_price[0][1]:
				frappe.throw("Item: {} in Row# {} does not match with Price List Rate\
					of {}. Reload the Item".format(row.item_code, row.idx, item_price[0][0]))

def check_delivery_note_rule(doc,method):
	'''
	1. No Sales Invoice without Delivery Note to be mentioned without UPDATE stock, basically \
		above rule is to ensure that if a DN is not made then STOCK is updated via SI
	2. No Partial DN to be ALLOWED to be BILL, this is because if a customer's DN is for 100pcs of
		one item and we send 50pcs then balance 50pcs he can deny especially for Special Items its
		a problem
	3. Also ensure that if there are 5 items in DN then all 5 items are in the SI with equal quantities
	4. Remove the Trial Rule which means NO INVOICING with TT SUBMITTED should be REMOVED.
	5. Disallow making a Sales Invoice for Items without SO but only DN, that is you make DN \
		without SO and then make INVOICE is not POSSIBLE, means you SO => DN => SI or only SI also
		denies SO => SI
	'''
	dn_dict = frappe._dict()
	list_of_dn_dict = []
	
	for d in doc.items:
		#Stock Items without DN would need Update Stock Check
		if d.delivery_note is None:
			item_doc = frappe.get_doc('Item', d.item_code)
			if item_doc.is_stock_item == 1 and doc.update_stock != 1:
				frappe.throw(("Item Code {0} in Row # {1} is Stock Item \
					without any DN so please check Update Stock Button\
					").format(d.item_code, d.idx))

		if d.dn_detail not in list_of_dn_dict and d.delivery_note is not None:

			dn_dict['dn'] = d.delivery_note
			dn_dict['dn_detail'] = d.dn_detail
			dn_dict['item_code'] = d.item_code
			list_of_dn_dict.append(dn_dict.copy())
		#With SO DN is mandatory
		if d.sales_order is not None and d.delivery_note is None:
			#Rule no.5 in the above description for disallow SO=>SI no skipping DN
			frappe.throw(("""Error in Row# {0} has SO# {1} but there is no DN.
			Hence making of Invoice is DENIED""").format(d.idx, d.sales_order))
		#With DN SO is mandatory
		if d.delivery_note is not None and d.sales_order is None:
			frappe.throw(("""Error in Row# {0} has DN# {1} but there is no SO.
			Hence making of Invoice is DENIED""").format(d.idx, d.delivery_note))
		#For DN items quantities should be same
		if d.delivery_note is not None:
			dn_qty = frappe.db.get_value ('Delivery Note Item', d.dn_detail, 'qty')
			if dn_qty != d.qty:
				frappe.throw(("Invoice Qty should be equal to DN quantity of \
					{0} at Row # {1}").format(dn_qty, d.idx))
	if list_of_dn_dict:
		unique_dn = {v['dn']:v for v in list_of_dn_dict}.values()
		for dn in unique_dn:
			dn_doc = frappe.get_doc('Delivery Note', dn.dn)
			for d in dn_doc.items:
				if not any (x['dn_detail'] == d.name for x in list_of_dn_dict):
					frappe.throw(("Item No: {0} with Item Code: {1} in DN# {2} \
						is not mentioned in SI# {3}").format(d.idx, d.item_code, \
						dn_doc.name, doc.name))

def check_gst_rules(doc,method):
	series_template = frappe.db.get_value("Sales Taxes and Charges Template", \
		doc.taxes_and_charges ,"series")
		
	#Check series of Tax with the Series Selected for Invoice
	if series_template != doc.naming_series[:len(series_template)] \
		and series_template != doc.name[:len(series_template)]:
		frappe.throw(("Selected Tax Template {0} Not Allowed since Series Selected {1} and \
			Invoice number {2} don't match with the Selected Template").format( \
			doc.taxes_and_charges, doc.naming_series, doc.name))
	

def update_fields(doc,method):
	c_form_tax =frappe.db.get_value("Sales Taxes and Charges Template", doc.taxes_and_charges , \
		"c_form_applicable")
	letter_head_tax = frappe.db.get_value("Sales Taxes and Charges Template", \
		doc.taxes_and_charges, "letter_head")
	
	doc.c_form_applicable = c_form_tax
	doc.letter_head = letter_head_tax
	if frappe.db.get_value("Transporters", doc.transporters, "fedex_credentials") == 1:
		ctrack = frappe.db.sql("""SELECT name FROM `tabCarrier Tracking` 
			WHERE document = 'Sales Invoice' AND document_name = '%s'"""%(doc.name), as_list=1)
		if ctrack:
			doc.lr_no = frappe.db.get_value("Carrier Tracking",ctrack[0][0] )
	else:
		doc.lr_no = re.sub('[^A-Za-z0-9]+', '', str(doc.lr_no))

def validate_carrier_tracking(doc,method):
	tracked_transporter = is_tracked_transporter(doc,method)
	if tracked_transporter == 1:

		frappe.msgprint(("{0} is Tracked Automatically all Shipment Data for LR No {1} \
				would be automatically updated in Carrier Tracking Document").format(
				frappe.get_desk_link('Transporters', doc.transporters), doc.lr_no))
	return tracked_transporter

def create_new_carrier_track(doc,method):
	#If SI is from Cancelled Doc then update the Existing Carrier Track
	is_tracked = is_tracked_transporter(doc,method)
	if is_tracked == 1:
		if doc.amended_from:
			existing_track = check_existing_track(doc.doctype, doc.amended_from, doc.lr_no)
			if existing_track:
				exist_track = frappe.get_doc("Carrier Tracking", existing_track[0][0])
				if exist_track.docstatus == 0:
					exist_track.awb_number = doc.lr_no
					exist_track.receiver_name = doc.customer
					exist_track.document_name = doc.name
					exist_track.carrier_name = doc.transporters
					exist_track.flags.ignore_permissions = True
					exist_track.save()
					frappe.msgprint(("Updated {0}").format(frappe.get_desk_link\
						('Carrier Tracking', exist_track.name)))
				elif exist_track.docstatus == 1:
					frappe.throw("Carrier Tracking {} is Submitted hence \
						cannot Proceed".format(exist_track.name))
				else:
					new_ctrack = frappe.copy_doc(exist_track)
					new_ctrack.amended_from = exist_track.name
					new_ctrack.document_name = doc.name
					new_ctrack.insert()
					frappe.msgprint(("Added New {0}").format(frappe.get_desk_link\
						('Carrier Tracking', new_ctrack.name)))
			else:
				create_new_ship_track(doc)

		elif check_existing_track(doc.doctype, doc.name, doc.lr_no) is None:
			#Dont create a new Tracker if already exists
			create_new_ship_track(doc)

def create_new_ship_track(si_doc):
	track = frappe.new_doc("Carrier Tracking")
	track.carrier_name = si_doc.transporters
	track.awb_number = si_doc.lr_no
	track.receiver_document = "Customer"
	track.receiver_name = si_doc.customer
	track.document = "Sales Invoice"
	track.document_name = si_doc.name
	track.flags.ignore_permissions = True
	track.insert()
	frappe.msgprint(("Created New {0}").format(frappe.get_desk_link('Carrier Tracking', track.name)))

def check_existing_track(doctype, docname, awb_no):
	exists = frappe.db.sql("""SELECT name FROM `tabCarrier Tracking` WHERE document = '%s' AND 
		document_name = '%s' AND awb_number = '%s'""" %(doctype, docname, awb_no))
	if exists:
		return exists

def is_tracked_transporter(doc,method):
	ttrans = frappe.get_value ("Transporters", doc.transporters, "track_on_shipway")
	return ttrans

def new_brc_tracking(doc,method):
	#If SI is from Cancelled DOC then UPDATE the details of same in BRC
	stct_doc = frappe.get_doc("Sales Taxes and Charges Template", doc.taxes_and_charges)
	add_doc = frappe.get_doc("Address", doc.shipping_address_name)
	if stct_doc.is_export == 1 and add_doc.country != "India":
		if doc.amended_from:
			is_exist = frappe.db.sql("""SELECT name FROM `tabBRC MEIS Tracking` WHERE reference_name = '%s'
				""" %(doc.amended_from), as_list=1)
			if not is_exist:
				create_new_brc_tracking(doc,method)
			else:
				exist_brc = frappe.get_doc("BRC MEIS Tracking", is_exist[0][0])
				exist_brc.reference_name = doc.name
				exist_brc.flags.ignore_permissions = True
				exist_brc.save()
				frappe.msgprint(("Updated {0}").format(frappe.get_desk_link('BRC MEIS Tracking', exist_brc.name)))
		else:
			is_exist = frappe.db.sql("""SELECT name FROM `tabBRC MEIS Tracking` WHERE reference_name = '%s'
				""" %(doc.name), as_list=1)
			if not is_exist:
				create_new_brc_tracking(doc,method)


def create_new_brc_tracking(doc,method):
	brc_doc = frappe.new_doc("BRC MEIS Tracking")
	brc_doc.flags.ignore_permissions = True
	brc_doc.export_or_import = 'Export'
	brc_doc.reference_doctype = doc.doctype
	brc_doc.reference_name = doc.name
	brc_doc.insert()
	frappe.msgprint(("Created New {0}").format(frappe.get_desk_link('BRC MEIS Tracking', brc_doc.name)))

def update_shipment_booking(doc, method):
	if doc.amended_from:
		bk_ship = frappe.db.sql("""SELECT name FROM `tabCarrier Tracking`  
			WHERE docstatus != 2 AND document = 'Sales Invoice'
			AND document_name = '%s'"""%(doc.amended_from), as_list=1)
		for bks in bk_ship:
			frappe.db.set_value("Carrier Tracking", bks[0], "document_name", doc.name)

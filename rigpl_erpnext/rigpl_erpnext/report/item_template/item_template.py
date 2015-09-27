# Copyright (c) 2013, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def execute(filters=None):
	if not filters: filters = {}
	columns = get_columns()
	data = get_items(filters)
	
	return columns, data
	
def get_columns():
	return[
		"Item:Link/Item:300", "# Variants:Int:50","Is RM::50","BM::60", "Brand::100", "Quality::150",
		"SPL::100", "TT::300", "D1_MM::100", "D1_INCH::100", "W1_MM::100",
		"W1_INCH::100", "L1_MM::100", "L1_INCH::100"
	]

def get_items(filters):
	#List of fields to be fetched in the report
	attributes = ['Is RM', 'Base Material', 'Brand', '%Quality', 'Special Treatment',
		'Tool Type', 'd1_mm', 'd1_inch', 'w1_mm', 'w1_inch', 'l1_mm', 'l1_inch']
	
	float_fields = ['d1_mm', 'w1_mm', 'l1_mm']
	linked_fields = ['d1_inch', 'w1_inch', 'l1_inch']
	
	################################################################################################
	#TODO: List the range of Float fields and also for linked fields show Yes/No
	################################################################################################
	
	#Select only Those Item Codes which are having Attributes ==> Templates
	data = frappe.db.sql("""SELECT it.name FROM `tabItem` it
		WHERE it.has_variants = 1
		AND ifnull(it.end_of_life, '2099-12-31') > curdate()
		ORDER BY it.name""", as_list=1)
		
	#Below loop would fetch the data of the attributes from Restriction Table
	#and the Item Variant Attribute table and Item Attribute table to be filled
	#in the report.
	
	for i in range(len(data)):
		#Add the total number of active items under a template
		nos = frappe.db.sql("""SELECT count(it.name) FROM `tabItem` it
		WHERE it.variant_of = '%s' AND ifnull(it.end_of_life, '2099-12-31') > 
		curdate()""" %data[i][0], as_list=1)
		
		data[i].extend(nos[0])
		
		restrictions = []
		for j in attributes:			
			#Check if the attribute is mentioned in the Restrictions table, if it is
			#then insert the value in the report, for Multiple Values
			#the data should be filled like "Rohit, None"
			
			att = frappe.db.sql("""SELECT ifnull(ivr.allowed_values,"-")
				FROM `tabItem Variant Restrictions` ivr
				WHERE ivr.attribute LIKE '%s'
				AND ivr.parent = '%s'
				ORDER BY ivr.allowed_values""" %(j,data[i][0]), as_list=1)
			
			#If attribute has mutliple values in the restriction tables then
			#it would list all the values concatenated
			
			if len(att) > 1: #if restriction table has more than 1 value for a Attribute
				for k in range (len(att)):
					if k > 0:
						restrictions = [[restrictions[0][0] + ", " + att[k][0]]]
					else:
						restrictions = [att[k]]
			elif len(att) == 1:
				restrictions = [att[0]]
			
			else:
				restrictions = ["-"]
			
			restrictions = [restrictions]
			#If attribute is not found in the restrictions table then the code checks if it
			#is in the Item Variant Attribute table, if that attribute is there then the
			#code fetches all the values of the attribute from attribute master and puts it in the 
			#report
			
			if restrictions == [["-"]]:
				att = []
				att = frappe.db.sql("""SELECT iva.attribute
				FROM `tabItem Variant Attribute` iva
				WHERE iva.attribute LIKE '%s'
				AND iva.parent = '%s'""" %(j,data[i][0]), as_list=1)
								
				if att:
					att = frappe.db.sql("""SELECT iav.attribute_value
						FROM `tabItem Attribute Value` iav
						WHERE iav.parent = '%s'
						ORDER BY iav.attribute_value""" %(j), as_list=1)
					if len(att) > 1:
						for k in range (len(att)):
							if k > 0:
								restrictions = [restrictions[0][0] + ", " + att[k][0]]
							else:
								restrictions = [att[k]]
						restrictions = [restrictions]
				else:
					restrictions = [["-"]]
			data[i].extend(restrictions[0])
			
	#data = sorted (data, key = lambda x:(x[1], x[3], x[5], x[6], x[7]))
	#frappe.msgprint(data)
	
	return data
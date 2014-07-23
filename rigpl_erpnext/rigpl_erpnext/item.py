# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe import msgprint

def validate(doc, method):
	#Below fields are for the unique fields which would be used to check
	#if an item is not getting created again.
	#unique0 is the field which is used for DEFINING ITEM IN ITEM CODE.

	unique0 = ["RM","BM","QLT","TT","ZN","SPL","BR"]
	uniquel0 = [doc.height_dia, doc.width, doc.length]
	uniquel1 = [doc.a1, doc.d1, doc.l1, doc.a2,
		doc.d2,doc.l2, doc.r1, doc.a3]
	if (doc.tool_type != "Others"):
		if (doc.tool_type == "Ball Nose"):
				#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit,
				#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc,
				#9.Type, 10.In Desc
			dim_fields = [
				[doc.d1,"Flute \xd8",1,26,doc.d1_inch,
					doc.inch_d1,"F\xd8:"," ","Length", "Yes"],
				[doc.l1,"Flute Length",3,200,doc.l1_inch,
					doc.inch_l1," FL:"," ","Length","Yes"],
				[doc.height_dia,"Shank \xd8",1,26,doc.height_dia_inch,
					doc.inch_h," S\xd8:"," ","Length","Yes"],
				[doc.length,"OAL",25,350,doc.length_inch,
					doc.inch_l," OAL:"," ","Length","Yes"],
				[doc.no_of_flutes,"No of Flutes",2,7,"",""," Z=","",
					"Integer","Yes"],
				[doc.a1, "Angle",0,180.001,"","","","\xb0","Angle","No"]]
				#fields and their limits along with the labels
			spl_trt = ["ACX", "None", "TiN", "TiAlN"] #allowed special treatment
			#FL shud be less than OAL.
			fn_two_nos_compare(doc, "greater", dim_fields[3], dim_fields[1])


		elif (doc.tool_type == "Centre Drill Type A"):
			#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit,
			#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc,
			#9.Type, 10.In Desc
			dim_fields = [
				[doc.d1,"Pilot \xd8",1,25,doc.d1_inch,
					doc.inch_d1,"P\xd8:"," ","Length","Yes"],
				[doc.l1,"Pilot Length",3,200,doc.l1_inch,
					doc.inch_l1," PL:"," ","Length","Yes"],
				[doc.height_dia,"Shank \xd8",1,25,doc.height_dia_inch,
					doc.inch_h," S\xd8:"," ","Length","Yes"],
				[doc.length,"OAL",25,350,doc.length_inch,
					doc.inch_l," OAL:"," ","Length","Yes"],
				[doc.no_of_flutes,"No of Flutes",2,3,"","",
					" Z=","","Integer","Yes"],
				[doc.a1, "Angle",120,120.001,"","","","\xb0","Angle","No"],
				[doc.a2, "Angle",60,60.001,"","","","\xb0","Angle","No"]]
			spl_trt = [] #allowed special treatment
			 #FL shud be less than OAL.
			fn_two_nos_compare(doc, "greater", dim_fields[3], dim_fields[1])
			#Pilot Dia less than Shank Dia
			fn_two_nos_compare(doc, "greater", dim_fields[2], dim_fields[1])

		elif (doc.tool_type == "Centre Drill Type B"):
			#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit,
			#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc,
			#9.Type, 10.In Desc
			dim_fields = [
				[doc.d1,"Pilot \xd8",1,25,doc.d1_inch,
					doc.inch_d1,"P\xd8:"," ","Length","Yes"],
				[doc.l1,"Pilot Length",3,200,doc.l1_inch,
					doc.inch_l1," PL:"," ","Length","Yes"],
				[doc.height_dia,"Shank \xd8",1,25,doc.height_dia_inch,
					doc.inch_h," S\xd8:"," ","Length","Yes"],
				[doc.length,"OAL",25,350,doc.length_inch,
					doc.inch_l," OAL:"," ","Length","Yes"],
				[doc.no_of_flutes,"No of Flutes",2,3,"","","Z=","",
					"Integer","Yes"],
				[doc.a1, "Angle",120,120.001,"","","","\xb0","Angle","No"],
				[doc.a2, "Angle",60,60.001,"","","","\xb0","Angle","No"],
				[doc.a3, "Angle",120,120.001,"","","","\xb0","Angle","No"]]
			spl_trt = [] #allowed special treaftment
			#FL shud be less than OAL.
			fn_two_nos_compare(doc, "greater", dim_fields[3], dim_fields[1])
			#Pilot Dia less than Shank Dia
			fn_two_nos_compare(doc, "greater", dim_fields[2], dim_fields[1])

		elif (doc.tool_type == "Drill"):
			#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit,
				#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc,
				#9.Type, 10.In Desc
			dim_fields = [
				[doc.d1,"Flute \xd8",1,25,doc.d1_inch,
					doc.inch_d1,"F\xd8:"," ","Length","Yes"],
				[doc.l1,"Flute Length",3,200,doc.l1_inch,
					doc.inch_l1," FL:"," ","Length","Yes"],
				[doc.height_dia,"Shank \xd8",1,25,doc.height_dia_inch,
					doc.inch_h," S\xd8:"," ","Length","Yes"],
				[doc.length,"OAL",25,350,doc.length_inch,
					doc.inch_l," OAL:"," ","Length","Yes"],
				[doc.no_of_flutes,"No of Flutes",2,3,"","","Z=","",
					"Integer","Yes"],
				[doc.a1, "Angle",0,180.001,"","","Pt Angle:","\xb0 ","Angle","Yes"]]
			spl_trt = ["ACX", "None", "TiN", "TiAlN"] #allowed special treatment
			 #FL shud be less than OAL.
			fn_two_nos_compare(doc, "greater", dim_fields[3], dim_fields[1])

		elif (doc.tool_type == "Mandrels"):
			#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit,
				#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc,
				#9.Type, 10.In Desc
			dim_fields = [
				[doc.height_dia,"Height",2,100,doc.height_dia_inch,
					doc.inch_h,"","x","Length","Yes"],
				[doc.width,"Width",3,100,doc.width_inch,
					doc.inch_w,"","x","Length","Yes"],
				[doc.length,"OAL",25,550,doc.length_inch,
					doc.inch_l,"","","Length","Yes"],
				[doc.a1, "Bevel Angle",0,31,"",""," Bevel:","\xb0","Angle","Yes"]]
			spl_trt = [] #allowed special treatment
			 #H<W check (10x20 and NOT 20x10)
			fn_two_nos_compare(doc, "greater-equal", dim_fields[1], dim_fields[0])

		elif (doc.tool_type == "Parting"):
			#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit,
				#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc,
				#9.Type, 10.In Desc
			dim_fields = [
				[doc.height_dia,"Height",1,55,doc.height_dia_inch,
					doc.inch_h,"","x","Length","Yes"],
				[doc.width,"Width",4,55,doc.width_inch,
					doc.inch_w,"","x","Length","Yes"],
				[doc.length,"OAL",25,300,doc.length_inch,
					doc.inch_l,"","","Length","Yes"],
				[doc.a1, "Bevel Angle",0,31,"",""," Bevel:","\xb0","Angle","Yes"]]
			spl_trt = ["CRY","None"] #allowed special treatment
			#H<W check (1/8 x 3/4 and NOT 3/4 x 1/8)
			fn_two_nos_compare(doc, "greater", dim_fields[1], dim_fields[0])

		elif (doc.tool_type == "Punch Step3"):
			#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit,
				#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc,
				#9.Type, 10.In Desc
			dim_fields = [
				[doc.height_dia,"Head \xd8",3,26,doc.height_dia_inch,
					doc.inch_h,"H\xd8:"," ","Length","Yes"],
				[doc.l1,"Head Length",2,33,doc.l1_inch,
					doc.inch_l1," HL:"," ","Length","Yes"],
				[doc.d1,"Mid \xd8",2,26,doc.d1_inch,
					doc.inch_d1," M\xd8:"," ","Length","Yes"],
				[doc.l2,"Mid Length",6,101,doc.l2_inch,
					doc.inch_l2," ML:"," ","Length","Yes"],
				[doc.d2,"Front \xd8",1,26,doc.d2_inch,
					doc.inch_d1," F\xd8:"," ","Length","Yes"],
				[doc.length,"OAL",25,300,doc.length_inch,
					doc.inch_l," OAL:","","Length","Yes"],
				[doc.a1, "Angle",0,61,"","","","\xb0","Angle","No"],
				[doc.a2, "Angle",0,61,"","","","\xb0","Angle","No"]]
			spl_trt = [] #allowed special treatment
			#Head Dia > Mid Dia
			fn_two_nos_compare(doc, "greater", dim_fields[0], dim_fields[2])
			#Mid Dia > Front Dia
			fn_two_nos_compare(doc, "greater", dim_fields[2], dim_fields[4])
			#OAL > Sum of Mid Length and Head Length + 5
			if dim_fields[5][0] < (dim_fields[3][0] + dim_fields[1][0] + 5):
				frappe.msgprint('{0}{1}{2}{3}{4}{5}'.format(
				dim_fields[5][1], " should be greater than sum of ",
				dim_fields[3][1], " & ", dim_fields[1][1], " by 5mm."),
				raise_exception=1)

		elif (doc.tool_type == "Punches"):
			#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit,
				#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc,
				#9.Type, 10.In Desc
			dim_fields = [
				[doc.height_dia,"Head \xd8",3,26,doc.height_dia_inch,
					doc.inch_h,"H\xd8:"," ","Length","Yes"],
				[doc.l1,"Head Length",2,33,doc.l1_inch,
					doc.inch_l1," HL:"," ","Length","Yes"],
				[doc.d1,"Body \xd8",1,26,doc.d1_inch,
					doc.inch_d1," B\xd8:"," ","Length","Yes"],
				[doc.length,"OAL",25,300,doc.length_inch,
					doc.inch_l," OAL:"," ","Length","Yes"],
				[doc.a1, "Angle",0,61,"","","","\xb0","Angle","No"]]
			spl_trt = [] #allowed special treatment
			#Head Dia > Body Dia
			fn_two_nos_compare(doc, "greater", dim_fields[0], dim_fields[2])
			#OAL > HL
			fn_two_nos_compare(doc, "greater", dim_fields[3], dim_fields[1])

		elif (doc.tool_type == "Reamer"):
			#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit,
				#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc,
				#9.Type, 10.In Desc
			dim_fields = [
				[doc.d1,"Flute \xd8",3,26,doc.d1_inch,
					doc.inch_d1,"F\xd8:"," ","Length","Yes"],
				[doc.l1,"Flute Length",3,200,doc.l1_inch,
					doc.inch_l1,"FL:"," ","Length","Yes"],
				[doc.height_dia,"Shank \xd8",3,26,doc.height_dia_inch,
					doc.inch_h,"S\xd8:"," ","Length","Yes"],
				[doc.length,"OAL",25,350,doc.length_inch,
					doc.inch_l,"OAL:"," ","Length","Yes"],
				[doc.no_of_flutes,"No of Flutes",4,9,"","","Z=","",
					"Integer","Yes"],
				[doc.a1, "Angle",0,60.001,"","","","\xb0","Angle","Yes"]]
			spl_trt = ["ACX", "None", "TiN", "TiAlN"] #allowed special treatment
			 #FL shud be less than OAL.
			fn_two_nos_compare(doc, "greater", dim_fields[3], dim_fields[1])

		elif (doc.tool_type == "Rectangular"):
			if (doc.is_rm == "No"):
				#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit,
				#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc,
				#9.Type, 10.In Desc
				dim_fields = [
					[doc.height_dia,"Height",0.5,55,
						doc.height_dia_inch,doc.inch_h,"","x",
						"Length","Yes"],
					[doc.width,"Width",1.5,55,doc.width_inch,
						doc.inch_w,"","x","Length","Yes"],
					[doc.length,"OAL",25,550,doc.length_inch,
						doc.inch_l,"","","Length","Yes"],
					[doc.a1, "Bevel Angle",0,31,"","","","\xb0",
						"Angle","Yes"]]
				spl_trt = ["CRY", "None"] #allowed special treatment
			if (doc.is_rm == "Yes"):
				if (doc.base_material == "HSS"):
					spl_trt = ["Hard", "None"] #allowed special treatment
					dim_fields = [
						[doc.height_dia,"Height",6,150,
							doc.height_dia_inch,doc.inch_h,"","x",
							"Length","Yes"],
						[doc.width,"Width",6,150,doc.width_inch,
							doc.inch_w,"","","Length","Yes"],
						[doc.length,"OAL",0,0.001,doc.length_inch,
							doc.inch_l,"","","Length","Yes"],
						[doc.a1, "Bevel Angle",0,0.001,"","","","",
							"Angle","Yes"]]
				elif (doc.base_material == "Carbide"):
					spl_trt = ["None"] #allowed special treatment
					dim_fields = [
						[doc.height_dia,"Height",2.5,30,
							doc.height_dia_inch,doc.inch_h,"","x",
							"Length","Yes"],
						[doc.width,"Width",2.5,30,doc.width_inch,
							doc.inch_w,"","x","Length","Yes"],
						[doc.length,"OAL",10,331,doc.length_inch,
							doc.inch_l,"","","Length","Yes"],
						[doc.a1, "Bevel Angle",0,0.001,"","","","",
							"Angle","Yes"]]
			#H>W check
			fn_two_nos_compare(doc, "greater", dim_fields[1], dim_fields[0])

		elif (doc.tool_type == "Round"):
			if (doc.is_rm == "No"):
				#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit,
				#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc,
				#9.Type, 10.In Desc
				dim_fields = [
					[doc.height_dia,"Dia \xd8",0.5,55,
						doc.height_dia_inch,doc.inch_h,"\xd8","x",
						"Length","Yes"],
					[doc.length,"OAL",25,550,doc.length_inch,
						doc.inch_l,"","","Length","Yes"],
					[doc.a1, "Bevel Angle",0,0.001,"",""," Bevel:","\xb0",
						"Angle","Yes"]]
				spl_trt = ["CRY", "None"] #allowed special treatment
			if (doc.is_rm == "Yes"):
				if (doc.base_material == "HSS"):
					spl_trt = ["Hard", "None"] #allowed special treatment
					dim_fields = [
						[doc.height_dia,"Dia \xd8",2,151,
							doc.height_dia_inch,doc.inch_h,"\xd8"," ",
							"Length","Yes"],
						[doc.length,"OAL",0,0.001,doc.length_inch,
							doc.inch_l,"","","Length","Yes"],
						[doc.a1, "Bevel Angle",0,0.001,"","","","\xb0",
							"Angle","No"]]
				elif (doc.base_material == "Carbide"):
					spl_trt = ["None"] #allowed special treatment
					dim_fields = [
						[doc.height_dia,"Dia \xd8",3,33,
							doc.height_dia_inch,doc.inch_h,"\xd8","x",
							"Length","Yes"],
						[doc.length,"OAL",10,331,doc.length_inch,
							doc.inch_l,"","","Length","Yes"],
						[doc.a1, "Bevel Angle",0,0.001,"",""," Bevel:","\xb0",
							"Angle","No"]]

		elif (doc.tool_type == "SQEM"):
				#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit,
				#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc,
				#9.Type, 10.In Desc
			dim_fields = [
				[doc.d1,"Flute \xd8",1,26,doc.d1_inch,
					doc.inch_d1,"F\xd8:"," ","Length", "Yes"],
				[doc.l1,"Flute Length",3,200,doc.l1_inch,
					doc.inch_l1,"FL:"," ","Length","Yes"],
				[doc.height_dia,"Shank \xd8",1,26,doc.height_dia_inch,
					doc.inch_h,"S\xd8:"," ","Length","Yes"],
				[doc.length,"OAL",25,350,doc.length_inch,
					doc.inch_l,"OAL:"," ","Length","Yes"],
				[doc.no_of_flutes,"No of Flutes",2,7,"","","Z=","",
					"Integer","Yes"],
				[doc.a1, "Angle",0,180.001,"","","","\xb0","Angle","No"]]
				#fields and their limits along with the labels
			spl_trt = ["ACX", "None", "TiN", "TiAlN"] #allowed special treatment
			#FL shud be less than OAL.
			fn_two_nos_compare(doc, "greater", dim_fields[3], dim_fields[1])

		elif (doc.tool_type == "Square"):
			if (doc.is_rm == "No"):
				#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit,
				#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc,
				#9.Type, 10.In Desc
				dim_fields = [
					[doc.height_dia,"Height",1.5,55,
						doc.height_dia_inch,doc.inch_h,"","x",
						"Length","Yes"],
					[doc.width,"Width",1.5,55,doc.width_inch,
						doc.inch_w,"","x","Length","Yes"],
					[doc.length,"OAL",25,550,doc.length_inch,
						doc.inch_l,"","","Length","Yes"],
					[doc.a1, "Bevel Angle",0,31,"","","","\xb0",
						"Angle","Yes"]]
				spl_trt = ["TiN", "CRY", "None"] #allowed special treatment
			if (doc.is_rm == "Yes"):
				if (doc.base_material == "HSS"):
					spl_trt = ["Hard", "None"] #allowed special treatment
					dim_fields = [
						[doc.height_dia,"Height",2.5,150,
							doc.height_dia_inch,doc.inch_h,"","x",
							"Length","Yes"],
						[doc.width,"Width",2.5,150,doc.width_inch,
							doc.inch_w,"","","Length","Yes"],
						[doc.length,"OAL",0,0.001,doc.length_inch,
							doc.inch_l,"","","Length","Yes"],
						[doc.a1, "Bevel Angle",0,0.001,"","","","",
							"Angle","Yes"]]
				elif (doc.base_material == "Carbide"):
					spl_trt = ["None"] #allowed special treatment
					dim_fields = [
						[doc.height_dia,"Height",2.5,50,
							doc.height_dia_inch,doc.inch_h,"","x",
							"Length","Yes"],
						[doc.width,"Width",2.5,50,doc.width_inch,
							doc.inch_w,"","x","Length","Yes"],
						[doc.length,"OAL",0,400,doc.length_inch,
							doc.inch_l,"","","Length","Yes"],
						[doc.a1, "Bevel Angle",0,0.001,"","","","",
							"Angle","Yes"]]
			#H=W check
			fn_two_nos_compare(doc, "equal", dim_fields[0], dim_fields[1])

		else:
			frappe.msgprint('{0}{1}{2}'.format("Tool Type Selected =",
				doc.tool_type, ", is not covered. Kindly contact \
				aditya@rigpl.com or Mr Aditya Duggal for further information"),
				raise_exception=1)

		fn_common_check(doc)
		fn_integer_check(doc, dim_fields) #limit check
		#Make Description, Web Description, Item Code, Concat, Concat1,
		#Item Name (in the above order only)
		doc.description,doc.web_long_description,doc.item_code,doc.concat,doc.concat1,doc.item_name = fn_gen_description(doc, dim_fields, spl_trt, uniquel0, uniquel1)
################################################################################
def fn_gen_description(doc, fds,trt,ul0, ul1):
	#This function generates the following:
	#Item Code, Description, Website Description, Web Specs,
	#Item Uniqueness check fields

	#ic_RM, ic_BM, ic_QLT, ic_TT, ic_ZN, ic_SP, ic_BR, ic_SN, ic_CD
	#D_RM, D_BM, D_BR, D_QLT, D_SPL, D_DT, D_TT, D_SZ, DZN
	#S1_RM

	if doc.is_rm == "Yes":
		ic_RM = "R"
		D_RM = "RM "
		Dw_RM = "Raw Material "
	else:
		ic_RM = ""
		D_RM = ""
		Dw_RM = ""

	if doc.base_material == "HSS":
		ic_BM = "H"
		D_BM = "HSS "
		Dw_BM = "High Speed Steel "
	elif doc.base_material == "Carbide":
		ic_BM = "C"
		D_BM = "Carb "
		Dw_BM = "Solid Carbide "
	else:
		msgprint("Please enter base material", raise_exception=1)

	ic_QLT = frappe.db.get_value("Quality", doc.quality , "code")
	D_QLT = frappe.db.get_value("Quality", doc.quality,
		"description") + " "
	Dw_QLT = frappe.db.get_value("Quality", doc.quality,
		"website_description") + " "

	ic_TT = frappe.db.get_value("Tool Type", doc.tool_type ,
		 "code")
	D_TT = frappe.db.get_value("Tool Type", doc.tool_type,
		"description") + " "
	Dw_TT = frappe.db.get_value("Tool Type", doc.tool_type,
		"website_description") + " "

	ic_ZN = fn_flutes(doc, doc.no_of_flutes)

	ic_SP = fn_special_trt_check(doc, trt)
	SPL = doc.special_treatment
	if SPL == 'CRY':
		if doc.quality == "H-3X":
			D_SPL = '{0}'.format("EC500 ")
			Dw_SPL = D_SPL
		else:
			D_SPL = SPL + " "
			Dw_SPL = "Cryogenically Treated "
	elif SPL == 'ACX' or SPL == 'Hard' or SPL == 'TiAlN' or SPL == 'TiN':
		D_SPL = '{0}{1}'.format(doc.special_treatment, " ")
		Dw_SPL = D_SPL
	else:
		D_SPL = '{0}'.format("")
		Dw_SPL = D_SPL

	ic_BR = frappe.db.get_value("Brand", doc.brand, "code")
	if ic_BR == "X": ic_BR = ""
	D_BR = '{0}{1}'.format(frappe.db.get_value("Brand", doc.brand,
		 "item_desc"), " ")
	Dw_BR = D_BR
	#old Serial no from Item Group
	#ic_SN =  frappe.db.get_value("Item Group", "Carbide Tools" ,
	#	"serial_number")

	#new serial no from tool Type
	ic_SN = frappe.db.get_value("Tool Type", doc.tool_type ,
		"serial_number")

	ic_check = '{0}{1}{2}{3}{4}{5}{6}'.format(ic_RM, ic_BM,
		ic_QLT, ic_TT, ic_ZN, ic_SP, ic_BR)
	ic_inter = '{0}{1}{2}{3}{4}{5}{6}{7}'.format(ic_RM, ic_BM,
		ic_QLT, ic_TT, ic_ZN, ic_SP, ic_BR, ic_SN)
	ic_CD = fn_check_digit(doc, ic_inter)
	ic_code = '{0}{1}'.format(ic_inter, ic_CD)

	if (doc.item_code and doc.item_code != "dummy"):
		ic_existing = doc.item_code[:(len(doc.item_code)-4)]
		#frappe.msgprint(ic_existing)
		if ic_existing != ic_check:
			frappe.msgprint("Change NOT ALLOWED since this would change \
				Item Code which is NOT POSSIBLE.\nKindly contact \
				Aditya Duggal for further details",
				raise_exception = 1)

	if doc.drill_type is None:
		D_DT = '{0}'.format("")
		Dw_DT = D_DT
	else:
		D_DT = '{0}{1}'.format(doc.drill_type, " ")
		Dw_DT = D_DT

	D_SZ = ""
	Dw_SZ = ""
      ######################################################################
		#Size Description Generation
      ######################################################################
	for i in range(0,len(fds)):
		if fds[i][9] == "Yes": #Check if field is to be used in desc
			if fds[i][8] == "Length": #Check type of field
				if fds[i][0] != 0 :
					if fds[i][5]==1: #Check if Inch box checked
						D_SZ += '{0}{1}{2}{3}'.format(fds[i][6],fds[i][4],
							'"',fds[i][7])
						Dw_SZ +=  '{0}{1}{2}{3}'.format(fds[i][6],fds[i][4],
						'"',fds[i][7])
					else:
						D_SZ += '{0}{1:.4g}{2}'.format(fds[i][6],fds[i][0],
							fds[i][7])
						Dw_SZ += '{0}{1:.4g}{2}{3}'.format(fds[i][6],
							fds[i][0],'mm',fds[i][7])
			elif fds[i][8] == "Angle":
				if fds[i][0] != 0 :
					D_SZ += '{0}{1}{2}'.format(" ", fds[i][0], fds[i][7])
					Dw_SZ += '{0}{1}{2}{3}{4}'.format(" ", fds[i][1],":",
						fds[i][0], fds[i][7])
			elif fds[i][8] == "Integer":
				if fds[i][0] != 0 :
					D_SZ += '{0}{1}{2}{3}'.format(" ", fds[i][6], fds[i][0],
						 fds[i][7])
					Dw_SZ += '{0}{1}{2}{3}'.format(" ", fds[i][6],fds[i][0],
						 fds[i][7])

	if (doc.no_of_flutes):
		D_ZN = '{0}{1}'.format(" Z= ", doc.no_of_flutes)
		Dw_ZN = '{0}{1}'.format(" Flutes= ", doc.no_of_flutes)
	else:
		D_ZN = '{0}'.format("")
		Dw_ZN = '{0}'.format("")

	D_Desc = '{0}{1}{2}{3}{4}{5}{6}{7}'.format(D_RM, D_BM, D_BR, D_QLT,
		 D_SPL, D_DT, D_TT, D_SZ)
	Dw_Desc = '{0}{1}{2}{3}{4}{5}{6}{7}'.format(Dw_RM, Dw_BM, Dw_BR,
		 Dw_QLT, Dw_SPL, Dw_DT, Dw_TT, Dw_SZ)

	it_name = '{0}{1}{2}{3}{4}{5}{6}{7}'.format(Dw_RM, Dw_BM, Dw_BR,
		 Dw_QLT, Dw_SPL, Dw_DT, Dw_TT, Dw_SZ)

	it_name = (it_name[:140]+ '...') if len(it_name)>140 else it_name

    ####################################################################
		#Unique Fields list which are in numbers
    #######################################################################
	uc_c0 = '{0}{1}{2}{3}{4}{5}{6}'.format(ic_RM, ic_BM, ic_QLT, ic_TT,
		 ic_ZN, ic_SP, ic_BR)
	for i in range(0,len(ul0)):
		if (ul0[i]):
			if ul0[i] == 0:
				uc_c0 += '{0:.4f}'.format(0.0000)
			else:
				uc_c0 += '{0:.4f}'.format(ul0[i])
		else:
			uc_c0 += '{0:.4f}'.format(0.0000)

	uc_c1 = ""
	for i in range(0,len(ul1)):
		if (ul1[i]):
			if ul1[i] == 0:
				uc_c1 += '{0:.4f}'.format(0.0000)
			else:
				uc_c1 += '{0:.4f}'.format(ul1[i])
		else:
			uc_c1 += '{0:.4f}'.format(0.0000)
	########################################################################
	#Update the IMAGE From TOOL TYPE
	########################################################################
	doc.dim_image_list = frappe.db.get_value("File Data",
	    {"attached_to_doctype": "Tool Type", "attached_to_name":
	    doc.tool_type}, "file_url")

	return (D_Desc, Dw_Desc, ic_code, uc_c0, uc_c1, it_name)
################################################################################
def fn_next_string(doc,s):
	#This function would increase the serial number by One following the
	#alpha-numeric rules as well
	if len(s) == 0:
		return '1'
	head = s[0:-1]
	tail = s[-1]
	if tail == 'Z':
		return fn_next_string(doc, head) + '0'
	if tail == '9':
		return head+'A'
	if tail == 'H':
		return head+'J'
	if tail == 'N':
		return head+'P'
	return head + chr(ord(tail)+1)
################################################################################
def fn_integer_check(doc,float):
	for i in range(0,len(float)):
		if not float[i][0]:
			float[i][0] = 0
			if float[i][0] < float[i][2] or float[i][0] >= float[i][3]:
				frappe.msgprint('{0}{1}{2}{3}{4}{5}'.format(float[i][1],
				" entered should be between ", float[i][2],
				" (including) and ",float[i][3], " (excluding)"),
				raise_exception=1)
		else:
			if float[i][0] < float[i][2] or float[i][0] >= float[i][3]:
				frappe.msgprint('{0}{1}{2}{3}{4}{5}'.format(float[i][1],
				" entered should be between ", float[i][2],
				" (including) and ",float[i][3], " (excluding)"),
				raise_exception=1)
################################################################################
def fn_common_check(doc):
		#Check if the BRAND selected is in unison with RM
	if (doc.is_rm):
		if doc.is_rm != frappe.db.get_value ("Brand", doc.brand, "is_rm"):
			frappe.msgprint("Brand Selected is NOT ALLOWED", raise_exception=1)

		#Check if the base material selected is in unison with the quality
	if doc.base_material != frappe.db.get_value("Quality", doc.quality, "base_material"):
		frappe.msgprint("Base Material and Quality Combo is WRONG", raise_exception=1)

		#Check if the IS RM selected is in unison with the quality
	if (doc.is_rm):
		if doc.is_rm != frappe.db.get_value("Quality", doc.quality, "is_rm"):
			 frappe.msgprint("RM-Quality Combo is WRONG", raise_exception=1)
################################################################################
def fn_two_nos_compare(doc,type, d1, d2):
	if type == "equal":
		if d1[0] != d2[0]:
			frappe.msgprint('{0}{1}{2}'.format(d1[1],
			" should be equal to ", d2[1]), raise_exception=1)
	elif type == "greater":
		if d1[0] <= d2[0]:
			frappe.msgprint('{0}{1}{2}'.format(d1[1],
			" should be greater than ", d2[1]), raise_exception=1)
	else:
		if d1[0] < d2[0]:
			frappe.msgprint('{0}{1}{2}'.format(d1[1],
			" should be greater than or equal to ", d2[1]),
			raise_exception=1)
################################################################################
def fn_special_trt_check(doc, spl):
	if not spl:
		if (doc.special_treatment) :
			frappe.msgprint('{0}{1}{2}'.format("Special Treatment- ",
		doc.special_treatment, " selected is not allowed"),
		raise_exception=1)
	else:
		if doc.special_treatment not in spl:
			frappe.msgprint('{0}{1}{2}'.format("Special Treatment- ",
			doc.special_treatment, " selected is not allowed"),
			raise_exception=1)
	return {
		"TiAlN": '1',
		"TiN": '2',
		"ACX": '3',
		"CRY": '4',
		"ALDURA": '5',
		"Hard": 'H',
	}.get(doc.special_treatment,"")
##############~Code to generate the letter based on Flutes~#####################
################################################################################
def fn_flutes(doc,flutes):
	return {
		1:1,
		2:2,
		3:3,
		4:4,
		5:5,
		6:6,
		7:7,
		8:8,
		9:9,
		10:'A',
	}.get(flutes,"")

###############~Code to generate the CHECK DIGIT~###############################
################################################################################
def fn_check_digit(doc,id_without_check):

	# allowable characters within identifier
	valid_chars = "0123456789ABCDEFGHJKLMNPQRSTUVYWXZ"

	# remove leading or trailing whitespace, convert to uppercase
	id_without_checkdigit = id_without_check.strip().upper()

	# this will be a running total
	sum = 0;

	# loop through digits from right to left
	for n, char in enumerate(reversed(id_without_checkdigit)):

			if not valid_chars.count(char):
					raise Exception('InvalidIDException')

			# our "digit" is calculated using ASCII value - 48
			digit = ord(char) - 48

			# weight will be the current digit's contribution to
			# the running total
			weight = None
			if (n % 2 == 0):

					# for alternating digits starting with the rightmost, we
					# use our formula this is the same as multiplying x 2 &
					# adding digits together for values 0 to 9.  Using the
					# following formula allows us to gracefully calculate a
					# weight for non-numeric "digits" as well (from their
					# ASCII value - 48).
					weight = (2 * digit) - int((digit / 5)) * 9
			else:
					# even-positioned digits just contribute their ascii
					# value minus 48
					weight = digit

			# keep a running total of weights
			sum += weight

	# avoid sum less than 10 (if characters below "0" allowed,
	# this could happen)
	sum = abs(sum) + 10

	# check digit is amount needed to reach next number
	# divisible by ten. Return an integer
	return int((10 - (sum % 10)) % 10)

def autoname(doc, method):
	validate(doc, method)
	#New Serial No from Tool Type
	sn = frappe.db.get_value("Tool Type", doc.tool_type ,
		"serial_number")
	nxt_sn = fn_next_string(doc, sn)
	frappe.db.set_value("Tool Type", doc.tool_type,
		"serial_number", nxt_sn)

	#old Serial No from Item Group

	#sn = frappe.db.get_value("Item Group", "Carbide Tools" ,
	#	"serial_number")
	#nxt_sn = self.fn_next_string(sn)
	#frappe.db.set_value("Item Group", "Carbide Tools",
	#	"serial_number", nxt_sn)

	doc.autoname()

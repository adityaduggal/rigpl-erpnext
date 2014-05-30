# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import webnotes
from webnotes.model.doc import addchild

class CustomDocType(DocType):
################################################################################
		#Validation based on various rules for Tool Types
################################################################################
	def custom_validate(self):
	
		#Below fields are for the unique fields which would be used to check
		#if an item is not getting created again.
		#unique0 is the field which is used for DEFINING ITEM IN ITEM CODE.
		
		unique0 = ["RM","BM","QLT","TT","ZN","SPL","BR"]
		uniquel0 = [self.doc.height_dia, self.doc.width, self.doc.length]
		uniquel1 = [self.doc.a1, self.doc.d1, self.doc.l1, self.doc.a2, 
			self.doc.d2,self.doc.l2, self.doc.r1, self.doc.a3]
		if (self.doc.tool_type != "Others"):
			if (self.doc.tool_type == "Ball Nose"):
					#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit, 
					#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc, 9.Type, 10.In Desc
				dim_fields = [
					[self.doc.d1,"Flute \xd8",1,25,self.doc.d1_inch,
						self.doc.inch_d1,"F\xd8:"," ","Length", "Yes"],
					[self.doc.l1,"Flute Length",3,200,self.doc.l1_inch,
						self.doc.inch_l1,"FL:"," ","Length","Yes"],
					[self.doc.height_dia,"Shank \xd8",1,25,self.doc.height_dia_inch,
						self.doc.inch_h,"S\xd8:"," ","Length","Yes"],
					[self.doc.length,"OAL",25,350,self.doc.length_inch,
						self.doc.inch_l,"OAL:"," ","Length","Yes"],
					[self.doc.no_of_flutes,"No of Flutes",2,7,"","","Z=","",
						"Integer","Yes"],
					[self.doc.a1, "Angle",0,180.001,"","","","\xb0","Angle","No"]] 
					#fields and their limits along with the labels
				spl_trt = ["ACX", "None", "TiN", "TiAlN"] #allowed special treatment
				#FL shud be less than OAL.
				self.fn_two_nos_compare("greater", dim_fields[3], dim_fields[1]) 
			
		
			elif (self.doc.tool_type == "Centre Drill Type A"):
				#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit, 
				#5.inch_field, 6.is_inch, 7.desc, 8.web desc, 9.Type, 10.In Desc
				dim_fields = [
					[self.doc.d1,"Pilot \xd8",1,25,self.doc.d1_inch,
						self.doc.inch_d1,"P\xd8:"," ","Length","Yes"],
					[self.doc.l1,"Pilot Length",3,200,self.doc.l1_inch,
						self.doc.inch_l1,"PL:"," ","Length","Yes"],
					[self.doc.height_dia,"Shank \xd8",1,25,self.doc.height_dia_inch,
						self.doc.inch_h,"S\xd8:"," ","Length","Yes"],
					[self.doc.length,"OAL",25,350,self.doc.length_inch,
						self.doc.inch_l,"OAL:"," ","Length","Yes"],
					[self.doc.no_of_flutes,"No of Flutes",2,3,"","",
						"Z=","","Integer","Yes"],
					[self.doc.a1, "Angle",120,120.001,"","","","\xb0","Angle","No"]
					[self.doc.a2, "Angle",60,60.001,"","","","\xb0","Angle","No"]]
				spl_trt = [] #allowed special treatment
				 #FL shud be less than OAL.
				self.fn_two_nos_compare("greater", dim_fields[3], dim_fields[1])
				#Pilot Dia less than Shank Dia
				self.fn_two_nos_compare("greater", dim_fields[2], dim_fields[1])
		
			elif (self.doc.tool_type == "Centre Drill Type B"):
				#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit, 
				#5.inch_field, 6.is_inch, 7.desc, 8.web desc, 9.Type, 10.In Desc
				dim_fields = [
					[self.doc.d1,"Pilot \xd8",1,25,self.doc.d1_inch,
						self.doc.inch_d1,"P\xd8:"," ","Length","Yes"],
					[self.doc.l1,"Pilot Length",3,200,self.doc.l1_inch,
						self.doc.inch_l1,"PL:"," ","Length","Yes"],
					[self.doc.height_dia,"Shank \xd8",1,25,self.doc.height_dia_inch,
						self.doc.inch_h,"S\xd8:"," ","Length","Yes"],
					[self.doc.length,"OAL",25,350,self.doc.length_inch,
						self.doc.inch_l,"OAL:"," ","Length","Yes"],
					[self.doc.no_of_flutes,"No of Flutes",2,3,"","","Z=","",
						"Integer","Yes"],
					[self.doc.a1, "Angle",120,120.001,"","","","\xb0","Angle","No"]
					[self.doc.a2, "Angle",60,60.001,"","","","\xb0","Angle","No"]
					[self.doc.a3, "Angle",120,120.001,"","","","\xb0","Angle","No"]] 
				spl_trt = [] #allowed special treaftment
				#FL shud be less than OAL.
				self.fn_two_nos_compare("greater", dim_fields[3], dim_fields[1])
				#Pilot Dia less than Shank Dia
				self.fn_two_nos_compare("greater", dim_fields[2], dim_fields[1])
		
			elif (self.doc.tool_type == "Drill"):
				#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit, 
				#5.inch_field, 6.is_inch, 7.desc, 8.web desc, 9.Type, 10.In Desc
				dim_fields = [
					[self.doc.d1,"Flute \xd8",1,25,self.doc.d1_inch,
						self.doc.inch_d1,"F\xd8:"," ","Length","Yes"],
					[self.doc.l1,"Flute Length",3,200,self.doc.l1_inch,
						self.doc.inch_l1,"FL:"," ","Length","Yes"],
					[self.doc.height_dia,"Shank \xd8",1,25,self.doc.height_dia_inch,
						self.doc.inch_h,"S\xd8:"," ","Length","Yes"],
					[self.doc.length,"OAL",25,350,self.doc.length_inch,
						self.doc.inch_l,"OAL:"," ","Length","Yes"],
					[self.doc.no_of_flutes,"No of Flutes",2,3,"","","Z=","",
						"Integer","Yes"],
					[self.doc.a1, "Angle",0,180.001,"","","","\xb0","Angle","Yes"]]
				spl_trt = ["ACX", "None", "TiN", "TiAlN"] #allowed special treatment
				 #FL shud be less than OAL.
				self.fn_two_nos_compare("greater", dim_fields[3], dim_fields[1])
		
			elif (self.doc.tool_type == "Mandrels"):
				#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit, 
				#5.inch_field, 6.is_inch, 7.desc, 8.web desc, 9.Type, 10.In Desc
				dim_fields = [
					[self.doc.height_dia,"Height",0.5,55,self.doc.height_dia_inch,
						self.doc.inch_h,"","x","Length","Yes"],
					[self.doc.width,"Width",1.5,55,self.doc.width_inch,
						self.doc.inch_w,"","x","Length","Yes"],
					[self.doc.length,"OAL",25,550,self.doc.length_inch,
						self.doc.inch_l,"","","Length","Yes"],
					[self.doc.a1, "Bevel Angle",0,31,"","","","\xb0","Angle","Yes"]]
				spl_trt = [] #allowed special treatment
				 #H>W check
				self.fn_two_nos_compare("greater-equal", dim_fields[0], dim_fields[1])
			
			elif (self.doc.tool_type == "Parting"):
				#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit, 
				#5.inch_field, 6.is_inch, 7.desc, 8.web desc, 9.Type, 10.In Desc
				dim_fields = [
					[self.doc.height_dia,"Height",1,55,self.doc.height_dia_inch,
						self.doc.inch_h,"","x","Length","Yes"],
					[self.doc.width,"Width",4,55,self.doc.width_inch,
						self.doc.inch_w,"","x","Length","Yes"],
					[self.doc.length,"OAL",25,300,self.doc.length_inch,
						self.doc.inch_l,"","","Length","Yes"],
					[self.doc.a1, "Bevel Angle",0,31,"","","","\xb0","Angle","Yes"]]
				spl_trt = ["CRY","None"] #allowed special treatment
				#H>W check
				self.fn_two_nos_compare("greater", dim_fields[0], dim_fields[1])
		
			elif (self.doc.tool_type == "Punch Step3"):
				#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit, 
				#5.inch_field, 6.is_inch, 7.desc, 8.web desc, 9.Type, 10.In Desc
				dim_fields = [
					[self.doc.height_dia,"Head \xd8",5,26,self.doc.height_dia_inch,
						self.doc.inch_h,"H\xd8:","","Length","Yes"],
					[self.doc.l1,"Head Length",2,101,self.doc.l1_inch,
						self.doc.inch_l1," HL:","","Length","Yes"],
					[self.doc.d1,"Mid \xd8",5,26,self.doc.d1_inch,
						self.doc.inch_d1," M\xd8:","","Length","Yes"],
					[self.doc.l2,"Mid Length",6,101,self.doc.l2_inch,
						self.doc.inch_l2," ML:","","Length","Yes"],
					[self.doc.d2,"Front \xd8",5,26,self.doc.d2_inch,
						self.doc.inch_d1," F\xd8:","","Length","Yes"],
					[self.doc.length,"OAL",25,300,self.doc.length_inch,
						self.doc.inch_l," OAL:","","Length","Yes"],
					[self.doc.a1, "Angle",0,61,"","","","\xb0","Angle","No"],
					[self.doc.a2, "Angle",0,61,"","","","\xb0","Angle","No"]]
				spl_trt = [] #allowed special treatment
				#Head Dia > Mid Dia
				self.fn_two_nos_compare("greater", dim_fields[0], dim_fields[2])
				#Mid Dia > Front Dia
				self.fn_two_nos_compare("greater", dim_fields[2], dim_fields[4])
				#OAL > Sum of Mid Length and Head Length + 5
				if dim_fields[5][0] < (dim_fields[3][0] + dim_fields[1][0] + 5):
					webnotes.msgprint('{0}{1}{2}{3}{4}{5}'.format(
					dim_fields[5][1], " should be greater than sum of ", 
					dim_fields[3][1], " & ", dim_fields[1][1], " by 5mm."), 
					raise_exception=1)

			elif (self.doc.tool_type == "Punches"):
				#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit, 
				#5.inch_field, 6.is_inch, 7.desc, 8.web desc, 9.Type, 10.In Desc
				dim_fields = [
					[self.doc.height_dia,"Head \xd8",5,26,self.doc.height_dia_inch,
						self.doc.inch_h,"H\xd8:","Head \xd8:","Length","Yes"],
					[self.doc.l1,"Head Length",2,101,self.doc.l1_inch,
						self.doc.inch_l1," HL:"," Head Length:","Length","Yes"],
					[self.doc.d1,"Body \xd8",5,26,self.doc.d1_inch,
						self.doc.inch_d1," B\xd8:"," Body \xd8:","Length","Yes"],
					[self.doc.length,"OAL",25,300,self.doc.length_inch,
						self.doc.inch_l," OAL:"," Overall Length:","Length","Yes"],
					[self.doc.a1, "Angle",0,61,"","","","\xb0","Angle","No"]]
				spl_trt = [] #allowed special treatment
				#Head Dia > Body Dia
				self.fn_two_nos_compare("greater", dim_fields[0], dim_fields[2])
				#OAL > HL
				self.fn_two_nos_compare("greater", dim_fields[3], dim_fields[1])

			elif (self.doc.tool_type == "Reamer"):
				#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit, 
				#5.inch_field, 6.is_inch, 7.desc, 8.web desc, 9.Type, 10.In Desc
				dim_fields = [
					[self.doc.d1,"Flute \xd8",1,25,self.doc.d1_inch,
						self.doc.inch_d1,"F\xd8:"," Flute \xd8:","Length","Yes"],
					[self.doc.l1,"Flute Length",3,200,self.doc.l1_inch,
						self.doc.inch_l1,"FL:"," Flute Length:","Length","Yes"],
					[self.doc.height_dia,"Shank \xd8",1,25,self.doc.height_dia_inch,
						self.doc.inch_h,"S\xd8:"," Shank \xd8:","Length","Yes"],
					[self.doc.length,"OAL",25,350,self.doc.length_inch,
						self.doc.inch_l,"OAL:"," Overall Length:","Length","Yes"],
					[self.doc.no_of_flutes,"No of Flutes",4,9,"","","Z=","",
						"Integer","Yes"],
					[self.doc.a1, "Angle",0,60.001,"","","","\xb0","Angle","Yes"]]
				spl_trt = ["ACX", "None", "TiN", "TiAlN"] #allowed special treatment
				 #FL shud be less than OAL.
				self.fn_two_nos_compare("greater", dim_fields[3], dim_fields[1])

			elif (self.doc.tool_type == "Rectangular"):
				if (self.doc.is_rm == "No"):
					#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit, 
					#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc, 9.Type, 10.In Desc
					dim_fields = [
						[self.doc.height_dia,"Height",0.5,55,
							self.doc.height_dia_inch,self.doc.inch_h,"","x",
							"Length","Yes"],
						[self.doc.width,"Width",1.5,55,self.doc.width_inch,
							self.doc.inch_w,"","x","Length","Yes"],
						[self.doc.length,"OAL",25,550,self.doc.length_inch,
							self.doc.inch_l,"","","Length","Yes"],
						[self.doc.a1, "Bevel Angle",0,31,"","","","\xb0",
							"Angle","Yes"]]
					spl_trt = ["CRY", "None"] #allowed special treatment
				if (self.doc.is_rm == "Yes"):
					if (self.doc.base_material == "HSS"):
						spl_trt = ["Hard", "None"] #allowed special treatment
						dim_fields = [
							[self.doc.height_dia,"Height",6,150,
								self.doc.height_dia_inch,self.doc.inch_h,"","x",
								"Length","Yes"],
							[self.doc.width,"Width",6,150,self.doc.width_inch,
								self.doc.inch_w,"","","Length","Yes"],
							[self.doc.length,"OAL",0,0.001,self.doc.length_inch,
								self.doc.inch_l,"","","Length","Yes"],
							[self.doc.a1, "Bevel Angle",0,0.001,"","","","",
								"Angle","Yes"]]
					elif (self.doc.base_material == "Carbide"):
						spl_trt = ["None"] #allowed special treatment
						dim_fields = [
							[self.doc.height_dia,"Height",2.5,30,
								self.doc.height_dia_inch,self.doc.inch_h,"","x",
								"Length","Yes"],
							[self.doc.width,"Width",2.5,30,self.doc.width_inch,
								self.doc.inch_w,"","x","Length","Yes"],
							[self.doc.length,"OAL",10,331,self.doc.length_inch,
								self.doc.inch_l,"","","Length","Yes"],
							[self.doc.a1, "Bevel Angle",0,0.001,"","","","",
								"Angle","Yes"]]
				#H>W check
				self.fn_two_nos_compare("greater", dim_fields[1], dim_fields[0])

			elif (self.doc.tool_type == "Round"):
				if (self.doc.is_rm == "No"):
					#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit, 
					#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc, 9.Type, 10.In Desc
					dim_fields = [
						[self.doc.height_dia,"Dia \xd8",0.5,55,
							self.doc.height_dia_inch,self.doc.inch_h,"\xd8","x",
							"Length","Yes"],
						[self.doc.length,"OAL",25,550,self.doc.length_inch,
							self.doc.inch_l,"","","Length","Yes"],
						[self.doc.a1, "Bevel Angle",0,0.001,"","","","\xb0",
							"Angle","Yes"]]
					spl_trt = ["CRY", "None"] #allowed special treatment
				if (self.doc.is_rm == "Yes"):
					if (self.doc.base_material == "HSS"):
						spl_trt = ["Hard", "None"] #allowed special treatment
						dim_fields = [
							[self.doc.height_dia,"Dia \xd8",2,151,
								self.doc.height_dia_inch,self.doc.inch_h,"\xd8"," ",
								"Length","Yes"],
							[self.doc.length,"OAL",0,0.001,self.doc.length_inch,
								self.doc.inch_l,"","","Length","Yes"],
							[self.doc.a1, "Bevel Angle",0,0.001,"","","","\xb0",
								"Angle","No"]]
					elif (self.doc.base_material == "Carbide"):
						spl_trt = ["None"] #allowed special treatment
						dim_fields = [
							[self.doc.height_dia,"Dia \xd8",3,33,
								self.doc.height_dia_inch,self.doc.inch_h,"\xd8"," ",
								"Length","Yes"],
							[self.doc.length,"OAL",10,331,self.doc.length_inch,
								self.doc.inch_l,"","","Length","Yes"],
							[self.doc.a1, "Bevel Angle",0,0.001,"","","","\xb0",
								"Angle","No"]]

			elif (self.doc.tool_type == "SQEM"):
					#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit, 
					#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc, 9.Type, 10.In Desc
				dim_fields = [
					[self.doc.d1,"Flute \xd8",1,25,self.doc.d1_inch,
						self.doc.inch_d1,"F\xd8:"," ","Length", "Yes"],
					[self.doc.l1,"Flute Length",3,200,self.doc.l1_inch,
						self.doc.inch_l1,"FL:"," ","Length","Yes"],
					[self.doc.height_dia,"Shank \xd8",1,25,self.doc.height_dia_inch,
						self.doc.inch_h,"S\xd8:"," ","Length","Yes"],
					[self.doc.length,"OAL",25,350,self.doc.length_inch,
						self.doc.inch_l,"OAL:"," ","Length","Yes"],
					[self.doc.no_of_flutes,"No of Flutes",2,7,"","","Z=","",
						"Integer","Yes"],
					[self.doc.a1, "Angle",0,180.001,"","","","\xb0","Angle","No"]] 
					#fields and their limits along with the labels
				spl_trt = ["ACX", "None", "TiN", "TiAlN"] #allowed special treatment
				#FL shud be less than OAL.
				self.fn_two_nos_compare("greater", dim_fields[3], dim_fields[1]) 

			elif (self.doc.tool_type == "Square"):
				if (self.doc.is_rm == "No"):
					#1.Field Name, 2.Field Label, 3.Lower Limit, 4.Upper Limit, 
					#5.inch_field, 6.is_inch, 7.pref_desc, 8.suff_desc, 9.Type, 10.In Desc
					dim_fields = [
						[self.doc.height_dia,"Height",1.5,55,
							self.doc.height_dia_inch,self.doc.inch_h,"","x",
							"Length","Yes"],
						[self.doc.width,"Width",1.5,55,self.doc.width_inch,
							self.doc.inch_w,"","x","Length","Yes"],
						[self.doc.length,"OAL",25,550,self.doc.length_inch,
							self.doc.inch_l,"","","Length","Yes"],
						[self.doc.a1, "Bevel Angle",0,31,"","","","\xb0",
							"Angle","Yes"]]
					spl_trt = ["TiN", "CRY", "None"] #allowed special treatment
				if (self.doc.is_rm == "Yes"):
					if (self.doc.base_material == "HSS"):
						spl_trt = ["Hard", "None"] #allowed special treatment
						dim_fields = [
							[self.doc.height_dia,"Height",2.5,150,
								self.doc.height_dia_inch,self.doc.inch_h,"","x",
								"Length","Yes"],
							[self.doc.width,"Width",2.5,150,self.doc.width_inch,
								self.doc.inch_w,"","","Length","Yes"],
							[self.doc.length,"OAL",0,0.001,self.doc.length_inch,
								self.doc.inch_l,"","","Length","Yes"],
							[self.doc.a1, "Bevel Angle",0,0.001,"","","","",
								"Angle","Yes"]]
					elif (self.doc.base_material == "Carbide"):
						spl_trt = ["None"] #allowed special treatment
						dim_fields = [
							[self.doc.height_dia,"Height",2.5,50,
								self.doc.height_dia_inch,self.doc.inch_h,"","x",
								"Length","Yes"],
							[self.doc.width,"Width",2.5,50,self.doc.width_inch,
								self.doc.inch_w,"","x","Length","Yes"],
							[self.doc.length,"OAL",0,400,self.doc.length_inch,
								self.doc.inch_l,"","","Length","Yes"],
							[self.doc.a1, "Bevel Angle",0,0.001,"","","","",
								"Angle","Yes"]]
				#H=W check
				self.fn_two_nos_compare("equal", dim_fields[0], dim_fields[1])
		
			else:
				webnotes.msgprint('{0}{1}{2}'.format("Tool Type Selected =",
					self.doc.tool_type, ", is not covered. Kindly contact \
					aditya@rigpl.com or Mr Aditya Duggal for further information"),
					raise_exception=1)

			self.fn_common_check()
			self.fn_integer_check(dim_fields) #limit check
			#Make Description, Web Description, Item Code, Concat, Concat1,
			#Item Name (in the above order only)
			self.doc.description,self.doc.web_long_description,self.doc.item_code,self.doc.concat,self.doc.concat1,self.doc.item_name = self.fn_gen_description(dim_fields, spl_trt, uniquel0, uniquel1)
################################################################################			
	def fn_gen_description(self, fds,trt,ul0, ul1):
		#This function generates the following:
		#Item Code, Description, Website Description, Web Specs,
		#Item Uniqueness check fields
		
		#ic_RM, ic_BM, ic_QLT, ic_TT, ic_ZN, ic_SP, ic_BR, ic_SN, ic_CD
		#D_RM, D_BM, D_BR, D_QLT, D_SPL, D_DT, D_TT, D_SZ, DZN
		#S1_RM
		
		if self.doc.is_rm == "Yes":
			ic_RM = "R"
			D_RM = "RM "
			Dw_RM = "Raw Material "
		else:
			ic_RM = ""
			D_RM = ""
			Dw_RM = ""
			
		if self.doc.base_material == "HSS":
			ic_BM = "H"
			D_BM = "HSS "
			Dw_BM = "High Speed Steel "
		elif self.doc.base_material == "Carbide":
			ic_BM = "C"
			D_BM = "Carb "
			Dw_BM = "Solid Carbide "
		else:
			msgprint("Please enter base material", raise_exception=1)
		
		ic_QLT = webnotes.conn.get_value("Quality", self.doc.quality , "code")
		D_QLT = webnotes.conn.get_value("Quality", self.doc.quality, 
			"description") + " "
		Dw_QLT = webnotes.conn.get_value("Quality", self.doc.quality, 
			"website_description") + " "
		
		ic_TT = webnotes.conn.get_value("Tool Type", self.doc.tool_type ,
			 "code")
		D_TT = webnotes.conn.get_value("Tool Type", self.doc.tool_type, 
			"description") + " "
		Dw_TT = webnotes.conn.get_value("Tool Type", self.doc.tool_type, 
			"website_description") + " "
		
		ic_ZN = self.fn_flutes(self.doc.no_of_flutes)
		
		ic_SP = self.fn_special_trt_check(trt)
		SPL = self.doc.special_treatment
		if SPL == 'CRY':
			if self.doc.quality == "H-3X":
				D_SPL = '{0}'.format("EC500 ")
				Dw_SPL = D_SPL
			else:
				D_SPL = SPL + " "
				Dw_SPL = "Cryogenically Treated "
		elif SPL == 'ACX' or SPL == 'Hard' or SPL == 'TiAlN' or SPL == 'TiN':
			D_SPL = '{0}{1}'.format(self.doc.special_treatment, " ")
			Dw_SPL = D_SPL
		else:
			D_SPL = '{0}'.format("")
			Dw_SPL = D_SPL
		
		ic_BR = webnotes.conn.get_value("Brand", self.doc.brand, "code")
		if ic_BR == "X": ic_BR = ""
		D_BR = '{0}{1}'.format(webnotes.conn.get_value("Brand", self.doc.brand,
			 "item_desc"), " ")
		Dw_BR = D_BR
		#old Serial no from Item Group
		ic_SN =  webnotes.conn.get_value("Item Group", "Carbide Tools" , 
			"serial_number")
		
		#new serial no from tool Type
		#ic_SN = webnotes.conn.get_value("Tool Type", self.doc.tool_type , 
		#	"serial_number")
			
		ic_check = '{0}{1}{2}{3}{4}{5}{6}'.format(ic_RM, ic_BM, 
			ic_QLT, ic_TT, ic_ZN, ic_SP, ic_BR)
		ic_inter = '{0}{1}{2}{3}{4}{5}{6}{7}'.format(ic_RM, ic_BM, 
			ic_QLT, ic_TT, ic_ZN, ic_SP, ic_BR, ic_SN)
		ic_CD = self.fn_check_digit(ic_inter)
		ic_code = '{0}{1}'.format(ic_inter, ic_CD)
		
		if (self.doc.item_code):
			ic_existing = self.doc.item_code[:(len(self.doc.item_code)-4)]
			#webnotes.msgprint(ic_existing)
			if ic_existing != ic_check:
				webnotes.msgprint("Change NOT ALLOWED since this would change \
					Item Code which is NOT POSSIBLE.\nKindly contact \
					Aditya Duggal for further details",
					raise_exception = 1)
		
		if self.doc.drill_type is None:
			D_DT = '{0}'.format("")
			Dw_DT = D_DT
		else:
			D_DT = '{0}{1}'.format(self.doc.drill_type, " ")
			Dw_DT = D_DT
		
		D_SZ = ""
		Dw_SZ = ""
################################################################################
			#Size Description Generation
################################################################################
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
						
		if (self.doc.no_of_flutes):
			D_ZN = '{0}{1}'.format(" Z= ", self.doc.no_of_flutes)
			Dw_ZN = '{0}{1}'.format(" Flutes= ", self.doc.no_of_flutes)
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
		
################################################################################
			#Unique Fields list which are in numbers
################################################################################
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
		return (D_Desc, Dw_Desc, ic_code, uc_c0, uc_c1, it_name)
################################################################################			
	def fn_next_string(self,s):
		#This function would increase the serial number by One following the
		#alpha-numeric rules as well
		if len(s) == 0:
			return '1'
		head = s[0:-1]
		tail = s[-1]
		if tail == 'Z':
			return self.next_string(head) + '0'
		if tail == '9':
			return head+'A'
		if tail == 'H':
			return head+'J'
		if tail == 'N':
			return head+'P'
		return head + chr(ord(tail)+1)
################################################################################
	def fn_integer_check(self,float):
		for i in range(0,len(float)):
			if not float[i][0]:
				float[i][0] = 0
				if float[i][0] < float[i][2] or float[i][0] >= float[i][3]:
					webnotes.msgprint('{0}{1}{2}{3}{4}{5}'.format(float[i][1],
					" entered should be between ", float[i][2],
					" (including) and ",float[i][3], " (excluding)"),
					raise_exception=1)
			else:
				if float[i][0] < float[i][2] or float[i][0] >= float[i][3]:
					webnotes.msgprint('{0}{1}{2}{3}{4}{5}'.format(float[i][1],
					" entered should be between ", float[i][2],
					" (including) and ",float[i][3], " (excluding)"),
					raise_exception=1)
################################################################################
	def fn_common_check(self):
			#Check if the BRAND selected is in unison with RM	
		if (self.doc.is_rm):
			if self.doc.is_rm != webnotes.conn.get_value ("Brand", 
				self.doc.brand, "is_rm"):webnotes.msgprint("Brand Selected \
				is NOT ALLOWED", raise_exception=1)

			#Check if the base material selected is in unison with the quality
		if self.doc.base_material != webnotes.conn.get_value("Quality", 
			self.doc.quality, "base_material"):webnotes.msgprint("Base \
			Material and Quality Combo is WRONG", raise_exception=1)
				
			#Check if the IS RM selected is in unison with the quality
		if (self.doc.is_rm):
			if self.doc.is_rm != webnotes.conn.get_value("Quality",
				 self.doc.quality, "is_rm"):webnotes.msgprint("RM-Quality \
				 Combo is WRONG", raise_exception=1)
################################################################################	
	def fn_two_nos_compare(self,type, d1, d2):
		if type == "equal":
			if d1[0] != d2[0]:
				webnotes.msgprint('{0}{1}{2}'.format(d1[1], 
				" should be equal to ", d2[1]), raise_exception=1)
		elif type == "greater":
			if d1[0] <= d2[0]:
				webnotes.msgprint('{0}{1}{2}'.format(d1[1], 
				" should be greater than ", d2[1]), raise_exception=1)
		else:
			if d1[0] < d2[0]:
				webnotes.msgprint('{0}{1}{2}'.format(d1[1], 
				" should be greater than or equal to ", d2[1]), 
				raise_exception=1)
################################################################################
	def fn_special_trt_check(self, spl):
		if not spl:
			if (self.doc.special_treatment) :
				webnotes.msgprint('{0}{1}{2}'.format("Special Treatment- ", 
			self.doc.special_treatment, " selected is not allowed"), 
			raise_exception=1)
		else:
			if self.doc.special_treatment not in spl:
				webnotes.msgprint('{0}{1}{2}'.format("Special Treatment- ", 
				self.doc.special_treatment, " selected is not allowed"), 
				raise_exception=1)
		return {
			"TiAlN": '1',
			"TiN": '2',
			"ACX": '3',
			"CRY": '4',
			"ALDURA": '5',
			"Hard": 'H',
		}.get(self.doc.special_treatment,"")
##############~Code to generate the letter based on Flutes~#####################
################################################################################
	def fn_flutes(self,flutes):
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
	def fn_check_digit(self,id_without_check):
	 
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
################################################################################
#This code is called when the item code is not generated.
	def autoname(self):
		self.custom_validate()
		#New Serial No from Tool Type
		#sn = webnotes.conn.get_value("Tool Type", self.doc.tool_type , 
		#	"serial_number")
		#nxt_sn = self.fn_next_string(sn)
		#webnotes.conn.set_value("Tool Type", self.doc.tool_type, 
		#	"serial_number", nxt_sn)
		
		#old Serial No from Item Group
		
		sn = webnotes.conn.get_value("Item Group", "Carbide Tools" , 
			"serial_number")
		nxt_sn = self.fn_next_string(sn)
		webnotes.conn.set_value("Item Group", "Carbide Tools", 
			"serial_number", nxt_sn)
		
		return super(CustomDocType, self).autoname()
################################################################################

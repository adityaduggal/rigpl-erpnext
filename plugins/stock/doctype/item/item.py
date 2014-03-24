# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import webnotes
from webnotes.model.doc import addchild

class CustomDocType(DocType):
        #This part of the code generates the alphanumeric series which
		#does not include 0,I, O (includes 1-9 and A-Z)
		#==============================
	def next_string(self,s):
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
		
		#Code to generate the letter based on Base Metal
		#====================
	def fn_base_metal(self,base_material):
		return {
			"HSS": 'H',
			"Carbide": 'C',
		}.get(base_material,"")	

		#Code to generate the letter based on Flutes
		#====================
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

		#Code to generate the letter based on Special Treatment
		#====================		
	def fn_special_treatment(self,treatment):
		if self.doc.is_rm == 'Yes':
			if treatment != "Hard" and treatment != "None":
				webnotes.msgprint("Treatment Selected is not Permitted for RM", raise_exception=1)
		else:
			if treatment == "Hard":
				webnotes.msgprint("Treatment Selected is not Permitted", raise_exception=1)
		return {
			"TiAlN": '1',
			"TiN": '2',
			"ACX": '3',
			"CRY": '4',
			"ALDURA": '5',
			"Hard": 'H',
		}.get(treatment,"")

		#Code to generate the letter based on RM
		#====================
	def fn_isrm(self,is_rm):
		return {
			"Yes": 'R',
		}.get(is_rm,"")
		
		#Code to Check the numeric fields
		#====================		
	def fn_float_check(self,float):
		if not float:
			float = 0
		else:
			if float >= 1000:
				webnotes.msgprint("Number entered should be less than 1000", 
					raise_exception=1)
			elif float < 0:
				webnotes.msgprint("Number entered should be more than Zero", 
					raise_exception=1)
	
	def fn_check_flutes (self,z):
		if z == "":
			webnotes.msgprint("Flutes Cannot be less than 1", raise_exception=1)
		elif z <1:
			webnotes.msgprint("Flutes Cannot be less than 1", raise_exception=1)
		elif z>20:
			webnotes.msgprint("Flutes cannot be more than 20", raise_exception=1)
	
	def fn_d1_d2 (self,d1,d2):
		if d1 < d2:
			if self.doc.tool_type != "SQEM" and self.doc.base_material != "HSS":
				webnotes.msgprint("D or H/D should be greater than W or D1", raise_exception=1)
		elif d1 == d2:
			if self.doc.tool_type != "Square" or self.doc.tool_type != "Mandrels":
				webnotes.msgprint("H/D and W equal only for Square Tools and Mandrels", raise_exception=1)
	
	def fn_length(self,l):
		if self.doc.is_rm == "Yes" and self.doc.base_material== "HSS":
			if l !=0:
				webnotes.msgprint("Length of HSS RM should be ZERO", raise_exception=1)
		else:
			if l ==0:
				webnotes.msgprint("Length cannot be ZERO", raise_exception=1)
	
	def fn_a1(self, a1):
		if a1 == "" :
			webnotes.msgprint("Some mandatory field missing", raise_exception=1)
	
	def fn_l1 (self,L,L1):
		if L <= L1:
			webnotes.msgprint("L1 should be less than L", raise_exception=1)
	
	def fn_l1_l2(self,L,L1,L2):
		if L <= (L1 + L2):
			webnotes.msgprint("L1+L2 should be less than L", raise_exception=1)
	
	def fn_ttbased_check(self, tt):
			# Count of Tool Type==1 below
		if tt == "Square":
			self.fn_d1_d2(self.doc.height_dia, self.doc.width)
			self.fn_length(self.doc.length)
			self.fn_a1(self.doc.a1)
			
			# Count of Tool Type==4 below
		elif tt=="Rectangular" or tt=="Mandrels" or tt=="Parting":
			self.fn_d1_d2(self.doc.width, self.doc.height_dia)
			self.fn_length(self.doc.length)
			self.fn_a1(self.doc.a1)

			# Count of Tool Type==8 below
		elif tt=="Ball Nose" or tt=="Drill" or tt=="Reamer" or tt=="SQEM" :
			self.fn_d1_d2(self.doc.height_dia, self.doc.d1)
			self.fn_a1(self.doc.a1)
			self.fn_length(self.doc.length)
			self.fn_length(self.doc.l1)
			self.fn_l1(self.doc.length, self.doc.l1)
			self.fn_check_flutes(self.doc.no_of_flutes)
			
			# Count of Tool Type==9 below
		elif tt=="Punches" :
			self.fn_d1_d2(self.doc.height_dia, self.doc.d1)
			self.fn_a1(self.doc.a1)
			self.fn_length(self.doc.length)
			self.fn_length(self.doc.l1)
			self.fn_l1(self.doc.length, self.doc.l1)

			# Count of Tool Type==10 below
		elif tt=="Centre Drill Type A":
			self.fn_d1_d2(self.doc.height_dia, self.doc.d1)
			self.fn_length(self.doc.length)
			self.fn_length(self.doc.l1)
			self.fn_a1(self.doc.a1)
			self.fn_l1(self.doc.length, self.doc.l1)
			self.fn_check_flutes(self.doc.no_of_flutes)
			
			# Count of Tool Type==11 below
		elif tt=="Centre Drill Type B":
			self.fn_d1_d2(self.doc.height_dia, self.doc.d1)
			self.fn_d1_d2(self.doc.d1, self.doc.d2)
			self.fn_length(self.doc.length)
			self.fn_length(self.doc.l1)
			self.fn_length(self.doc.l2)
			self.fn_a1(self.doc.a1)
			self.fn_a1(self.doc.a2)
			self.fn_a1(self.doc.a3)
			self.fn_l1(self.doc.length, self.doc.l1)
			self.fn_check_flutes(self.doc.no_of_flutes)
			
			# Count of Tool Type==12 below
		elif tt=="Centre Drill Type R":
			self.fn_d1_d2(self.doc.height_dia, self.doc.d1)
			self.fn_d1_d2(self.doc.d1, self.doc.d2)
			self.fn_length(self.doc.length)
			self.fn_a1(self.doc.a1)
			self.fn_a1(self.doc.a2)
			self.fn_a1(self.doc.a3)
			self.fn_a1(self.doc.r1)
			self.fn_l1(self.doc.length, self.doc.l1)
			self.fn_check_flutes(self.doc.no_of_flutes)

			# Count of Tool Type==13 below
		elif tt=="Punch Step3":
			self.fn_d1_d2(self.doc.height_dia, self.doc.d1)
			self.fn_length(self.doc.length)
			self.fn_a1(self.doc.a1)
			self.fn_a1(self.doc.a2)
			self.fn_l1(self.doc.length, self.doc.l1)
			self.fn_l1_l2(self.doc.length, self.doc.l1, self.doc.l2)

			# Count of Tool Type==14 below
		elif tt=="Round":
			self.fn_length(self.doc.length)
			self.fn_a1(self.doc.a1)

		#This function converts inch size
	def fn_inch_size(self, s):
		if (s):
			t = '{0}{1}'.format(s, '"')
		else:
			t = '{0}'.format("")
		return(t)

	def fn_mm_size(self,s):
		if (s):
			t = '{0:.4g}'.format(s)
			tw = '{0:.4g}{1}'.format(s,"mm")
		else:
			t = '{0}'.format("")
			tw = '{0}'.format("")
		return (t, tw)
	
		#Code to generate the Size Description based on the Tool Type
	def fn_size_desc(self,tooltype):
		if self.doc.inch_h==1:
			D = self.fn_inch_size(self.doc.height_dia_inch)
			Dweb = self.fn_inch_size(self.doc.height_dia_inch)
		else:
			D = self.fn_mm_size(self.doc.height_dia)[0]
			Dweb = self.fn_mm_size(self.doc.height_dia)[1]
			

		if self.doc.inch_w==1:
			W = self.fn_inch_size(self.doc.width_inch)
			Wweb = self.fn_inch_size(self.doc.width_inch)
		else:
			W = self.fn_mm_size(self.doc.width)[0]
			Wweb = self.fn_mm_size(self.doc.width)[1]

		if self.doc.inch_l==1:
			L = self.fn_inch_size(self.doc.length_inch)
		else:
			L = self.fn_mm_size(self.doc.length)[0]
		
		if self.doc.inch_d1==1:
			D1 = self.fn_inch_size(self.doc.d1_inch)
		else:
			D1 = self.fn_mm_size(self.doc.d1)[0]

		if self.doc.inch_l1==1:
			L1 = self.fn_inch_size(self.doc.l1_inch)
		else:
			L1 = self.fn_mm_size(self.doc.l1)[0]

		if self.doc.inch_d2==1:
			D2 = self.fn_inch_size(self.doc.d2_inch)
		else:
			D2 = self.fn_mm_size(self.doc.d2)[0]

		if self.doc.inch_l2==1:
			L2 = self.fn_inch_size(self.doc.l2_inch)
		else:
			L2 = self.fn_mm_size(self.doc.l2)[0]
		
		if not self.doc.a1:
			A1 = '{0}'.format("")
		else:
			A1 = '{0}{1}{2}'.format(" ",self.doc.a1,"\xb0")
			
		if not self.doc.a2:
			A2 = '{0}'.format("")
		else:
			A2 = '{0}{1}{2}'.format(" ",self.doc.a2,"\xb0")
			
		if not self.doc.a3:
			A3 = '{0}'.format("")
		else: 
			A3 = '{0}{1}{2}'.format(" ",self.doc.a3,"\xb0")
		
		R1 = self.fn_mm_size(self.doc.r1)[0]
		
		if tooltype == "Ball Nose" or tooltype == "SQEM" or tooltype == "Reamer":
			if D1 != D:
				SizeDesc = '{0}{1}{2}{3}{4}{5}{6}{7}{8}{9}{10}{11}'.format("\xd8",D1, "x", L1, 
					"x\xd8", D, "x", L, A1, A2,A3 ," ")
			else:
				SizeDesc = '{0}{1}{2}{3}{4}{5}{6}{7}{8}{9}'.format("\xd8",D1, "x", L1, 
					"x", L, A1, A2,A3 ," ")
		elif tooltype == "Drill":
			if D1 != D:
				SizeDesc = '{0}{1}{2}{3}{4}{5}{6}{7}{8}{9}{10}{11}{12}'.format("\xd8",D1, "x", L1, 
					"x\xd8", D, "x", L, " PA:", A1, A2,A3 ," ")
			else:
				SizeDesc = '{0}{1}{2}{3}{4}{5}{6}{7}{8}{9}{10}'.format("\xd8",D1, "x", L1,
					"x", L, " PA:", A1, A2,A3 ," ")
		
		elif tooltype == "Centre Drill Type A" or tooltype == "Centre Drill Type B" or tooltype == "Centre Drill Type R" :
			SizeDesc = '{0}{1}{2}{3}{4}{5}{6}{7}{8}'.format("\xd8",D1, " SH:\xd8", D, " PA:",A1, A2, A3, R1, " ")
		
		elif tooltype == "Square" or tooltype == "Rectangular" or tooltype == "Mandrels" or tooltype == "Parting" :
			if self.doc.length >0:
				SizeDesc = '{0}{1}{2}{3}{4}{5}{6}'.format(D, "x", W, "x", L, A1, " ")
				SizeDweb = '{0}{1}{2}{3}{4}{5}{6}'.format(Dweb, "x", Wweb, "x", L, A1, " ")
			else:
				SizeDesc = '{0}{1}{2}{3}'.format(D, "x", W, " ")
		
		elif tooltype == "Round" :
			if self.doc.length >0:
				SizeDesc = '{0}{1}{2}{3}{4}{5}'.format("\xd8", D, "x", L, A1, " ")
			else:
				SizeDesc = '{0}{1}{2}'.format("\xd8", D, " ")
			
		elif tooltype == "Punches" :
			SizeDesc = '{0}{1}{2}{3}{4}{5}{6}{7}{8}{9}'.format("\xd8", D, "x", L1,"  \xd8", D1, "x", L, A1, " ")
		
		elif tooltype == "Punch Step3" :
			SizeDesc = '{0}{1}{2}{3}{4}{5}{6}{7}{8}{9}{10}{11}{12}{13}{14}'.format("\xd8", D, "x", L1, " \xd8", D1, 
				"x", L2, " \xd8", D2, "x", L, A1, A2, " ")
				
		else:
			webnotes.msgprint("Unable to generate Size Description")
		return (SizeDesc)
	
	def fn_unique_float(self,s):
		if (s):
			if s == 0:
				t = '{0:.4f}'.format(0.0000)
			else:
				t = '{0:.4f}'.format(s)
		else:
			t = '{0:.4f}'.format(0.0000)
		return (t)
	
		#Code to generate the CHECK DIGIT
		#====================
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
						# use our formula this is the same as multiplying x 2 and
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

	def fn_add_item_website_specifications(self):
		web_specs = [d.label for d in self.doclist.get({"parentfield": "item_website_specification"})]
		if "H" not in web_specs:
			ch = addchild(self.doc, 'item_website_specification', 'Item Website Specification', self.doclist)
			ch.label = "H"
			ch.description = self.doc.height_dia

		#Validation based on various rules
		#====================
	def custom_validate(self):
		if self.doc.tool_type != "Others":
			Check = self.fn_float_check(self.doc.height_dia)
			Check = self.fn_float_check(self.doc.width)
			Check = self.fn_float_check(self.doc.length)
			Check = self.fn_float_check(self.doc.a1)
			Check = self.fn_float_check(self.doc.d1)
			Check = self.fn_float_check(self.doc.l1)
			Check = self.fn_float_check(self.doc.a2)
			Check = self.fn_float_check(self.doc.d2)
			Check = self.fn_float_check(self.doc.l2)
			Check = self.fn_float_check(self.doc.a3)
			Check = self.fn_float_check(self.doc.r1)
			
				#Check values based on the tool type
				#================================================================
			Check = self.fn_ttbased_check (self.doc.tool_type)
			
				#Check if the BRAND selected is in unison with RM
				#============================			
			if (self.doc.is_rm):
				if self.doc.is_rm != webnotes.conn.get_value ("Brand", self.doc.brand, "is_rm"):
					webnotes.msgprint("Brand Selected is NOT ALLOWED", raise_exception=1)

				#Check if the base material selected is in unison with the quality
				#============================
			if self.doc.base_material != webnotes.conn.get_value("Quality", self.doc.quality, "base_material"):
				webnotes.msgprint("Base Material and Quality Combo is WRONG", raise_exception=1)

				#Check if the IS RM selected is in unison with the quality
				#============================			
			if (self.doc.is_rm):
				if self.doc.is_rm != webnotes.conn.get_value("Quality", self.doc.quality, "is_rm"):
					webnotes.msgprint("Is RM and Quality Combo is WRONG", raise_exception=1)

				#Check for HEIGHT should always be less than WIDTH
				#============================
			if self.doc.width >0:
				if self.doc.height_dia > self.doc.width:
					webnotes.msgprint("HEIGHT cannot be more than WIDTH", raise_exception=1)
			
				#Check Dia Field
			
				#Check No of Flutes
				#============================
			if (self.doc.no_of_flutes) and self.doc.no_of_flutes >10:
				webnotes.msgprint("No of Flutes cannot be more than 10", raise_exception=1)


				#Check Overall Length and Other Lengths
				#============================
			if self.doc.length == 0 and self.doc.is_rm != "Yes":
				webnotes.msgprint("Overall Length cannot be ZERO", raise_exception=1)
			
			if self.doc.is_rm == "Yes":
				if self.doc.a1 >0:
					webnotes.msgprint("α1 Should be Zero in case of RM", raise_exception=1)
				if self.doc.special_treatment != "None" and self.doc.special_treatment != "Hard":
					webnotes.msgprint("Special Treatment has to be NONE or HARD in case of RM", raise_exception=1)
				if self.doc.length >0 and self.doc.base_material != "Carbide" :
					webnotes.msgprint ("Lenght has to be ZERO for HSS RM", raise_exception = 1)
					
			self.fn_add_item_website_specifications()
			self.generate_item_code()

	def generate_item_code(self):
		if self.doc.tool_type != "Others":
			#Code to generate automatic item code & description
			#============================
			BM = self.fn_base_metal(self.doc.base_material)		
			BMDesc = self.doc.base_material
			serial_no = webnotes.conn.get_value("Item Group", "Carbide Tools" , "serial_number")
			QLT = webnotes.conn.get_value("Quality", self.doc.quality , "code")
			QLTDesc = " " + webnotes.conn.get_value("Quality", self.doc.quality, "description") + " "
			QTLWebD = " " + webnotes.conn.get_value("Quality", self.doc.quality, "website_description") + " "
			TT = webnotes.conn.get_value("Tool Type", self.doc.tool_type, "code")
			TTDesc = webnotes.conn.get_value("Tool Type", self.doc.tool_type, "description") + " "
			TTWebD = webnotes.conn.get_value("Tool Type", self.doc.tool_type, "website_description") + " "
			Zn = self.fn_flutes(self.doc.no_of_flutes)
		
			if (self.doc.no_of_flutes):
				ZnDesc = '{0}{1}'.format(" Z= ", self.doc.no_of_flutes)
				ZnWebD = '{0}{1}'.format(" Flutes= ", self.doc.no_of_flutes)
			else:
				ZnDesc = '{0}'.format("")
				ZnWebD = '{0}'.format("")

			
			SPL = self.fn_special_treatment(self.doc.special_treatment)
			if SPL == '4':
				if self.doc.quality == "H-3X":
					SPLDesc = '{0}'.format(" EC500 ")
				else:
					SPLDesc = '{0}'.format(" Cryo ")
			elif SPL == '3' or SPL == '2' or SPL == '1' or SPL == '5' or SPL== 'H':
				SPLDesc = '{0}{1}{2}'.format(" ", self.doc.special_treatment, " ")
			else:
				SPLDesc = '{0}'.format("")
			
			RM = self.fn_isrm(self.doc.is_rm)
			if self.doc.is_rm =="Yes":
				RMDesc = "RM "
			else:
				RMDesc = ""
		 
			BRAND = webnotes.conn.get_value("Brand", self.doc.brand, "code")
			if BRAND =="X":
				BRAND = ""
		
			BRANDDesc = '{0}{1}'.format(" ", webnotes.conn.get_value("Brand", self.doc.brand, "item_desc"))
		
			if self.doc.drill_type is None:
				DTDesc = '{0}'.format("")
			else:
				DTDesc = '{0}{1}'.format(self.doc.drill_type, " ")
		
			SizeDesc =	self.fn_size_desc(self.doc.tool_type)
			SizeDweb =	self.fn_size_desc(self.doc.tool_type)
		
			desc_inter = '{0}{1}{2}{3}{4}{5}{6}{7}{8}'.format(RMDesc, BMDesc, BRANDDesc , QLTDesc, 
				SPLDesc, DTDesc, TTDesc, SizeDesc, ZnDesc)
			desc_web = '{0}{1}{2}{3}{4}{5}{6}{7}{8}'.format(RMDesc, BMDesc, BRANDDesc , QTLWebD, 
				SPLDesc, DTDesc, TTWebD, SizeDweb, ZnWebD)
			
			item_code_intermediate = '{0}{1}{2}{3}{4}{5}{6}{7}'.format(RM, BM, QLT, TT, Zn, SPL, 
				BRAND, serial_no)
		
			CD = self.fn_check_digit (item_code_intermediate)
		
				#below field concat is going to be used to check the integrity of data so that no one makes 2 codes for 
				#1 item.
			Du = self.fn_unique_float(self.doc.height_dia)
			Wu = self.fn_unique_float(self.doc.width)
			Lu = self.fn_unique_float(self.doc.length)
			A1u = self.fn_unique_float(self.doc.a1)
			R1u = self.fn_unique_float(self.doc.R1)
			D1u = self.fn_unique_float(self.doc.d1)
			L1u = self.fn_unique_float(self.doc.l1)
			D2u = self.fn_unique_float(self.doc.d2)
			L2u = self.fn_unique_float(self.doc.l2)
			A2u = self.fn_unique_float(self.doc.a2)
			A3u = self.fn_unique_float(self.doc.a3)
		
			self.doc.concat = '{0}{1}{2}{3}{4}{5}{6}{7}{8}{9}'.format(RM, BM, QLT, TT, Zn, SPL, BRAND, Du, Wu , Lu)
			self.doc.concat1 = '{0}{1}{2}{3}{4}{5}{6}{7}'.format(A1u, D1u, L1u, A2u, D2u, L2u, R1u, A3u)
			self.doc.concat2= ""
			self.doc.item_name=self.doc.item_code
				#update the image of the item
			self.doc.dim_image_list = webnotes.conn.get_value("File Data", {"attached_to_doctype": "Tool Type", 
				"attached_to_name": self.doc.tool_type}, "file_url")
			self.doc.description = desc_inter
			self.doc.web_long_description = desc_web
		
			# update incremented serial_no in item group
		
			# islocal check not required as this function will be called only in autoname
			if self.doc.fields.get("__islocal"):
				self.doc.item_code = '{0}{1}'.format(item_code_intermediate, CD)
				self.doc.item_name = '{0}{1}'.format(item_code_intermediate, CD)
					#increment serial_no value and assign to item_code
				next_serial_no = self.next_string(serial_no)
				webnotes.conn.set_value("Item Group", "Carbide Tools", "serial_number", next_serial_no)		#This part of the code generates the alphanumeric series which does not include 0,I, O (includes 1-9 and A-Z)

	def autoname(self):
		self.generate_item_code()
		return super(CustomDocType, self).autoname()

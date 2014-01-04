from __future__ import unicode_literals
import webnotes
from webnotes.utils import cint, cstr, flt
from webnotes.model.doc import Document
from webnotes.model.code import get_obj
from webnotes import msgprint, _

class CustomDocType(DocType):
    	#This part of the code generates the name for QUALITY
		#==============================	
	
	def fn_base_metal(self,base_material):
		return {
			"HSS": 'H',
			"Carbide": 'C',
		}.get(base_material,"")
	
	def fn_is_rm(self,is_rm):
		return {
			"Yes": 'R',
		}.get(is_rm,"")

	def custom_validate(self):
		RM = self.fn_is_rm(self.doc.is_rm)
		BM = self.fn_base_metal(self.doc.base_material)
		QLT = self.doc.material
		name_inter = '{0}{1}{2}{3}'.format(RM, BM, "-", QLT)
		
		if self.doc.fields.get("__islocal"):
			self.doc.name = name_inter
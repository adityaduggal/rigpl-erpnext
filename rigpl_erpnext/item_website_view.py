import frappe
from frappe.website.website_generator import WebsiteGenerator

class ItemWebsiteView(WebsiteGenerator):
	"""Website view for Item with custom template"""
	
	def get_context(self, context):
		"""Build context for item website view"""
		item = frappe.get_doc('Item', self.name)
		
		# Get parent item group for breadcrumbs
		breadcrumbs = [{'label': 'Home', 'url': '/'}]
		
		if item.item_group:
			try:
				ig_doc = frappe.get_doc('Item Group', item.item_group)
				parents = []
				current = ig_doc
				
				# Get parent hierarchy
				while current.parent_item_group:
					try:
						parent = frappe.get_doc('Item Group', current.parent_item_group)
						parents.insert(0, parent)
						current = parent
					except:
						break
				
				# Add breadcrumbs
				for parent in parents:
					pr = frappe.db.get_value('Item Group', parent.name, 'custom_route')
					breadcrumbs.append({
						'label': parent.item_group_name,
						'url': f"/{pr}" if pr else f"/item-group/{parent.name}"
					})
				
				# Add current item group
				igr = frappe.db.get_value('Item Group', item.item_group, 'custom_route')
				breadcrumbs.append({
					'label': ig_doc.item_group_name,
					'url': f"/{igr}" if igr else f"/item-group/{item.item_group}"
				})
			except Exception as e:
				frappe.log_error(f"Error building breadcrumbs: {e}")
		
		# Add item as last breadcrumb
		breadcrumbs.append({
			'label': item.item_name,
			'url': item.get_website_url()
		})
		
		context.update({
			'item': item,
			'item_code': item.name,
			'item_name': item.item_name,
			'description': item.description,
			'image': item.image,
			'breadcrumbs': breadcrumbs,
			'title': item.item_name,
			'no_cache': 1,
		})
		
		return context

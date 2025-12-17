import frappe
from urllib.parse import unquote

no_cache = 1

def get_context(context):
	"""
	Handles hierarchical product routes.
	"""
	path = unquote(frappe.request.path).strip("/")

	# 1. Check if the entire path maps to an Item Group's custom_route
	item_group = frappe.db.get_value(
		"Item Group",
		{"custom_route": path},
		["name", "item_group_name", "description", "image", "custom_route"],
		as_dict=True,
	)
	if item_group:
		return _get_item_group_context(context, item_group)

	# 2. Check if it's an Item (Template or Variant) via custom_route
	item_route = frappe.db.get_value("Item", {"custom_route": path}, "name")
	if item_route:
		item_doc = frappe.get_doc("Item", item_route)
		return _get_item_context(context, item_doc, path)

	# 3. Fallback: check based on item code at end of url
	path_parts = path.split("/")
	item_code = path_parts[-1]
	
	if frappe.db.exists("Item", item_code):
		item_doc = frappe.get_doc("Item", item_code)
		return _get_item_context(context, item_doc, path)

	# 404 if nothing matches
	raise frappe.PageNotFoundError(f"Product or Category not found: {path}")


def _get_item_group_context(context, item_group):
	"""Return context for item group listing page"""
	
	# Get Child Groups
	child_item_groups = frappe.get_all(
		"Item Group",
		filters={"parent_item_group": item_group["name"], "custom_published_in_website": 1},
		fields=["name", "item_group_name", "image", "custom_route", "description"],
		order_by="idx"
	)

	child_items = []
	if not child_item_groups:
		# Show Templates (Series) OR Standalone items
		# We exclude items that are variants of another item to keep the list clean
		child_items = frappe.get_all(
			'Item',
			filters={
				'item_group': item_group['name'],
				'variant_of': ('is', 'not set'),
				'disabled': 0,
				'custom_published_in_website': 1
			},
			fields=['name', 'item_name', 'item_code', 'image', 'description', 'custom_route'],
			limit_page_length=999
		)
	
	# Build breadcrumbs
	breadcrumbs = [{'label': 'Home', 'url': '/'}]
	try:
		ig_doc = frappe.get_doc('Item Group', item_group['name'])
		parents = []
		current = ig_doc
		while current.parent_item_group:
			try:
				parent = frappe.get_doc('Item Group', current.parent_item_group)
				parents.insert(0, parent)
				current = parent
			except:
				break
		for parent in parents:
			custom_route = frappe.db.get_value('Item Group', parent.name, 'custom_route')
			breadcrumbs.append({
				'label': parent.item_group_name,
				'url': f"/{custom_route}" if custom_route else f"/{parent.name}"
			})
		breadcrumbs.append({
			'label': item_group['item_group_name'],
			'url': f"/{item_group['custom_route']}"
		})
	except Exception as e:
		frappe.log_error(f"Error building breadcrumbs: {e}")
	
	context.update({
		'item_group': item_group,
		'child_item_groups': child_item_groups,
		'items': child_items,
		'item_group_name': item_group.get('item_group_name', ''),
		'description': item_group.get('description', ''),
		'image': item_group.get('image', ''),
		'title': item_group.get('item_group_name', ''),
		'breadcrumbs': breadcrumbs,
		'template': 'rigpl_erpnext/templates/product_page.html',
	})
	
	return context


def _get_item_context(context, item, path):
	"""Return context for individual item page"""
	breadcrumbs = [{'label': 'Home', 'url': '/'}]
	
	# Breadcrumb Logic
	try:
		if item.item_group:
			ig_doc = frappe.get_doc('Item Group', item.item_group)
			parents = []
			current = ig_doc
			while current.parent_item_group:
				try:
					parent = frappe.get_doc('Item Group', current.parent_item_group)
					parents.insert(0, parent)
					current = parent
				except:
					break
			for parent in parents:
				custom_route = frappe.db.get_value('Item Group', parent.name, 'custom_route')
				breadcrumbs.append({
					'label': parent.item_group_name,
					'url': f"/{custom_route}" if custom_route else f"/{parent.name}"
				})
			custom_route = frappe.db.get_value('Item Group', ig_doc.name, 'custom_route')
			breadcrumbs.append({
				'label': ig_doc.item_group_name,
				'url': f"/{custom_route}" if custom_route else f"/{ig_doc.name}"
			})
	except:
		pass
	
	breadcrumbs.append({
		'label': item.item_name,
		'url': f"/{path}"
	})

	variants_data = []
	attribute_headers = []
	item_attributes = []
	current_price_info = {}
	current_stock_qty = 0

	# --- CONDITION 1: IT IS A TEMPLATE / SERIES ---
	# We show the "Item List" (Variants Table)
	if item.has_variants:
		
		# Base Path for Links (Use current path as we are on the template page)
		parent_path_base = path

		variant_items = frappe.get_all(
			"Item",
			filters={"variant_of": item.name, "disabled": 0},
			fields=["name", "item_name", "item_code", "description"],
			order_by="idx asc, item_code asc"
		)

		if variant_items:
			# Get Headers
			attributes_meta = frappe.db.get_all("Item Variant Attribute", 
				filters={"parent": item.name}, 
				fields=["attribute"], 
				order_by="idx"
			)
			attribute_headers = [d.attribute for d in attributes_meta]

			for variant in variant_items:
				# Fetch Attributes
				var_attrs = frappe.db.get_all("Item Variant Attribute",
					filters={"parent": variant.name},
					fields=["attribute", "attribute_value"]
				)
				attr_map = {d.attribute: d.attribute_value for d in var_attrs}

				# Fetch Price
				price_info = frappe.db.get_value("Item Price",
					{"item_code": variant.name, "price_list": "Standard Selling"},
					["price_list_rate", "uom", "currency"],
					as_dict=True
				)
				if not price_info:
					price_info = frappe.db.get_value("Item Price",
						{"item_code": variant.name, "selling": 1},
						["price_list_rate", "uom", "currency"],
						as_dict=True
					)
				
				# Fetch Stock (Safe SQL)
				stock_data = frappe.db.sql("""
					SELECT SUM(actual_qty) FROM `tabBin` WHERE item_code = %s
				""", (variant.name))
				stock_qty = stock_data[0][0] if stock_data and stock_data[0][0] else 0

				# Construct URL
				variant_url = f"/{parent_path_base}/{variant.item_code}".replace("//", "/")

				variants_data.append({
					"name": variant.name,
					"item_code": variant.item_code,
					"item_name": variant.item_name,
					"attributes": attr_map,
					"price": price_info.price_list_rate if price_info else 0,
					"currency": price_info.currency if price_info else "₹",
					"uom": price_info.uom if price_info else "Nos",
					"stock_qty": stock_qty,
					"in_stock": stock_qty > 0,
					"url": variant_url
				})

	# --- CONDITION 2: IT IS A SPECIFIC ITEM / VARIANT ---
	# We show "Specifications" and "Single Cart" (No Table)
	else:
		# Fetch Attributes for the "Specifications" Table
		item_attributes = frappe.get_all("Item Variant Attribute", 
			filters={"parent": item.name},
			fields=["attribute", "attribute_value"],
			order_by="idx"
		)

		# Fetch Price
		current_price_info = frappe.db.get_value("Item Price",
			{"item_code": item.name, "price_list": "Standard Selling"},
			["price_list_rate", "currency", "uom"],
			as_dict=True
		)
		if not current_price_info:
			current_price_info = frappe.db.get_value("Item Price",
				{"item_code": item.name, "selling": 1},
				["price_list_rate", "currency", "uom"],
				as_dict=True
			)
		current_price_info = current_price_info or {}

		# Fetch Stock (Safe SQL)
		current_stock_data = frappe.db.sql("""
			SELECT SUM(actual_qty) FROM `tabBin` WHERE item_code = %s
		""", (item.name))
		current_stock_qty = current_stock_data[0][0] if current_stock_data and current_stock_data[0][0] else 0

	context.update({
		'item': item,
		'title': item.item_name,
		'breadcrumbs': breadcrumbs,
		'template': 'rigpl_erpnext/templates/item.html',
		
		# Template Page Data
		'variants': variants_data,
		'attribute_headers': attribute_headers,
		
		# Specific Item Page Data
		'item_attributes': item_attributes,
		'current_price_info': current_price_info,
		'current_stock_qty': current_stock_qty,
		'in_stock': current_stock_qty > 0
	})
	
	return context
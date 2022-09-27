frappe.provide( "erpnext.item" );

frappe.ui.form.on( "Item", {
	refresh: function ( frm ) { 
		erpnext.item.rig_setup_attributes_table( frm );
		erpnext.item.rig_setup_restriction_table( frm );
		erpnext.item.rig_setup_btns( frm );
	},
	onload: function ( frm ) {
		erpnext.item.rig_set_ivr_rest_attr( frm );
		erpnext.item.rig_set_attribute_queries( frm );

	}
} );

frappe.ui.form.on( "Item Variant Restrictions", {
	attribute: function ( frm, cdt, cdn ) {
		erpnext.item.rig_set_ivr_allowed_values( frm, cdt, cdn );
	},
	allowed_values: function ( frm, cdt, cdn ) {
		erpnext.item.rig_set_ivr_allowed_values( frm, cdt, cdn );
	},
	on_load_post_render: function ( frm, cdt, cdn ) {
		// var nrow = locals[ cdt ][ cdn ];
		frm.fields_dict.item_vairaint_restrictions.grid.wrapper.on( "focus", "input[data-fieldname='allowed_values'][data-doctype='Item Attribute Value']", function ( e ) {
			console.log( e.type );
			erpnext.item.rig_set_ivr_allowed_values( frm, cdt, cdn );
		} );
	},
} );

frappe.ui.form.on( "Item Variant Attribute", {
	on_load_post_render: function ( frm ) {
		erpnext.item.rig_set_ivr_rest_attr( frm );
	},
	attributes_add: function ( frm ) {
		erpnext.item.rig_set_ivr_rest_attr( frm );
	},
	attributes_remove: function ( frm ) {
		erpnext.item.rig_set_ivr_rest_attr( frm );
	},
} );

$.extend( erpnext.item, {
	rig_setup_btns: function ( frm ) {
		frm.add_custom_button( "New Variant with Restrictions", function () {
			erpnext.item.rig_make_new_variant_frm_restrictions();
		}, "Create" );
		frm.remove_custom_button( "Single Variant", "Create" );
		frm.remove_custom_button( "Multiple Variants", "Create" );
	},
	rig_setup_attributes_table: function ( frm ) {
		// Function to hide Fields in Attribtes Table if item is template then it hides variant fields
		// if item is variant then it hides template fields from Item Variant Attribute Table
		// below is the case when item is a variant
		var var_attr_fdnm = [ "attribute_value" ];
		var temp_attr_fdnm = [ "use_in_description", "prefix", "suffix", "from_range", "to_range", "increment" ];
		var attr_tbl = frm.fields_dict.attributes;
		var attr_tbl_gd = attr_tbl.grid;

		attr_tbl_gd.df.read_only = frm.doc.__islocal ? false : true;
		attr_tbl_gd.docfields.forEach( function ( field ) {
			field.read_only = frm.doc.__islocal ? false : true;
		} );
		if ( !frm.doc.has_variants && frm.doc.variant_of ) {
			attr_tbl_gd.docfields.forEach( function ( field ) {
				if ( temp_attr_fdnm.includes( field.fieldname ) ) {
					attr_tbl_gd.update_docfield_property( field.fieldname, "hidden", 1 );
					attr_tbl_gd.update_docfield_property( field.fieldname, "in_list_view", 0 );
				}
			} );
		}
		if ( frm.doc.has_variants === 1 && frm.doc.variant_based_on === "Item Attribute" ) {
			attr_tbl_gd.docfields.forEach( function ( field ) {
				if ( var_attr_fdnm.includes( field.fieldname ) ) {
					attr_tbl_gd.update_docfield_property( field.fieldname, "hidden", 1 );
					attr_tbl_gd.update_docfield_property( field.fieldname, "in_list_view", 0 );
				}
			} );
		}
		attr_tbl_gd.reset_grid();
	},
	rig_setup_restriction_table: function ( frm ) {
		var ivr_fds_not_used_in_items = [ "rename_field", "item_number" ];
		var ivr_gd = frm.fields_dict.item_variant_restrictions.grid;
		if ( frm.doc.doctype === "Item" ) {
			ivr_gd.docfields.forEach( function ( hd_fd ) {
				if ( ivr_fds_not_used_in_items.includes( hd_fd.fieldname ) ) {
					ivr_gd.update_docfield_property( hd_fd.fieldname, "hidden", 1 );
					ivr_gd.update_docfield_property( hd_fd.fieldname, "in_list_view", 0 );
				}
			} );
			ivr_gd.reset_grid();
		}
	},
	rig_set_ivr_allowed_values: function ( frm, cdt, cdn ) {
		//This function basically makes the allowed values field in IVR table Autocomplete
		// with options coming from the Attribute Tables for various options in that Attributes
		var me = this;
		var row = locals[ cdt ][ cdn ];
		if ( !row.attribute ) {
			frappe.throw( "First Select the Attribute Type in Row" );
		} else if ( row.is_numeric !== 1 && row.attribute ) {
			var all_vals = []; // All Attribute Values of an Attribute defined in Item Attributes Table
			var ivr_gd = frm.fields_dict.item_variant_restrictions.grid;
			var alw_val_fd = ivr_gd.fields_map.allowed_values;
			frappe.db.get_doc( "Item Attribute", row.attribute ).then( ivdt => {
				all_vals = this.rig_get_array_frm_chd_tbl( ivdt.item_attribute_values, "attribute_value");
			} );
		}
	},
	rig_get_array_frm_chd_tbl: function ( child_tbl, fd_nm ) {
		var chld_arry = [];
		Object.keys(child_tbl).forEach(function (i) {
			console.log(child_tbl[i]);
			chld_arry.push((child_tbl[ i ])[ fd_nm ]);
		});
		return chld_arry;
	},

	rig_set_ivr_rest_attr: function ( frm ) {
		if ( !frm.doc.attributes ) {
			frappe.throw( "First Add some Attributes before Selecting Restrictions" );
		} else if ( frm.doc.attributes.length < 1 ) {
			frappe.throw( "First Add some Attributes before Selecting Restrictions" );
		} else {
			frm.set_query( "attribute", "item_variant_restrictions", function ( doc, cdt, cdn ) {
				var rest_attr_lst = erpnext.item.rig_get_current_attr( frm );
				return { "filters": [ [ "Item Attribute", "name", "in", rest_attr_lst ] ] };
			} );
		}
	},
	rig_get_current_attr: function ( frm ) {
		var curr_attributes = [];
		frm.doc.attributes.forEach( function ( row ) {
			curr_attributes.push( row.attribute );
		} );
		return curr_attributes;
	},
	rig_set_attribute_queries: function ( frm ) {
		frm.set_query( "attribute", "attributes", function ( doc, cdt, cdn ) {
			return {
				"filters": [ [ "Item Attribute", "virtual", "=", 0 ] ]
			};
		} );
	},
	rig_get_numeric_attr: function ( frm ) {
		var me = this;
		var cur_attr = this.rig_get_current_attr( frm );
		frappe.call( {
			"async": false,
			"method": "frappe.client.get_list",
			"args": {
				"doctype": "Item Attribute",
				"filters": [
					[ "Item Attribute", "hidden", "=", 1 ],
					[ "Item Attribute", "name", "in", cur_attr ]
				],
				"fields": [
					"name", "update_from", "source", "short_name", "relation"
				]
			},
			"callback": function ( result ) {
				return result.message;
			}
		} );
	},
	
});
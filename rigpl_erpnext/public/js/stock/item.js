frappe.provide("erpnext.item");

frappe.ui.form.on("Item", {
    refresh: function(frm) {
        frm.__rig_variant_data = null;
        erpnext.item.rig_setup_btns( frm );
        erpnext.item.rig_setup_attributes_table( frm );
        erpnext.item.rig_setup_restriction_table( frm );
        /* Disable the attribute table if the item is saved */
        if (frappe.user.has_role("System Manager")) {
            frm.fields_dict.attributes.grid.df.read_only = frm.doc.__islocal ? false: true;
            frm.fields_dict.attributes.grid.docfields.forEach(function(field) {
                field.read_only = frm.doc.__islocal ? false: true;
            });
            frm.refresh_field("attributes");
        }
    },
	onload: function ( frm ) {
		erpnext.item.rig_set_ivr_rest_attr( frm );
		erpnext.item.rig_set_attribute_queries( frm );
	}
});

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
});

frappe.ui.form.on( "Item Variant Restrictions", {
	form_render: function ( frm, cdt, cdn ) {
		erpnext.item.rig_set_ivr_allowed_values( frm, cdt, cdn );
	},
	attribute: function ( frm, cdt, cdn ) {
		erpnext.item.rig_set_ivr_allowed_values( frm, cdt, cdn );
	},
} );

$.extend(erpnext.item, {
	rig_setup_btns: function ( frm ) {
		// Only our dialog makes variants of a template, so ERPNext's Create buttons are removed.
		if ( frm.doc.__islocal || !frm.doc.has_variants || frm.doc.variant_based_on !== "Item Attribute" ) return;
		frm.add_custom_button( __( "New Variant with Restrictions" ), function () {
			erpnext.item.rig_make_new_variant_frm_restrictions( frm );
		}, __( "Create" ) );
		frm.remove_custom_button( "Single Variant", "Create" );
		frm.remove_custom_button( "Multiple Variants", "Create" );
	},
	rig_setup_attributes_table: function ( frm ) {
		/*
        Function to hide Fields in Attribtes Table if item is template then it hides variant fields
		if item is variant then it hides template fields from Item Variant Attribute Table
		below is the case when item is a variant
        */
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
		var ivr_fds_used = [ "attribute", "is_numeric", "allowed_values", "rule"];
		var ivr_gd = frm.fields_dict.item_variant_restrictions.grid;
		if ( frm.doc.doctype === "Item" ) {
			ivr_gd.docfields.forEach( function ( hd_fd ) {
				if ( ivr_fds_used.includes( hd_fd.fieldname ) ) {
					ivr_gd.update_docfield_property( hd_fd.fieldname, "hidden", 0 );
					ivr_gd.update_docfield_property( hd_fd.fieldname, "in_list_view", 1);
				} else {
                    ivr_gd.update_docfield_property( hd_fd.fieldname, "hidden", 1 );
                    ivr_gd.update_docfield_property( hd_fd.fieldname, "in_list_view", 0);
                }
			} );
			ivr_gd.reset_grid();
		}
	},
	rig_set_ivr_allowed_values: function ( frm, cdt, cdn ) {
		// Suggest the values of the row's attribute in Allowed Values
		var row = locals[ cdt ][ cdn ];
		var grid_row = frm.fields_dict.item_variant_restrictions.grid.grid_rows_by_docname[ cdn ];
		var field = grid_row && grid_row.grid_form && grid_row.grid_form.fields_dict.allowed_values;
		if ( !row.attribute || cint( row.is_numeric ) || !field || !field.$input ) return;
		erpnext.item.rig_get_variant_dialog_data( frm ).then( function ( data ) {
			var values = data.values[ row.attribute ] || [];
			var awesomplete = field.$input.data( "awesomplete_obj" );
			if ( awesomplete ) awesomplete.destroy();
			field.$input.data( "awesomplete_obj", new Awesomplete( field.$input[ 0 ], {
				list: values,
				minChars: 0,
				filter: Awesomplete.FILTER_STARTSWITH,
			} ) );
			field.$input.off( "awesomplete-selectcomplete" ).on( "awesomplete-selectcomplete", function ( e ) {
				field.set_value( e.originalEvent.text.value );
			} );
		} );
	},
	rig_set_attribute_queries: function ( frm ) {
		frm.set_query( "attribute", "attributes", function ( doc, cdt, cdn ) {
			return {
				"filters": [ [ "Item Attribute", "virtual", "=", 0 ] ]
			};
		} );
	},
	rig_set_ivr_rest_attr: function ( frm ) {
        var message = "First Add some Attributes before Selecting Restrictions";
		if ( !frm.doc.attributes ) {
			frappe.throw(message);
		} else if ( frm.doc.attributes.length < 1 ) {
			frappe.throw( message);
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
	rig_get_variant_dialog_data: function ( frm ) {
		// One call per form load: values, linked size fields with their UOMs, and UOM factors
		if ( !frm.__rig_variant_data || frm.__rig_variant_data_for !== frm.doc.name ) {
			frm.__rig_variant_data_for = frm.doc.name;
			frm.__rig_variant_data = frappe.call( {
				method: "rigpl_erpnext.utils.attribute_query.get_variant_dialog_data",
				args: { template: frm.doc.name },
			} ).then( function ( r ) {
				return r.message;
			} );
		}
		return frm.__rig_variant_data;
	},
	rig_parse_number: function ( text ) {
		// "4.5", "3", "3/16" or "1+1/2" (the format of the inch values)
		var s = ( text + "" ).trim(), m;
		if ( /^\d+(\.\d+)?$/.test( s ) ) return flt( s );
		m = s.match( /^(?:(\d+)\+)?(\d+)\/(\d+)$/ );
		if ( m && cint( m[ 3 ] ) ) return cint( m[ 1 ] || 0 ) + cint( m[ 2 ] ) / cint( m[ 3 ] );
		frappe.throw( __( "Value {0} is not a number. Use 4.5, 3/16 or 1+1/2.", [ s ] ) );
	},
	rig_uom_factor: function ( factors, from_uom, to_uom ) {
		if ( from_uom === to_uom ) return 1;
		if ( factors[ from_uom ] && factors[ from_uom ][ to_uom ] ) return factors[ from_uom ][ to_uom ];
		if ( factors[ to_uom ] && factors[ to_uom ][ from_uom ] ) return 1 / factors[ to_uom ][ from_uom ];
		return null;
	},
	rig_variant_dialog_fields: function ( frm, data ) {
		var fields = [], created = {};
		frm.doc.attributes.forEach( function ( row ) {
			var link = Object.keys( data.links ).find( function ( name ) {
				return data.links[ name ].uoms.hasOwnProperty( row.attribute );
			} );
			var range = row.numeric_values ? __( "Min Value: {0}, Max Value: {1}, in Increments of: {2}",
				[ row.from_range, row.to_range, row.increment ] ) : "";
			if ( link ) {
				// One Data field for all the UOMs of a size (d1 for d1_mm and d1_inch)
				if ( created[ link ] || !row.use_in_description ) return;
				created[ link ] = true;
				fields.push( { label: link + " (" + row.field_name + ")", fieldname: link, reqd: 1, fieldtype: "Data", description: range } );
				return;
			}
			var field = { label: row.attribute + " (" + row.field_name + ")", fieldname: row.attribute, reqd: 1, description: range };
			if ( row.numeric_values ) {
				fields.push( Object.assign( field, { fieldtype: "Float" } ) );
				return;
			}
			var options = erpnext.item.rig_allowed_values( frm, row.attribute );
			if ( !options.length ) options = data.values[ row.attribute ] || [];
			Object.assign( field, { fieldtype: "Select", options: options } );
			if ( options.length === 1 ) Object.assign( field, { default: options[ 0 ], read_only: 1, hidden: 1 } );
			fields.push( field );
		} );
		return fields;
	},
	rig_allowed_values: function ( frm, attribute ) {
		var allowed = [];
		frappe.utils.filter_dict( frm.doc.item_variant_restrictions || [], { "attribute": attribute } ).forEach( function ( d ) {
			if ( d.allowed_values ) allowed.push( d.allowed_values );
		} );
		return allowed;
	},
	rig_setup_uom_button: function ( frm, d, data, link, selected_uom ) {
		// The UOM dropdown in front of a size field. It sets selected_uom[link].
		var field = d.fields_dict[ link ], info = data.links[ link ];
		var target = field.$input.parent(), menu = $( "<ul class=\"dropdown-menu\"></ul>" );
		var button = $( "<div class=\"input-group-btn\"><button type=\"button\" class=\"btn btn-default dropdown-toggle\" data-toggle=\"dropdown\" aria-haspopup=\"true\" aria-expanded=\"false\"></button></div>" );
		var select_uom = function ( attribute ) {
			var uom = info.uoms[ attribute ];
			selected_uom[ link ] = uom;
			button.find( "button" ).text( uom );
			var awesomplete = field.$input.data( "awesomplete_obj" );
			if ( awesomplete ) awesomplete.destroy();
			field.$input.removeData( "awesomplete_obj" );
			var allowed = erpnext.item.rig_allowed_values( frm, attribute );
			var list = allowed.length ? allowed : ( data.values[ attribute ] || [] );
			if ( list.length ) {
				field.$input.data( "awesomplete_obj", new Awesomplete( field.$input[ 0 ], {
					list: list, minChars: 0, filter: Awesomplete.FILTER_STARTSWITH,
				} ) );
			}
		};
		Object.keys( info.uoms ).forEach( function ( attribute ) {
			var option = $( "<li><a class=\"dropdown-item\"></a></li>" );
			option.find( "a" ).text( info.uoms[ attribute ] ).on( "click", function () {
				select_uom( attribute );
			} );
			menu.append( option );
		} );
		button.find( "button" ).text( info.source );
		button.append( menu ).prependTo( target );
		target.addClass( "input-group" ).removeAttr( "style" );
		field.$input.on( "awesomplete-selectcomplete", function ( e ) {
			field.parse_validate_and_set_in_model( e.originalEvent.text.value );
		} );
		var default_attribute = Object.keys( info.uoms ).find( function ( attribute ) {
			return info.uoms[ attribute ] === info.default_uom;
		} );
		if ( default_attribute ) select_uom( default_attribute );
	},
	rig_convert_linked_sizes: function ( frm, data, args, selected_uom ) {
		// Replace each size field (d1) with its attributes (d1_mm, d1_inch) in their UOMs
		var numeric = {};
		frm.doc.attributes.forEach( function ( row ) {
			numeric[ row.attribute ] = cint( row.numeric_values );
		} );
		Object.keys( args ).filter( function ( key ) {
			return data.links.hasOwnProperty( key );
		} ).forEach( function ( link ) {
			var val = ( args[ link ] + "" ).trim(), from_uom = selected_uom[ link ], uoms = data.links[ link ].uoms;
			if ( !from_uom ) frappe.throw( __( "Select the {0} of {1} first", [ data.links[ link ].source, link ] ) );
			var base = erpnext.item.rig_parse_number( val );
			Object.keys( uoms ).forEach( function ( attribute ) {
				var to_uom = uoms[ attribute ], factor;
				if ( to_uom === from_uom ) {
					args[ attribute ] = val.indexOf( "/" ) === -1 ? flt( val ) : val;
					return;
				}
				factor = erpnext.item.rig_uom_factor( data.factors, from_uom, to_uom );
				if ( !numeric[ attribute ] || !factor ) {
					frappe.throw( __( "{0} cannot be calculated from {1}. Enter {2} in {3}.",
						[ attribute, from_uom, link, to_uom ] ) );
				}
				args[ attribute ] = flt( ( base * factor ).toFixed( cint( frappe.defaults.get_global_default( "float_precision" ) ) || 3 ) );
			} );
			delete args[ link ];
		} );
	},
	rig_check_restriction_rules: function ( frm, args ) {
		// The rules (e.g. "d1_mm < w1_mm") come from the template, which only Item editors change.
		var rules = {}, msg = [];
		frappe.utils.filter_dict( frm.doc.item_variant_restrictions || [], { "is_numeric": 1 } ).forEach( function ( d ) {
			if ( !d.rule ) return;
			if ( !rules.hasOwnProperty( d.attribute ) ) rules[ d.attribute ] = [];
			rules[ d.attribute ].push( d.rule );
		} );
		var names = Object.keys( args ).sort( function ( a, b ) {
			return b.length - a.length;
		} ).map( function ( name ) {
			return name.replace( /[.*+?^${}()|[\]\\]/g, "\\$&" );
		} );
		var name_re = new RegExp( "(^|[^\\w])(" + names.join( "|" ) + ")(?![\\w])", "g" );
		Object.keys( rules ).forEach( function ( attribute ) {
			if ( !args.hasOwnProperty( attribute ) ) return;
			rules[ attribute ].forEach( function ( rule ) {
				var js = rule.replace( name_re, function ( m, before, name ) {
					return before + "args[" + JSON.stringify( name ) + "]";
				} );
				var ok;
				try {
					ok = new Function( "args", "return (" + js + ");" )( args );
				} catch ( e ) {
					ok = false;
				}
				if ( !ok ) msg.push( __( "The rule \"{0}\" for the field \"{1}\" is not met", [ rule, attribute ] ) );
			} );
		} );
		if ( msg.length ) frappe.throw( msg.join( "<br>" ) );
	},
	rig_make_variant: function ( frm, d, args ) {
		Object.keys( args ).forEach( function ( attribute ) {
			args[ attribute ] = args[ attribute ] + "";
		} );
		frappe.call( {
			method: "erpnext.controllers.item_variant.get_variant",
			args: { "template": frm.doc.name, "args": args },
			callback: function ( r ) {
				if ( r.message ) {
					var variant = r.message;
					var msgprint_dialog = frappe.msgprint( __( "Item Variant {0} already exists with same attributes",
						[ repl( "<a href=\"/app/item/%(item_encoded)s\" class=\"strong variant-click\">%(item)s</a>", {
							item_encoded: encodeURIComponent( variant ),
							item: frappe.utils.escape_html( variant ),
						} ) ]
					) );
					msgprint_dialog.hide_on_page_refresh = true;
					msgprint_dialog.$wrapper.find( ".variant-click" ).on( "click", function () {
						d.hide();
					} );
					return;
				}
				d.hide();
				frappe.call( {
					method: "erpnext.controllers.item_variant.create_variant",
					args: { "item": frm.doc.name, "args": args },
					callback: function ( r ) {
						var doclist = frappe.model.sync( r.message );
						frappe.set_route( "Form", doclist[ 0 ].doctype, doclist[ 0 ].name );
					}
				} );
			}
		} );
	},
	rig_make_new_variant_frm_restrictions: function ( frm ) {
		erpnext.item.rig_get_variant_dialog_data( frm ).then( function ( data ) {
			var selected_uom = {};
			var d = new frappe.ui.Dialog( {
				title: __( "Make Variant Based on Restrictions" ),
				fields: erpnext.item.rig_variant_dialog_fields( frm, data ),
			} );
			Object.keys( d.fields_dict ).forEach( function ( fieldname ) {
				if ( data.links.hasOwnProperty( fieldname ) ) {
					erpnext.item.rig_setup_uom_button( frm, d, data, fieldname, selected_uom );
				}
			} );
			d.set_primary_action( __( "Make" ), function ( args ) {
				if ( !args ) return;
				erpnext.item.rig_convert_linked_sizes( frm, data, args, selected_uom );
				erpnext.item.rig_check_restriction_rules( frm, args );
				erpnext.item.rig_make_variant( frm, d, args );
			} );
			d.show();
		} );
	},
    toggle_attributes: function(frm) {
        frm.toggle_display("attributes", frm.doc.has_variants || frm.doc.variant_of);
        frm.fields_dict.attributes.grid.toggle_reqd("attribute_value", frm.doc.variant_of ? 1 : 0);
        frm.fields_dict.attributes.grid.set_column_disp("attribute_value", frm.doc.variant_of ? 1 : 0);
    }
});
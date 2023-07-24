frappe.provide("erpnext.item");

frappe.ui.form.on("Item", {
    refresh: function(frm) {
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

$.extend(erpnext.item, {
	rig_setup_btns: function ( frm ) {
        // Function to add and remove buttons from the Item Form
		frm.add_custom_button( "New Variant with Restrictions", function () {
			erpnext.item.rig_make_new_variant_frm_restrictions();
		}, "Create" );
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
		/*This function basically makes the allowed values field in IVR table Autocomplete
		with options coming from the Attribute Tables for various options in that Attributes*/
		var me = this;
		var row = locals[ cdt ][ cdn ];
		if ( !row.attribute ) {
			frappe.throw( "First Select the Attribute Type in Row" );
		} else if ( row.is_numeric !== 1 && row.attribute ) {
			var all_vals = []; // All Attribute Values of an Attribute defined in Item Attributes Table
			var ivr_gd = frm.fields_dict.item_variant_restrictions.grid;
			var alw_val_fd = ivr_gd.fields_map.allowed_values;
            
            /* Below code is not working for adding the suggestion in autocomplete field for Allowed Values
            /////////////////////////////////////////////////

            $(alw_val_fd.input_area).addClass("ui-front");
            alw_val_fd.$input.autocomplete({
                minChars: 0,
                minLength: 0,
                source: function(request, response) {
                    frappe.call({
                        method: "frappe.client.get_list",
                        args: {
                            doctype: "Item Attribute Value",
                            filters: [
                                ["parent", "=", alw_val_fd.doc.attribute],
                                ["attribute_value", "like", request.term + "%"]
                            ],
                            fields: ["attribute_value"],
                            "parent": frm.doctype
                        },
                        callback: function(res) {
                            response($.map(res.message, function(d) {
 return d.attribute_value;
}));
                        }
                    });
                },
                select: function(event, ui) {
                    alw_val_fd.$input.val(ui.item.value);
                    alw_val_fd.$input.trigger("change");
                }
            });

            /////////////////////////////////////////////////
            */
		}
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
    get_hidden_fields: function() {
        var ret = {}, cur_attrs = [];
        cur_frm.doc.attributes.forEach(function(d) {
            cur_attrs.push(d.attribute);
        });
        frappe.call({
            "async": false,
            "method": "frappe.client.get_list",
            "args": {
                "doctype": "Item Attribute",
                "filters": [
                    ["Item Attribute", "hidden", "=", 1],
                    ["Item Attribute", "name", "in", cur_attrs]
                ],
                fields: [
                    "name", "update_from", "source", "relation"
                ]
            },
            "callback": function(res) {
                (res.message || []).forEach(function(r) {
                    var only_allowed, options = [] ;
                    if (!ret.hasOwnProperty(r.update_from)) {
                        ret[r.update_from] = {};
                        ret[r.update_from]["source"] = r.source;
                        ret[r.update_from]["options"] = {};
                    }
                    ret[r.update_from][r.name] = r.relation;
                    ret[r.name] = r.update_from;
                    ret["lookup"] = r.update_from;
                    only_allowed = frappe.utils.filter_dict(cur_frm.doc.item_variant_restrictions, {"attribute": r.name});
                    (only_allowed || []).forEach(function(d) {
                        options.push(d.attribute);
                    });
                    if (!options.length) {
                        frappe.call({
                            "async": false,
                            "method": "frappe.client.get_list",
                            "args": {
                                "doctype": "Item Attribute Value",
                                "parent": "Item Attribute",
                                "filters": [
                                    ["Item Attribute Value", "parent", "=", r.name]
                                ],
                                "fields": ["attribute_value"],
                                "limit_page_length": 500
                            },
                            "callback": function(res) {
                                (res.message || []).forEach(function(r) {
                                    options.push(r.attribute_value);
                                });
                            }
                        });
                    }
                    ret[r.update_from]["options"][r.name] = options;
                });
            }
        });
        return ret;
    },
    get_conversion_factors: function(from_uom, to_uom) {
        var ret;
        frappe.call({
            "async": false,
            "method": "rigpl_erpnext.utils.attribute_query.get_uom_factors",
            "args": {
                "from_uom": from_uom,
                "to_uom": to_uom
            },
            "callback": function(res) {
                ret = res.message;
            }
        });
        return ret;
    },
    rig_make_new_variant_frm_restrictions: function(doc) {
        var fields = [], hidden_fields = this.get_hidden_fields(doc);
        for (var i=0;i< cur_frm.doc.attributes.length;i++) {
            var row = cur_frm.doc.attributes[i], field, link_fld;
            if (!hidden_fields.hasOwnProperty(row.attribute)) {
                // Case when the attribute is not in hidden fields
                field = {
                    "label": (row.attribute + " ("+ row.field_name + ")"),
                    "fieldname": row.attribute,
                    "reqd": 1,
                    "fieldtype": row.numeric_values ? "Float": "Select",
                    "description": row.numeric_values ?  "Min Value: "+ row.from_range +" , Max Value: "+ row.to_range +", in Increments of: "+ row.increment : ""
                };
                if (field.fieldtype==="Select") {
                    var filters = [
                            ["parent", "=", row.attribute],
                    ], allowed = [], options = [];
                    frappe.utils.filter_dict(cur_frm.doc.item_variant_restrictions, {"attribute": row.attribute}).forEach(function(d) {
                        if (d.allowed_values) allowed.push(d.allowed_values);
                    });
                    if (allowed.length) {
                        options = options.concat(allowed);
                    } else {
                        frappe.call({
                            "method": "frappe.client.get_list",
                            "async": false,
                            "args": {
                                "doctype": "Item Attribute Value",
                                "parent": "Item Attribute",
                                "filters": filters,
                                "fields": ["attribute_value"]
                            },
                            "callback": function(res) {
                                res.message.forEach(function(d) {
                                    options.push(d.attribute_value);
                                });
                            }
                        });
                    }
                    field.options = options;
                    if (options.length === 1) {
                        field.default = options[0];
                        field.read_only = 1;
                        field.hidden = 1;
                    }
                    fields.push(field);
                }
            } else if (!hidden_fields[hidden_fields[row.attribute]].created && row.use_in_description) {
                link_fld = hidden_fields[row.attribute]; /*link_fld is the virtual number for conversion 
                of UoM between different UoMs */
                field = {
                    "label": (link_fld + " ("+ row.field_name + ")"),
                    "fieldname": link_fld,
                    "reqd": 1,
                    "fieldtype": "Data",
                    "description": row.numeric_values ?  "Min Value: "+ row.from_range +" , Max Value: "+ row.to_range +", in Increments of: "+ row.increment : ""
                };
                hidden_fields[link_fld].created = true;
                fields.push(field);
            }
        }
        var d = new frappe.ui.Dialog({
            title: __("Make Variant Based on Restrictions"),
            fields: fields
        });
        Object.keys(d.fields_dict).forEach(function(fieldname) {
            if (d.fields_dict[fieldname].df.fieldtype !== "Data") return;

            var field = d.fields_dict[fieldname],
                target = field.$input.parent(),
                options = $("<ul class=\"dropdown-menu\"></ul>");

            Object.keys(hidden_fields[fieldname]).forEach(function(key) {
                if (in_list(["created", "source", "options"], key)) return;

                var option = $(repl("<li><a data-option=\"%(0)s\">%(0)s</a></li>", [hidden_fields[fieldname][key]]));
                option.find("a").on("click", function(evt) {
                    //evt.preventDefault();
                    var text = options.parent().find("button").text();
                    if (text === $(this).text()) return;
                    options.parent().find("button").text($(this).text());

                    if (field.$input.data("awesomplete_obj")) field.$input.data("awesomplete_obj").destroy();
                    if ((hidden_fields[fieldname].options[key]||"").length) {
                        field.$input.data("awesomplete_obj", new Awesomplete(field.$input[0], {
                            list: hidden_fields[fieldname].options[key],
                            minChars: 0,
                            filter: Awesomplete.FILTER_STARTSWITH
                        }));
                        field.$input.on("awesomplete-select", function(e) {
                            var awe = field.$input.data("awesomplete_obj");
                            field.parse_validate_and_set_in_model(e.originalEvent.text.value);
                        });
                    }
                });
                options.append(option);
            });

            $(frappe.format("<div class=\"input-group-btn\">\
                 <button type=\"button\" class=\"btn btn-default dropdown-toggle\" data-toggle=\"dropdown\" aria-haspopup=\"true\" data-fieldname=\"{1}\" aria-expanded=\"false\">{0}<span class=\"caret\"></span></button>\
              </div>", __([hidden_fields[fieldname].source, fieldname]))).append(options).prependTo(target);
            target.addClass("input-group").removeAttr("style");

            field.$input.on("change", function(evt) {
                if (!field.$input.val().length) return;
                var uom = options.parent().find("button").text();
                if (uom===hidden_fields[fieldname].source) {
                    field.$input.val("");
                    frappe.throw(frappe.format("Select the \"{0}\" of the field \"{1}\"\", first!", [hidden_fields[fieldname].source, fieldname]));
                }
            });
        });


        d.set_primary_action(__("Make"), function(args) {
                        var rules = {}, eval_in_context = (js) => {
                            Object.keys(args).forEach(k => {
                               js = js.replace(k, "args." + k);
                            });
                            return eval(js);
                        };
            if (!args) return;

            frappe.utils.filter_dict(cur_frm.doc.item_variant_restrictions, {"is_numeric": 1}).forEach(function(d) {
                if (!rules.hasOwnProperty(d.attribute)) rules[d.attribute] = [];
                rules[d.attribute].push(d.rule);
            });
            Object.keys(args).filter(function(key) {
 return hidden_fields.hasOwnProperty(key); 
}).forEach(function(key) {
                var val = args[key], base, targets = Object.keys(hidden_fields[key]).filter(function(k) {
 return !in_list(["created", "source", "options"], k);
});
                try {
                    base = eval(val);
                } catch ( e ) {
                    frappe.throw(repl("Failed to decode the value \"%(0)s\"", {"0": val}));
                }
                targets.forEach(function(tgt) {
                    var uom = Object.keys(hidden_fields[d.fields_dict[key].df.fieldname]).filter((k) => {
                            return k.indexOf(key + "_") === 0;
                        }).map((k) => {
                            return hidden_fields[key][k];
                        })[0],
                        tgt_uom = hidden_fields[key][tgt],
                        factors = (uom && tgt_uom) && erpnext.item.get_conversion_factors(uom, tgt_uom);
                    if (uom === tgt_uom) {
                        args[tgt] = val.indexOf("/") === -1 ? flt(val) : val;
                    } else if (factors && factors.rgt) {
                        args[tgt] = flt((base * factors.rgt).toFixed(frappe.defaults.get_global_default("float_precision")));
                    } else {
                        args[tgt] = cint(args[key]) || args[key];
                    }
                });
                delete args[key];
            });

            Object.keys(args).forEach(function(attribute) {
                if (!rules.hasOwnProperty(attribute)) return;
                var msg = [], out;
                for (var i=0, j=rules[attribute].length; i < j; i++) {
                    out = eval_in_context.call(args, rules[attribute][i]);
                    if (!out) {
                        msg.push(repl("Unable for ensure the rule \"%(1)s\" for the field \"%(0)s\"", {
                            "0": attribute, "1": rules[attribute][i]}));
                    }
                }
                if (msg.length) {
                    frappe.throw(msg.join("<br>"));
                }
            });
            Object.keys(args).forEach(function(attribute) {
 args[attribute] = args[attribute] + "";
});
            frappe.call({
                method: "erpnext.controllers.item_variant.get_variant",
                args: {
                    "template": cur_frm.doc.name,
                    "args": args
                },
                callback: function(r) {
                    // returns variant item
                    if (r.message) {
                        var variant = r.message;
                        var msgprint_dialog = frappe.msgprint(__("Item Variant {0} already exists with same attributes",
                            [repl("<a href=\"#Form/Item/%(item_encoded)s\" class=\"strong variant-click\">%(item)s</a>", {
                                item_encoded: encodeURIComponent(variant),
                                item: variant
                            })]
                        ));
                        msgprint_dialog.hide_on_page_refresh = true;
                        msgprint_dialog.$wrapper.find(".variant-click").on("click", function() {
                            d.hide();
                        });
                    } else {
                        d.hide();
                        frappe.call({
                            method: "erpnext.controllers.item_variant.create_variant",
                            args: {
                                "item": cur_frm.doc.name,
                                "args": args
                            },
                            callback: function(r) {
                                var doclist = frappe.model.sync(r.message);
                                frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
                            }
                        });
                    }
                }
            });
        });

        d.show();
    },
    toggle_attributes: function(frm) {
        frm.toggle_display("attributes", frm.doc.has_variants || frm.doc.variant_of);
        frm.fields_dict.attributes.grid.toggle_reqd("attribute_value", frm.doc.variant_of ? 1 : 0);
        frm.fields_dict.attributes.grid.set_column_disp("attribute_value", frm.doc.variant_of ? 1 : 0);
    }
});
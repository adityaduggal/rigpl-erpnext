import frappe
from collections import OrderedDict
from operator import getitem


def get_context(context):
    valid_attribute_keys = []
    attributes_map = frappe._dict({})

    for variant in (context.variants or []):
        variant.attribute_map = frappe._dict({})
        for attr in variant.attributes:
            variant.attribute_map[attr.attribute] = attr.attribute_value

    for d in context.attributes:
        attributes_map[d.attribute] = d

        if context.attribute_values:
            attr_values = context.attribute_values[d.attribute]
            if len(attr_values) > 1 and d.use_in_description:
                valid_attribute_keys.append(d.attribute)
    print(attributes_map)

    context.valid_attribute_keys = valid_attribute_keys
    context.attributes_map = attributes_map

    # meta information
    doc = context.doc

    context.meta = frappe._dict({})

    keywords = ','.join([doc.item_code, doc.item_name, doc.description, doc.item_group])
    keywords = ', '.join(keywords.split(' '))
    context.meta.keywords = keywords
    context.meta.url = frappe.utils.get_url() + '/' + context.route
    context.meta.image = frappe.utils.get_url() + context.website_image
    context.meta.description = doc.description[:150]

    return context


def get_item_attribute_data(variants, attributes, attribute_values):
    valid_attribute_keys = []
    attributes_map = frappe._dict({})
    for variant in (variants or []):
        variant.attribute_map = frappe._dict({})
        for attr in variant.attributes:
            variant.attribute_map[attr.attribute] = attr.attribute_value

    for d in attributes:
        attributes_map[d.attribute] = d
        if attribute_values:
            attr_values = attribute_values[d.attribute]
            if len(attr_values) > 1 and d.use_in_description:
                valid_attribute_keys.append(d.attribute)

    return {
        'valid_attribute_keys': valid_attribute_keys,
        'attributes_map': attributes_map
    }


def get_item_meta(item_code):
    doc = frappe.get_doc('Item', item_code)

    meta = frappe._dict({})

    keywords = ','.join([doc.item_code, doc.item_name, doc.description, doc.item_group])
    keywords = ', '.join(keywords.split(' '))
    meta.keywords = keywords
    meta.url = frappe.utils.get_url() + '/' + doc.route
    meta.image = frappe.utils.get_url() + doc.website_image
    meta.description = doc.description[:150]

    return meta

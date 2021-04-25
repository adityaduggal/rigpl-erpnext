# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
import requests
from datetime import datetime
from frappe.utils import add_days, flt, add_to_date, get_datetime
from frappe.utils.global_search import rebuild_for_doctype, update_global_search


def execute():
    get_indiamart_leads()


def get_indiamart_leads():
    rebuild_for_doctype('Lead')
    days_to_add = flt(frappe.db.get_value("IndiaMart Pull Leads", "IndiaMart Pull Leads", "days_to_add"))
    from_date_dt, to_date_dt, max_days = get_date_range()
    last_execution = frappe.get_value("IndiaMart Pull Leads", "IndiaMart Pull Leads", "last_execution")
    last_exec_diff = (datetime.now() - get_datetime(last_execution)).total_seconds()
    if not last_execution:
        last_execution = '2010-01-01 00:00:00.000000'
        frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'leads_data_updated', 1)
        frappe.db.commit()
    else:
        last_execution = datetime.now()
    from_date_txt = from_date_dt.strftime('%d-%b-%Y %H:%M:%S')  # Text Date
    to_date_txt = to_date_dt.strftime('%d-%b-%Y %H:%M:%S')
    last_action_ok = flt(frappe.get_value("IndiaMart Pull Leads", "IndiaMart Pull Leads", "leads_data_updated"))
    if last_action_ok == 1:
        move_ahead = check_last_execution(last_exec_diff)
        if move_ahead == 1:
            last_link = get_full_link(from_date=from_date_txt, to_date=to_date_txt)
            print(last_link)
            parsed_response = get_im_reply(last_link)
            total_leads = parsed_response[0].get('TOTAL_COUNT')
            max_leads = flt(frappe.db.get_value("RIGPL Settings", "RIGPL Settings", "max_leads"))
            if flt(total_leads) > max_leads:
                print("Exiting Since Max Leads breached " + str(max_leads))
                if days_to_add >= 2:
                    frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'days_to_add',
                                        (days_to_add - 1))
                    frappe.db.commit()
                    exit()
                elif 1 > days_to_add > 0.01:
                    frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'days_to_add',
                                        (days_to_add - 0.01))
                    frappe.db.commit()
                    exit()
                elif days_to_add == 0.01:
                    frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'days_to_add', 0.0059)
                    frappe.db.commit()
                    exit()
                elif days_to_add < 0.01:
                    frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'days_to_add',
                                        days_to_add - 0.001)
                    frappe.db.commit()
                    exit()
                elif days_to_add == 1:
                    frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'days_to_add', 0.23)
                    frappe.db.commit()
                    exit()
                else:
                    print('Unsupported Value for Days to Add')
                    exit()
            else:
                if days_to_add != max_days:
                    frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'days_to_add', max_days)
                update_db(from_date_txt, to_date_txt, last_execution, last_link, total_leads)
                make_or_update_lead(parsed_response, from_date_txt, to_date_txt, last_execution, last_link)
                frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'leads_data_updated', 1)
    else:
        last_link = get_full_link(from_date=from_date_txt, to_date=to_date_txt)
        json_reply = frappe.db.get_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'json_reply')
        parsed_response = json.loads(json_reply)
        total_leads = parsed_response[0].get('TOTAL_COUNT')
        make_or_update_lead(parsed_response, from_date_txt, to_date_txt, last_execution, last_link)
        frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'last_lead_count', total_leads)
        frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'leads_data_updated', 1)
    rebuild_for_doctype('Lead')
    print('Done')


def check_last_execution(last_exec_diff):
    if last_exec_diff < 900:
        print("Indiamart Does not allow to pull data from their servers more than once in 15 minutes")
        return 0
    elif last_exec_diff < 86400:
        print("Pulling of Data would happen only once a Day to keep it Simple")
        return 0
    else:
        return 1


def get_date_range():
    from_date = get_datetime(frappe.get_value("IndiaMart Pull Leads", "IndiaMart Pull Leads", "to_date"))
    max_days = flt(frappe.get_value("RIGPL Settings", "RIGPL Settings", "max_days"))
    now_time = datetime.now()
    if from_date is None:
        from_date = '2010-01-01 00:00:00.000000'
    elif get_datetime(from_date) > datetime.now():
        from_date = add_to_date(datetime.today().date(), hours=-24)
        from_date = datetime.combine(from_date, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S.%f")
    days_to_add = (now_time - from_date)
    # from_date_dt = datetime.strptime(from_date, '%Y-%m-%d %H:%M:%S.%f')  # Date Time Date
    from_date_dt = from_date
    if days_to_add.days > max_days:
        days_to_add = max_days
        to_date_dt = add_days(from_date_dt, days_to_add)
    elif days_to_add.days < 1:
        hrs_to_add = int(days_to_add.seconds / 3600)
        days_to_add = hrs_to_add / 100
        to_date_dt = add_to_date(from_date_dt, hours=hrs_to_add)
        if hrs_to_add < 1:
            print(f"{from_date} is Less than 1 hours from Now Wait for Some time ")
            exit()
    else:
        days_to_add = days_to_add.days
        to_date_dt = add_days(from_date_dt, days_to_add)
    return from_date_dt, to_date_dt, days_to_add


def update_db(frm_dt_txt, to_dt_txt, lst_exe_dt, last_link, total_leads=0, leads_updated=0):
    from_date = datetime.strptime(frm_dt_txt, '%d-%b-%Y %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S.%f')
    to_date = datetime.strptime(to_dt_txt, '%d-%b-%Y %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S.%f')

    frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'from_date', from_date)
    frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'to_date', to_date)
    frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'last_lead_count', flt(total_leads))
    frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'last_link', last_link)
    frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'last_execution', lst_exe_dt)
    frappe.db.set_value('Indiamart Pull Leads', 'Indiamart Pull Leads', 'leads_data_updated', leads_updated)
    frappe.db.commit()


def make_or_update_lead(parsed_response, frm_dt_txt, to_dt_txt, lst_exe_dt, last_link):
    em_time_limit = "It is advised to hit this API once in every 15 minutes,but it seems that you have " \
                    "crossed this limit. please try again after 15 minutes."
    em_no_lead = "There are no leads in the given time duration.please try for a different duration."
    error_message = parsed_response[0].get('Error_Message', "NO ERROR")

    if len(error_message) == len(em_time_limit):
        print('Time Limit Reached')
        frappe.db.set_value("Indiamart Pull Leads", "Indiamart Pull Leads", "leads_data_updated", 1)
        frappe.db.commit()
        exit()
    elif len(error_message) == len(em_no_lead):
        # Change the From Date and To Date and Execution Date and Lead Count so to run in future
        update_db(frm_dt_txt, to_dt_txt, lst_exe_dt, last_link, leads_updated=1)
        print('No Lead in Time Period')
        exit()
    elif error_message == "NO ERROR":
        print(error_message)

    total_leads = parsed_response[0].get('TOTAL_COUNT')
    for lead in parsed_response:
        lead_list = search_existing(search_m=lead.get('MOB', 'NO MOBILE'), search_e=
            lead.get('SENDEREMAIL', 'NO EMAIL'), country=lead.get('COUNTRY_ISO'))
        if lead_list:
            for lead_name in lead_list:
                frappe.db.set_value("Lead", lead_name, "source", "Campaign")
                frappe.db.set_value("Lead", lead_name, "campaign_name", "India Mart")
                recd_time = datetime.strptime(lead.get('DATE_TIME_RE'), '%d-%b-%Y %I:%M:%S %p')
                frappe.db.set_value("Lead", lead_name, "creation", recd_time)
                print(f"{lead.get('RN')}. Updated Lead {lead_name}")
        else:
            if lead.get('MOB') is None and lead.get('SENDEREMAIL') is None:
                print('For Serial# {}, No Lead Created for Query ID {}'.format(lead.get('RN'), lead.get('QUERY_ID')))
            else:
                print(f"{lead.get('RN')}. Creating New Lead")
                ld = frappe.new_doc("Lead")
                ld.email_id = lead.get('SENDEREMAIL', 'IM-Email')
                if lead.get('GLUSR_USR_COMPANYNAME') is None or (str(lead.get('GLUSR_USR_COMPANYNAME'))).replace(" ",
                                                                                                                 "") == "":
                    ld.company_name = 'IM-Company'
                else:
                    ld.company_name = lead.get('GLUSR_USR_COMPANYNAME')
                ld.lead_name = lead.get('SENDERNAME')
                if lead.get('MOB', '1234') is None:
                    mobile_number = '12345'
                else:
                    mobile_number = lead.get('MOB', '1234').strip() if not None else '123456'
                ld.mobile_no = mobile_number
                if lead.get('PHONE', '') is None:
                    phone_no = ''
                else:
                    if lead.get('PHONE').strip() is not None:
                        phone_no = lead.get('PHONE', '')
                    else:
                        phone_no = ''
                if lead.get('PHONE_ALT', '1234') is None:
                    phone_alt = ''
                else:
                    if lead.get('PHONE_ALT').strip() is not None:
                        phone_alt = lead.get('PHONE_ALT', '').strip
                    else:
                        phone_alt = ''
                if phone_no.strip() is not None:
                    combined_no = phone_no
                if phone_alt.strip() is not None:
                    combined_no += ", " + phone_alt
                if combined_no is not None:
                    ld.phone = combined_no
                if lead.get('COUNTRY_ISO') == 'IN':
                    ld.territory = 'India'
                else:
                    ld.territory = 'Exports'
                ld.source = 'Campaign'
                ld.campaign_name = 'India Mart'
                ld.requirement = 100
                ld.creation = datetime.strptime(lead.get('DATE_TIME_RE'), '%d-%b-%Y %I:%M:%S %p')
                ld.remark = str(lead.get('SUBJECT', "")) + " " + str(lead.get('ENQ_MESSAGE', "")) + \
                " City: "+ str(lead.get('ENQ_CITY', "")) + " State: " + str(lead.get('ENQ_STATE', "")) + \
                " Country: " + str(lead.get('COUNTRY_ISO', ""))
                ld.save()
                print("Created New Lead# " + ld.name)
                lead_doc = frappe.get_doc("Lead", ld.name)
                update_global_search(lead_doc)
                frappe.db.commit()


def get_full_link(from_date, to_date):
    base_link = 'https://mapi.indiamart.com/wservce/enquiry/listing/'
    im_mobile, im_pass = get_indiamart_login()
    base_link += 'GLUSR_MOBILE/' + str(im_mobile) + '/GLUSR_MOBILE_KEY/' + str(im_pass)
    base_link += '/Start_Time/' + str(from_date) + '/End_Time/' + str(to_date) + '/'
    return base_link


def get_im_reply(full_link):
    response = requests.get(full_link)
    new_response = response.text
    json_reply = new_response
    frappe.db.set_value("IndiaMart Pull Leads", "IndiaMart Pull Leads", "json_reply", new_response)
    frappe.db.set_value("IndiaMart Pull Leads", "IndiaMart Pull Leads", "leads_updated", 0)
    frappe.db.commit()
    parsed_response = json.loads(new_response)
    return parsed_response


def search_existing(search_e, search_m, country):
    if search_e != 'NO EMAIL' and search_e:
        search_e_key = '%' + search_e + '%'
    else:
        search_e_key = "NO EMAIL ENTERED"

    if search_m != 'NO MOBILE' and country == 'IN' and search_m:
        if len(search_m) == 14:
            search_m = search_m[4:]
        elif len(search_m) < 5:
            search_m = 'NO MOBILE'

    if search_m != 'NO MOBILE' and search_m:
        search_m_key = '%' + search_m + '%'
    else:
        search_m_key = None

    if search_m_key:
        lead_m = frappe.db.sql("""SELECT doctype, name FROM __global_search WHERE doctype = 'Lead' 
        AND content LIKE '%s'""" % search_m_key, as_dict=1)
    else:
        lead_m = {}

    lead_list = []
    if lead_m:
        for lead in lead_m:
            lead_list.append(lead.name)
    if search_e_key:
        lead_e = frappe.db.sql("""SELECT doctype, name FROM __global_search WHERE doctype = 'Lead' AND content LIKE 
        '%s'""" % search_e_key, as_dict=1)
    if lead_e:
        for lead in lead_e:
            lead_list.append(lead.name)
    if not lead_list:
        print("No Lead Found for Mobile: " + str(search_m) + " and Email: " + str(search_e) + " Country: " + str(
            country))
    return lead_list


def get_indiamart_login():
    rigpl_sett = frappe.get_doc('RIGPL Settings')
    im_pass = rigpl_sett.indiamart_api_key
    im_mobile = rigpl_sett.indiamart_primary_mobile
    return im_mobile, im_pass

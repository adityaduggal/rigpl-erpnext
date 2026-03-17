# -*- coding: utf-8 -*-
#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
import requests
import time
from datetime import datetime
from frappe.utils import add_days, flt, add_to_date, get_datetime
from frappe.utils.global_search import rebuild_for_doctype, update_global_search

log = frappe.logger("indiamart", allow_site=True)

REQUEST_TIMEOUT = 20
COMMIT_BATCH = 50


def execute():
    try:
        get_indiamart_leads()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "IndiaMart Lead Pull Failed")
        log.exception("IndiaMart scheduled task failed")


def get_indiamart_leads():

    settings = frappe.get_single("IndiaMart Pull Leads")
    rigpl_settings = frappe.get_single("RIGPL Settings")

    max_leads = flt(rigpl_settings.max_leads)
    days_to_add = flt(settings.days_to_add)

    from_date_dt, to_date_dt, max_days = get_date_range()

    from_date_txt = from_date_dt.strftime('%d-%b-%Y %H:%M:%S')
    to_date_txt = to_date_dt.strftime('%d-%b-%Y %H:%M:%S')

    last_execution = settings.last_execution
    last_exec_diff = None

    if last_execution:
        last_exec_diff = (datetime.now() - get_datetime(last_execution)).total_seconds()

    if last_exec_diff:

        if last_exec_diff < 900:
            log.info("Indiamart API cannot be called within 15 minutes")
            return

        if last_exec_diff < 86400:
            log.info("Indiamart pull allowed once a day")
            return

    last_action_ok = flt(settings.leads_data_updated)

    # -------------------------------------------------
    # Resume from cached JSON if previous run failed
    # -------------------------------------------------

    if last_action_ok != 1:

        json_reply = settings.json_reply

        if not json_reply:
            return

        parsed_response = json.loads(json_reply)

        total_leads = parsed_response[0].get('TOTAL_COUNT')

        make_or_update_lead(
            parsed_response,
            from_date_txt,
            to_date_txt,
            last_execution,
            settings.last_link
        )

        settings.last_lead_count = total_leads
        settings.leads_data_updated = 1
        settings.save()

        return

    # -------------------------------------------------
    # Normal API pull
    # -------------------------------------------------

    last_link = get_full_link(from_date_txt, to_date_txt)

    parsed_response = get_im_reply(last_link)

    if not parsed_response:
        return

    # -------------------------------------------------
    # IndiaMart Error Parser (CRITICAL)
    # -------------------------------------------------

    error_message = parsed_response[0].get('Error_Message')

    if error_message:

        msg = error_message.lower()

        if "15 minutes" in msg:

            log.warning("IndiaMart API 15-minute limit reached. Retrying later.")
            settings.leads_data_updated = 1
            settings.save()
            return

        elif "no leads" in msg:

            log.info("No leads found in this window. Moving window forward.")

            update_db(
                from_date_txt,
                to_date_txt,
                datetime.now(),
                last_link,
                0
            )

            settings.leads_data_updated = 1
            settings.save()

            return

        elif error_message != "NO ERROR":

            log.warning(f"IndiaMart returned unknown error: {error_message}")
            return

    # -------------------------------------------------
    # Lead count logic
    # -------------------------------------------------

    total_leads = parsed_response[0].get('TOTAL_COUNT')

    if flt(total_leads) > max_leads:

        log.warning(f"Lead count {total_leads} exceeds max_leads {max_leads}")

        shrink_window(settings)

        return

    if days_to_add != max_days:
        settings.days_to_add = max_days

    update_db(
        from_date_txt,
        to_date_txt,
        datetime.now(),
        last_link,
        total_leads
    )

    make_or_update_lead(
        parsed_response,
        from_date_txt,
        to_date_txt,
        datetime.now(),
        last_link
    )

    settings.leads_data_updated = 1
    settings.save()

    rebuild_for_doctype('Lead')

    log.info("IndiaMart lead pull completed")


def shrink_window(settings):

    days_to_add = flt(settings.days_to_add)

    if days_to_add >= 2:

        settings.days_to_add = days_to_add - 1

    elif 1 > days_to_add > 0.01:

        settings.days_to_add = days_to_add - 0.01

    elif days_to_add == 0.01:

        settings.days_to_add = 0.0059

    elif days_to_add < 0.01:

        settings.days_to_add = days_to_add - 0.001

    elif days_to_add == 1:

        settings.days_to_add = 0.23

    settings.save()


def get_date_range():

    from_date = get_datetime(
        frappe.db.get_value("IndiaMart Pull Leads", "IndiaMart Pull Leads", "to_date")
    )

    max_days = flt(
        frappe.db.get_value("RIGPL Settings", "RIGPL Settings", "max_days")
    )

    now_time = datetime.now()

    if from_date is None:

        from_date = datetime(2010, 1, 1)

    elif from_date > now_time:

        from_date = add_to_date(now_time, hours=-24)

    days_to_add = (now_time - from_date)

    from_date_dt = from_date

    if days_to_add.days > max_days:

        days_to_add = max_days
        to_date_dt = add_days(from_date_dt, days_to_add)

    elif days_to_add.days < 1:

        hrs_to_add = int(days_to_add.seconds / 3600)

        if hrs_to_add < 1:
            raise frappe.ValidationError("Less than 1 hour window")

        days_to_add = hrs_to_add / 100

        to_date_dt = add_to_date(from_date_dt, hours=hrs_to_add)

    else:

        days_to_add = days_to_add.days

        to_date_dt = add_days(from_date_dt, days_to_add)

    return from_date_dt, to_date_dt, days_to_add


def update_db(frm_dt_txt, to_dt_txt, lst_exe_dt, last_link, total_leads=0):

    settings = frappe.get_single("IndiaMart Pull Leads")

    settings.from_date = datetime.strptime(frm_dt_txt, '%d-%b-%Y %H:%M:%S')
    settings.to_date = datetime.strptime(to_dt_txt, '%d-%b-%Y %H:%M:%S')

    settings.last_lead_count = flt(total_leads)
    settings.last_link = last_link
    settings.last_execution = lst_exe_dt
    settings.leads_data_updated = 0

    settings.save()


def make_or_update_lead(parsed_response, frm_dt_txt, to_dt_txt, lst_exe_dt, last_link):

    created = 0
    updated = 0
    batch = 0

    for lead in parsed_response:

        lead_list = search_existing(
            lead.get('SENDEREMAIL'),
            lead.get('MOB'),
            lead.get('COUNTRY_ISO')
        )

        if lead_list:

            for lead_name in lead_list:

                frappe.db.set_value(
                    "Lead",
                    lead_name,
                    {
                        "source": "Campaign",
                        "campaign_name": "India Mart"
                    }
                )

                updated += 1

        else:

            if lead.get('MOB') is None and lead.get('SENDEREMAIL') is None:
                continue

            ld = frappe.new_doc("Lead")

            ld.flags.ignore_mandatory = True

            ld.email_id = lead.get('SENDEREMAIL', 'IM-Email')

            company = lead.get('GLUSR_USR_COMPANYNAME') or 'IM-Company'

            ld.company_name = company
            ld.lead_name = lead.get('SENDERNAME')

            mobile_number = lead.get('MOB') or ""

            ld.mobile_no = mobile_number.strip()

            phone_no = (lead.get('PHONE') or "").strip()
            phone_alt = (lead.get('PHONE_ALT') or "").strip()

            phones = ", ".join(filter(None, [phone_no, phone_alt]))

            if phones:
                ld.phone = phones

            ld.territory = 'India' if lead.get('COUNTRY_ISO') == 'IN' else 'Exports'

            ld.source = 'Campaign'
            ld.campaign_name = 'India Mart'

            ld.requirement = 100

            if lead.get('DATE_TIME_RE'):

                ld.creation = datetime.strptime(
                    lead.get('DATE_TIME_RE'),
                    '%d-%b-%Y %I:%M:%S %p'
                )

            ld.remark = " ".join(filter(None, [
                lead.get('SUBJECT'),
                lead.get('ENQ_MESSAGE'),
                lead.get('ENQ_CITY'),
                lead.get('ENQ_STATE'),
                lead.get('COUNTRY_ISO')
            ]))

            ld.save()

            update_global_search(ld)

            created += 1
            batch += 1

            if batch >= COMMIT_BATCH:

                frappe.db.commit()
                batch = 0

    frappe.db.commit()

    log.info(f"IndiaMart leads created={created} updated={updated}")


def get_full_link(from_date, to_date):

    base_link = 'https://mapi.indiamart.com/wservce/enquiry/listing/'

    im_mobile, im_pass = get_indiamart_login()

    return (
        f"{base_link}GLUSR_MOBILE/{im_mobile}/GLUSR_MOBILE_KEY/{im_pass}"
        f"/Start_Time/{from_date}/End_Time/{to_date}/"
    )


def get_im_reply(full_link):

    try:

        response = requests.get(full_link, timeout=REQUEST_TIMEOUT)

        response.raise_for_status()

        text = response.text

        frappe.db.set_value(
            "IndiaMart Pull Leads",
            "IndiaMart Pull Leads",
            "json_reply",
            text
        )

        frappe.db.set_value(
            "IndiaMart Pull Leads",
            "IndiaMart Pull Leads",
            "leads_updated",
            0
        )

        parsed_response = json.loads(text)

        return parsed_response

    except Exception:

        frappe.log_error(frappe.get_traceback(), "IndiaMart API Error")

        return None


def search_existing(search_e, search_m, country):

    lead_list = set()

    if search_m and country == 'IN':

        if len(search_m) == 14:
            search_m = search_m[4:]

        if len(search_m) >= 5:

            rows = frappe.db.sql("""
                SELECT name
                FROM __global_search
                WHERE doctype='Lead'
                AND content LIKE %s
            """, (f"%{search_m}%",), as_dict=True)

            for r in rows:
                lead_list.add(r.name)

    if search_e:

        rows = frappe.db.sql("""
            SELECT name
            FROM __global_search
            WHERE doctype='Lead'
            AND content LIKE %s
        """, (f"%{search_e}%",), as_dict=True)

        for r in rows:
            lead_list.add(r.name)

    return list(lead_list)


def get_indiamart_login():

    settings = frappe.get_single("RIGPL Settings")

    return settings.indiamart_primary_mobile, settings.indiamart_api_key
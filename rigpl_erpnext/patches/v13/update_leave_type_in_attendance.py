import frappe
import time


def execute():
    """
    This Patch Update all the old submitted attendance with leave type from the Leave Application
    """
    st_time = time.time()
    updated_att = 0
    not_updated = 0
    att_lst = frappe.get_list("Attendance",
                              fields=["name", "leave_type",
                                      "attendance_date", "employee", "status"],
                              filters={"docstatus": 1,
                                       "status": "On Leave", "leave_type": ""},
                              order_by="attendance_date")
    for att in att_lst:
        leave_lst = frappe.get_list("Leave Application",
                                    fields=["name", "leave_type", "employee",
                                            "from_date", "to_date", "status"],
                                    filters={"docstatus": 1, "status": "Approved",
                                             "employee": att.employee,
                                             "from_date": ["<=", att.attendance_date],
                                             "to_date": [">=", att.attendance_date]
                                             })
        if leave_lst:
            frappe.db.set_value("Attendance", att.name,
                                "leave_type", leave_lst[0].leave_type)
            print(f"Updated {att.name} with Leave Type = {leave_lst[0].leave_type} from Leave "
                  f"Application {leave_lst[0].name}")
            updated_att += 1
        else:
            print(f"Unable to find any Leave Application for {att.name}")
            not_updated += 1
    print(f"Total Records Updated = {updated_att} out of {len(att_lst)} and Total Time Taken = "
          f"{int(time.time()- st_time)} seconds")
    print(f"Total Records Not Updated = {not_updated}")

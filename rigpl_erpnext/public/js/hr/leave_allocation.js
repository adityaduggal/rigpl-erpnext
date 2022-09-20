frappe.ui.form.on("Leave Allocation", {
    onload: function(frm) {
        frm.set_query( "valid_attendance", "linked_attendances", function ( doc, cdt, cdn ) {
                    return {
                        "filters": {
                            "employee": frm.doc.employee,
                            "docstatus": 1,
                            "status": "Present",
                            "attendance_date": ["between", [frm.doc.from_date, frm.doc.to_date]],
                        },
                        "order_by": "attendance_date asc"
                 };
             });
        },
    from_date: function(frm) {
        frm.doc.linked_attendances = [];
        frm.refresh_fields();
    },
    to_date: function(frm) {
        frm.doc.linked_attendances = [];
        frm.refresh_fields();
    },
    employee: function(frm) {
        frm.doc.linked_attendances = [];
        frm.refresh_fields();
    },
    leave_type: function(frm) {
        frappe.db.get_doc("Leave Type", frm.doc.leave_type).then(ltd => {
            frm.doc.carry_forward = ltd.is_carry_forward;
            frm.doc.linked_attendances = [];
            frm.refresh_fields();
        });
    },
    carry_forward: function (frm) {
        frappe.db.get_doc("Leave Type", frm.doc.leave_type).then(ltd => {
            frm.doc.carry_forward = ltd.is_carry_forward; 
            frm.refresh_fields();
        });

    }
});
frappe.ui.form.on("Holiday List", {
    onload: function(frm){
        frm.set_query("base_holiday_list", function(doc){
            return {
                filters: [
                    ['is_base_list', '=', 1]
                ]
            };
        });
    },

    is_base_list: function(frm){
        frm.doc.base_holiday_list = "";
    },

    from_date: function(frm){
        if (frm.doc.is_base_list === 1){
            frm.doc.holidays = [];
        }
    },
    to_date: function(frm){
        if (frm.doc.is_base_list === 1){
            frm.doc.holidays = [];
        }
    },
    pull_holidays: function(frm){
        frm.doc.holidays = [];
        frappe.call({
            method: "rigpl_erpnext.rigpl_erpnext.validations.holiday_list.pull_holidays",
            args : {
                "hd_name": frm.doc.name,
                "frm_date": frm.doc.from_date,
                "to_date": frm.doc.to_date
            },
            callback: function(r){
                if (!r.exc){
                    frm.refresh_fields("holidays");
                }
            }
        });
        //frm.reload_doc();
    }
});
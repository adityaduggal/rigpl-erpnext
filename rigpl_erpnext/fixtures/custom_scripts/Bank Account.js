frappe.ui.form.on("Bank Account", {
    refresh: function(frm){
        cur_frm.cscript.lock_fields(frm)
    },
    onload: function(frm){
        cur_frm.cscript.lock_fields(frm)
    },
    verified: function(frm){
        cur_frm.cscript.lock_fields(frm)
    },
    is_company_account: function(frm){
        frm.doc.party_type = ""
        frm.doc.party = ""
        frm.doc.account = ""
        frm.doc.bank = ""
    },
});

cur_frm.cscript.lock_fields = function(frm){
    var read_only_value = frm.doc.verified;
    var locked_fields = ["account_name", "account", "bank", "is_company_account", "company",
    "bank_account_no", "branch_code", "swift_number", "party_type", "party", "name_in_bank_records"]
    for (var i = 0; i < locked_fields.length; i++){
        frm.set_df_property(locked_fields[i], "read_only", read_only_value);
    }
};
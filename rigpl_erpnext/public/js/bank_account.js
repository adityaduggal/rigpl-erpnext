frappe.ui.form.on("Bank Account", {
    is_company_account: function(frm) {
        frm.doc.party_type = "";
        frm.doc.party = "";
        frm.doc.account = "";
        frm.doc.bank = "";
    },
});
// Copyright (c) 2026, Rohit Industries Group Private Limited and contributors
// For license information, please see license.txt
// Dashboard of the Carrier Trackings of this account for a period, and the stale clean-up (#169).

const SUMMARY = "rigpl_erpnext.rigpl_erpnext.shipping.dashboard.get_account_summary";
const CLOSE_STALE = "rigpl_erpnext.rigpl_erpnext.shipping.dashboard.close_stale_trackings";
const STATUS_COLORS = {
	"Delivered": "green", "In Transit": "blue", "Out for Delivery": "blue", "Booked": "blue",
	"Exception": "orange", "RTO": "orange", "No Information": "orange", "No Status": "grey",
	"Cancelled": "grey", "Closed - No Update": "grey", "Not Booked": "grey",
};

frappe.ui.form.on("Shipping Provider Account", {
	refresh(frm) {
		if (frm.is_new()) return;
		rigpl_shipping_dashboard(frm);
		frm.add_custom_button(__("Close Stale Trackings"), () => rigpl_close_stale(frm), __("Actions"));
	},
});

function rigpl_shipping_dashboard(frm) {
	if (!frm.__summary_period) {
		frm.__summary_period = {
			from_date: frappe.datetime.add_days(frappe.datetime.get_today(), -30),
			to_date: frappe.datetime.get_today(),
		};
	}
	// refresh runs again after each save: drop the section of the last refresh
	$(frm.dashboard.wrapper).find(".rigpl-ship-summary").closest(".form-dashboard-section").remove();
	const section = frm.dashboard.add_section(
		`<div class="rigpl-ship-period row" style="margin-bottom: 8px;"></div>
		<div class="rigpl-ship-summary"></div>`,
		__("Carrier Trackings")
	);
	frm.dashboard.show();
	const bar = section.find(".rigpl-ship-period");
	["from_date", "to_date"].forEach((fieldname) => {
		const wrapper = $('<div class="col-sm-4"></div>').appendTo(bar);
		const control = frappe.ui.form.make_control({
			parent: wrapper,
			df: {
				fieldtype: "Date", fieldname, label: fieldname === "from_date" ? __("From Date") : __("To Date"),
				change() {
					const value = control.get_value();
					if (value && value !== frm.__summary_period[fieldname]) {
						frm.__summary_period[fieldname] = value;
						rigpl_load_summary(frm, section);
					}
				},
			},
			render_input: true,
		});
		control.set_value(frm.__summary_period[fieldname]);
	});
	rigpl_load_summary(frm, section);
}

function rigpl_load_summary(frm, section) {
	const target = section.find(".rigpl-ship-summary");
	target.html(`<p class="text-muted">${__("Loading...")}</p>`);
	frappe.call({
		method: SUMMARY,
		args: { account: frm.doc.name, ...frm.__summary_period },
		callback(r) {
			const data = r.message || {};
			frm.__stale_open = data.stale_open || 0;
			frm.__auto_close_days = data.auto_close_days;
			const box = (label, value, color) => `
				<div class="col-sm-3" style="margin-bottom: 8px;">
					<span class="indicator ${color}">${frappe.utils.escape_html(label)}</span>
					<div style="font-size: 18px; font-weight: 600;">${frappe.utils.escape_html(String(value))}</div>
				</div>`;
			let html = box(__("Made"), data.total || 0, "darkgrey");
			(data.by_status || []).forEach((row) => {
				html += box(__(row.status), row.count, STATUS_COLORS[row.status] || "grey");
			});
			if (data.avg_transit_days !== null && data.avg_transit_days !== undefined) {
				html += box(__("Avg Transit Days"), data.avg_transit_days, "green");
			}
			html += box(__("Stale Open (all time)"), data.stale_open || 0, data.stale_open ? "red" : "grey");
			target.html(`<div class="row">${html}</div>`);
		},
	});
}

function rigpl_close_stale(frm) {
	const count = frm.__stale_open || 0;
	if (!count) {
		frappe.msgprint(__("No open tracking of {0} is older than {1} days.", [frm.doc.name, frm.__auto_close_days]));
		return;
	}
	frappe.confirm(
		__("{0} open trackings are older than {1} days. Poll each one once, then close the rest as Closed - No Update?",
			[count, frm.__auto_close_days]),
		() => frappe.call({ method: CLOSE_STALE, args: { account: frm.doc.name } }).then((r) => {
			if (r.message) frappe.show_alert({ message: r.message, indicator: "blue" });
		})
	);
}

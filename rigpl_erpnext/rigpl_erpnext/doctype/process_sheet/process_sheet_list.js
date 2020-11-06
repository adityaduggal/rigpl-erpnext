frappe.listview_settings['Process Sheet'] = {
	get_indicator: function (doc) {
		if (doc.status === "Stopped") {
			return [__("Stopped"), "orange", "status,=,Stopped"];
		} else if (doc.status === "Short Closed") {
			return [__("Short Closed"), "orange", "status,=,Short Closed"];
		} else if (doc.status === "Completed") {
			return [__("Completed"), "green", "status,=,Completed"];
		} else if (doc.status === "Cancelled") {
		    return [__("Cancelled"), "red", "status,=,Cancelled"];
		} else if (doc.status === "Draft") {
		    return [__("Draft"), "violet", "status,=,Draft"];
		} else if (doc.status === "In Progress") {
		    return [__("In Progress"), "blue", "status,=,In Progress"];
		} else if (doc.status === "Submitted") {
		    return [__("In Progress"), "blue", "status,=,In Progress"];
		}

	}
};

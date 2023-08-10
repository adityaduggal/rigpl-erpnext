frappe.listview_settings['Process Job Card RIGPL'] = {
	get_indicator: function (doc) {
		if (doc.status === "Open") {
			return [__("Open"), "blue", "status,=,Open"];
		} else if (doc.status === "Work In Progress") {
			return [__("Work In Progress"), "orange", "status,=,Work In Progress"];
		} else if (doc.status === "Completed") {
			return [__("Completed"), "green", "status,=,Completed"];
		} else if (doc.status === "Cancelled") {
		    return [__("Cancelled"), "red", "status,=,Cancelled"];
		}

	}
};

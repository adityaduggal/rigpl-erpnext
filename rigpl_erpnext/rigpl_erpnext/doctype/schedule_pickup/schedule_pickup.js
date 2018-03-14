// Copyright (c) 2018, Rohit Industries Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Schedule Pickup', {
	refresh: function(frm) {

	},

	onload: function(frm){
		frm.set_query("pickup_address", function(doc) {
			return {
				"filters":{
					"is_your_company_address": 1,
				}
			};
		});
	}
});

cur_frm.set_query("carrier_tracking_no", "pickup_details", function(doc, cdt, cdn) {
	var d = locals[cdt][cdn];
	return{
		filters: [
			['Carrier Tracking', 'docstatus', '=', 0],
			['Carrier Tracking', 'status', '=', 'Booked']
		]
	}
});

frappe.ui.form.on("Schedule Pickup", "refresh", function(frm) {	
	frappe.ui.form.on("Pickup Schedule Details", {
			"carrier_tracking_no": function(frm) {
			frm.add_fetch("carrier_tracking_no", "awb_number", "awb_no");
			frm.add_fetch("carrier_tracking_no", "total_handling_units", "no_of_packages");
			frm.add_fetch("carrier_tracking_no", "total_weight", "weight");
			frm.add_fetch("carrier_tracking_no", "carrier_name", "carrier_name");
		}
	});

});

frappe.ui.form.on("Pickup Schedule Details", "carrier_tracking_no", function(frm, cdt, cdn) {
// code for calculate total and set on parent field.
	var weight = 0;
	var packs = 0;
	var uom = "Kg";
	var account = ""
	$.each(frm.doc.pickup_details || [], function(i, d) {
		weight += flt(d.weight);
		packs += flt(d.no_of_packages);
		account = d.carrier_name;
	});
	frm.set_value("total_weight", weight);
	//frm.set_value("weight_uom", uom);
	frm.set_value("no_of_packages", packs);
	frm.set_value("carrier_name", account);
});

frappe.ui.form.on("Schedule Pickup", "ready_time", function(frm) {
	// Rounds Pickup time to nearest 15mins and also closing time is +3 hrs
	var ptime = frm.doc.ready_time;
	var diff = '03:00:00';
	ptime = roundtime(ptime, 15);
	var ltime = addTimes(ptime, diff);
	frm.set_value("last_time", ltime);
	frm.set_value("ready_time", ptime);
});

/**
 * Add two string time values (HH:mm:ss) with javascript
 *
 * Usage:
 *  > addTimes('04:20:10', '21:15:10');
 *  > "25:35:20"
 *  > addTimes('04:35:10', '21:35:10');
 *  > "26:10:20"
 *  > addTimes('30:59', '17:10');
 *  > "48:09:00"
 *  > addTimes('19:30:00', '00:30:00');
 *  > "20:00:00"
 *
 * @param {String} startTime  String time format
 * @param {String} endTime  String time format
 * @returns {String}
 */
function addTimes (startTime, endTime) {
  var times = [ 0, 0, 0 ]
  var max = times.length

  var a = (startTime || '').split(':')
  var b = (endTime || '').split(':')

  // normalize time values
  for (var i = 0; i < max; i++) {
    a[i] = isNaN(parseInt(a[i])) ? 0 : parseInt(a[i])
    b[i] = isNaN(parseInt(b[i])) ? 0 : parseInt(b[i])
  }

  // store time values
  for (var i = 0; i < max; i++) {
    times[i] = a[i] + b[i]
  }

  var hours = times[0]
  var minutes = times[1]
  var seconds = times[2]

  if (seconds >= 60) {
    var m = (seconds / 60) << 0
    minutes += m
    seconds -= 60 * m
  }

  if (minutes >= 60) {
    var h = (minutes / 60) << 0
    hours += h
    minutes -= 60 * h
  }

  return ('0' + hours).slice(-2) + ':' + ('0' + minutes).slice(-2) + ':' + ('0' + seconds).slice(-2)
}

function roundtime(time_to_round, factor){
// This function rounds time to the nearest factor like '15:09:00' time is rounded to 15:15:00
	var times = [ 0, 0, 0 ]
	var max = times.length
	// normalize time values
	var a = (time_to_round || '').split(':')
	for (var i = 0; i < max; i++) {
		a[i] = isNaN(parseInt(a[i])) ? 0 : parseInt(a[i])
		}
	// store time values
	if (factor < 60){
		var new_min = factor * Math.round(a[1] / factor);
	}
	var new_time = ('0' + a[0]).slice(-2) + ':' + ('0' + new_min).slice(-2) + ':' + ('00').slice(-2);
	return new_time;
}
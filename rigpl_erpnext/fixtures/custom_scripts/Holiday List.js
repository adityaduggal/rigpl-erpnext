cur_frm.cscript.custom_onload = function () {
	cur_frm.set_query('base_holiday_list', function(doc){
		return {
			filters: [
				['is_base_list', '=', 1]
			]
		};
	});
}
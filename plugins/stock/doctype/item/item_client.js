//Reset the default fields since these fields are not applicable for new items
cur_frm.cscript.custom_onload = function() {
    if (cur_frm.doc.__islocal){
    	var fields = ["min_order_qty", "end_of_life", "re_order_level", "show_in_website", "brand",
			"base_material", "quality", "special_treatment", "is_rm", 
			"height_dia", "height_dia_inch", "inch_h", "width", "widht_inch", "inch_w", 
			"length", "length_inch", "inch_l", "a1", "d1", "d1_inch", "inch_d1", 
			"l1", "l1_inch", "inch_l1", "a2", "d2", "d2_inch", "inch_d2", "l2", "l2_inch", "inch_l2", 
			"r1", "a3","no_of_flutes", "drill_type"];
		for(var i in fields) {
			cur_frm.set_value(fields[i], "");
		}
	var inch_fds = ["height_dia", "width", "length", "d1", "l1", "d2", "l2"];
	var inch_fd_chk = ["h", "w", "l", "d1", "l1", "d2", "l2"];
	for (var i in inch_fds){
			cur_frm.toggle_display(inch_fds[i]+"_inch", cur_frm.doc.tool_type!="");
		}			
	}
	var inch_fds = ["height_dia", "width", "length", "d1", "l1", "d2", "l2"];
	var inch_fd_chk = ["h", "w", "l", "d1", "l1", "d2", "l2"];
	for (var i in inch_fds){
			cur_frm.toggle_display(inch_fds[i]+"_inch", cur_frm.doc.tool_type=="");
		}	
}

//Custom refresh function would make the entered fields DISABLED so that no one can change the defining fields.
cur_frm.cscript.custom_refresh = function() {
    // Disable defining fields of saved items only not applicable for unsaved items data
    cur_frm.toggle_enable(["description", "tool_type","brand", "base_material", "quality", "is_rm", 
		"height_dia", "height_dia_inch", "inch_h", "width", "width_inch", "inch_w", "length", "length_inch", "inch_l", 
		"a1", "d1", "d1_inch", "inch_d1", "l1", "l1_inch", "inch_l1", "a2", "d2", "d2_inch", "inch_d2", 
		"l2", "l2_inch", "inch_l2", "r1", "no_of_flutes", "drill_type", "special_treatment", "a3"], cur_frm.doc.__islocal);
	cur_frm.toggle_enable("description",cur_frm.doc.tool_type =="Others")
	cur_frm.cscript.tool_type();
}

//Custom query to get the Quality as per Base Material and Is RM selected
cur_frm.fields_dict['quality'].get_query = function(doc) {
doc = cur_frm.doc;
var cond = '';

if(doc.base_material!="" && doc.is_rm!=""){
	cond = '`tabQuality`.base_material = "'+doc.base_material+'" and `tabQuality`.is_rm = "'+doc.is_rm+'" and' ;
	}
else if (doc.is_rm == "" && doc.base_material != ""){
	cond = '`tabQuality`.base_material = "'+doc.base_material+'" and `tabQuality`.is_rm = "No" and' ;
	}
else if (doc.is_rm != "" && doc.base_material == ""){
	cond = '`tabQuality`.is_rm = "'+doc.is_rm+'" and' ;
}



return repl('SELECT DISTINCT `tabQuality`.`name`, base_material, is_rm, code FROM `tabQuality` \
            WHERE %(cond)s `tabQuality`.%(key)s LIKE "%s" \
            ORDER BY `tabQuality`.`name` DESC LIMIT 50', {company:doc.company,cond:cond})
}


//*************************************************************************************************
//FUNCTION PERTAINING TO HIDING AND MAKING REQUISITE FIELDS MANDATORY AS PER TOOL TYPE SELECTED
//*************************************************************************************************

cur_frm.cscript.tool_type = function() {
    
	cur_frm.cscript.custom_onload();
	
	// hide/unhide Height, Length, A1, Brand, Base Metal, Quality
    var condition = in_list(["Ball Nose", "Centre Drill Type A", "Centre Drill Type B", 
		"Centre Drill Type R", "Drill", "Mandrels", "Parting", "Punch Step3", "Punches", 
		"Reamer", "Rectangular", "Round", "SQEM", "Square"], cur_frm.doc.tool_type);
    
	//Hide or Unhide Height or Dia field
	cur_frm.toggle_display("height_dia", condition);
	cur_frm.toggle_display("inch_h", condition);
	cur_frm.toggle_reqd("height_dia", condition);
	
	//Hide or Unhide Length field
	cur_frm.toggle_display("length", condition);
	cur_frm.toggle_display("inch_l", condition);
	cur_frm.toggle_reqd("length", condition);
	
	//Hide or Unhide A1 field
	cur_frm.toggle_display("a1", condition);
	cur_frm.toggle_reqd("a1", condition);
	
	//Hide or Unhide Brand field
	cur_frm.toggle_display("brand", condition);
	cur_frm.toggle_reqd("brand", condition);
	
	//Hide or Unhide Base Material field
	cur_frm.toggle_display("base_material", condition);
	cur_frm.toggle_reqd("base_material", condition);
	
	//Hide or Unhide Quality field
	cur_frm.toggle_display("quality", condition);
	cur_frm.toggle_reqd("quality", condition);

    // Hide or Unhide Is RM field
    var condition = in_list(["Rectangular", "Round", "Square"], cur_frm.doc.tool_type);
    cur_frm.toggle_display("is_rm", condition);
	cur_frm.toggle_reqd("is_rm", condition);

    // hide/unhide width field
    var condition = in_list(["Mandrels", "Parting", "Rectangular", "Square"], cur_frm.doc.tool_type);
    cur_frm.toggle_display("width", condition);
	cur_frm.toggle_display("inch_w", condition);
	cur_frm.toggle_reqd("width", condition);

    // hide/unhide d1 field
    var condition = in_list(["Ball Nose", "Centre Drill Type A", "Centre Drill Type B", 
		"Centre Drill Type R", "Drill","Punches", "Punch Step3", "Reamer", "SQEM"], cur_frm.doc.tool_type);
    cur_frm.toggle_display("d1", condition);
	cur_frm.toggle_display("inch_d1", condition);
	cur_frm.toggle_reqd("d1", condition);

    // hide/unhide L1 field
    var condition = in_list(["Ball Nose", "Centre Drill Type A", "Centre Drill Type B", 
		"Centre Drill Type R", "Drill","Punches", "Punch Step3", "Reamer", "SQEM"], cur_frm.doc.tool_type);
    cur_frm.toggle_display("l1", condition);
	cur_frm.toggle_display("inch_l1", condition);
	cur_frm.toggle_reqd("l1", condition);

    // hide/unhide a2 field
    var condition = in_list(["Centre Drill Type A", "Centre Drill Type B", 
		"Centre Drill Type R", "Punch Step3"], cur_frm.doc.tool_type);
    cur_frm.toggle_display("a2", condition);
	cur_frm.toggle_reqd("a2", condition);

    // hide/unhide d2 field
    var condition = in_list(["Centre Drill Type B", "Punch Step3"], cur_frm.doc.tool_type);
    cur_frm.toggle_display("d2", condition);
	cur_frm.toggle_display("inch_d2", condition);
	cur_frm.toggle_reqd("d2", condition);

    // hide/unhide L2 field
    var condition = in_list(["Punch Step3"], cur_frm.doc.tool_type);
    cur_frm.toggle_display("l2", condition);
	cur_frm.toggle_display("inch_l2", condition);
	cur_frm.toggle_reqd("l2", condition);

    // hide/unhide r1 field
    var condition = in_list(["Centre Drill Type R"], cur_frm.doc.tool_type);
    cur_frm.toggle_display("r1", condition);
	cur_frm.toggle_reqd("r1", condition);
	
    // hide/unhide a3 field
    var condition = in_list(["Centre Drill Type B"], cur_frm.doc.tool_type);
    cur_frm.toggle_display("a3", condition);
	cur_frm.toggle_reqd("a3", condition);

    // hide/unhide Zn field
    var condition = in_list(["Ball Nose", "Centre Drill Type A", "Centre Drill Type B", 
		"Centre Drill Type R", "Drill", "Reamer", "SQEM"], cur_frm.doc.tool_type);
    cur_frm.toggle_display("no_of_flutes", condition);
	cur_frm.toggle_reqd("no_of_flutes", condition);

    // hide/unhide Drill Type field
    var condition = in_list(["Centre Drill Type A","Drill"], cur_frm.doc.tool_type);
    cur_frm.toggle_display("drill_type", condition);
	//cur_frm.toggle_reqd("drill_type", condition);

    // hide/unhide Special Treatment field
    var condition = in_list(["Ball Nose", "Drill", "Parting", "Reamer", "Rectangular", 
		"Round", "SQEM", "Square"], cur_frm.doc.tool_type);
    cur_frm.toggle_display("special_treatment", condition);
	cur_frm.toggle_reqd("special_treatment", condition);
	
	// hide/unhide ITEMCODE & ITEMNAME fields
	var condition = in_list(["Others"], cur_frm.doc.tool_type);
    cur_frm.toggle_display("item_code", condition);
	cur_frm.toggle_reqd("item_code", condition);
	cur_frm.toggle_display("item_name", condition);
	cur_frm.toggle_reqd("item_name", condition);
}

//**********************************************************************************************************************
//FUNCTION PERTAINING TO HIDING AND MAKING REQUISITE FIELDS MANDATORY AS PER TOOL TYPE SELECTED ENDS ABOVE THIS LINE
//**********************************************************************************************************************


//*************************************************
//FUNCTIONS PERTAINING TO INCH FIELDS
//*************************************************

//*************************************************
//Code to change inch to mm in fields.
//*************************************************

cur_frm.cscript.height_dia_inch = function(doc) {
	// suppose value of field_fraction = 4/5
	// then value of field_decimal will be set as 0.8
	cur_frm.set_value("height_dia","");
	if (Math.round(eval(doc.height_dia_inch)*25400)/1000 >0){
		cur_frm.set_value("height_dia", Math.round(eval(doc.height_dia_inch)*25400)/1000);
	}
	else{
		alert("Enter valid fraction in field, if you want to add inches greater than 1 then use 1+3/4 for 1.75 inch instead of 1-3/4");
		system.exit();
	}
}

cur_frm.cscript.width_inch = function(doc) {
	// suppose value of field_fraction = 4/5
	// then value of field_decimal will be set as 0.8
	cur_frm.set_value("width","");
	if (Math.round(eval(doc.width_inch)*25400)/1000 >0){
		cur_frm.set_value("width", Math.round(eval(doc.width_inch)*25400)/1000);
	}
	else{
		alert("Enter valid fraction in field, if you want to add inches greater than 1 then use 1+3/4 for 1.75 inch instead of 1-3/4");
		system.exit();
	}
}

cur_frm.cscript.length_inch = function(doc) {
	// suppose value of field_fraction = 4/5
	// then value of field_decimal will be set as 0.8
	cur_frm.set_value("length","");
	if (Math.round(eval(doc.length_inch)*25400)/1000 >0){
		cur_frm.set_value("length", Math.round(eval(doc.length_inch)*25400)/1000);
	}
	else{
		alert("Enter valid fraction in field, if you want to add inches greater than 1 then use 1+3/4 for 1.75 inch instead of 1-3/4");
		system.exit();
	}
}

cur_frm.cscript.d1_inch = function(doc) {
	// suppose value of field_fraction = 4/5
	// then value of field_decimal will be set as 0.8
	cur_frm.set_value("d1","");
	if (Math.round(eval(doc.d1_inch)*25400)/1000 >0){
		cur_frm.set_value("d1", Math.round(eval(doc.d1_inch)*25400)/1000);
	}
	else{
		alert("Enter valid fraction in field, if you want to add inches greater than 1 then use 1+3/4 for 1.75 inch instead of 1-3/4");
		system.exit();
	}
}

cur_frm.cscript.l1_inch = function(doc) {
	// suppose value of field_fraction = 4/5
	// then value of field_decimal will be set as 0.8
	cur_frm.set_value("l1","");
	if (Math.round(eval(doc.l1_inch)*25400)/1000 >0){
		cur_frm.set_value("l1", Math.round(eval(doc.l1_inch)*25400)/1000);
	}
	else{
		alert("Enter valid fraction in field, if you want to add inches greater than 1 then use 1+3/4 for 1.75 inch instead of 1-3/4");
		system.exit();
	}
}

cur_frm.cscript.d2_inch = function(doc) {
	// suppose value of field_fraction = 4/5
	// then value of field_decimal will be set as 0.8
	cur_frm.set_value("d2","");
	if (Math.round(eval(doc.d2_inch)*25400)/1000 >0){
		cur_frm.set_value("d2", Math.round(eval(doc.d2_inch)*25400)/1000);
	}
	else{
		alert("Enter valid fraction in field, if you want to add inches greater than 1 then use 1+3/4 for 1.75 inch instead of 1-3/4");
		system.exit();
	}
}

cur_frm.cscript.l2_inch = function(doc) {
	// suppose value of field_fraction = 4/5
	// then value of field_decimal will be set as 0.8
	cur_frm.set_value("l2","");
	if (Math.round(eval(doc.l2_inch)*25400)/1000 >0){
		cur_frm.set_value("l2", Math.round(eval(doc.l2_inch)*25400)/1000);
	}
	else{
		alert("Enter valid fraction in field, if you want to add inches greater than 1 then use 1+3/4 for 1.75 inch instead of 1-3/4");
		system.exit();
	}
}

//**********************************************************
//Code to change inch to mm in fields ENDS BEFORE THIS LINE
//**********************************************************

//Code runs when we click Inch_h button
cur_frm.cscript.inch_h = function() {

	cur_frm.toggle_enable("height_dia", cur_frm.doc.inch_h==0);
	cur_frm.toggle_display("height_dia_inch", cur_frm.doc.inch_h==1);
	cur_frm.set_value("height_dia_inch", "");
	cur_frm.set_value("height_dia", "");
	cur_frm.toggle_reqd("height_dia_inch", cur_frm.doc.inch_h==1);
}

//Code runs when we click Inch_w button
cur_frm.cscript.inch_w = function() {

	cur_frm.toggle_enable("width", cur_frm.doc.inch_w==0);
	cur_frm.toggle_display("width_inch", cur_frm.doc.inch_w==1);
	cur_frm.set_value("width_inch", "");
	cur_frm.set_value("width", "");
	cur_frm.toggle_reqd("width_inch", cur_frm.doc.inch_w==1);
}

//Code runs when we click inch_l button
cur_frm.cscript.inch_l = function() {

	cur_frm.toggle_enable("length", cur_frm.doc.inch_l==0);
	cur_frm.toggle_display("length_inch", cur_frm.doc.inch_l==1);
	cur_frm.set_value("length_inch", "");
	cur_frm.set_value("length", "");
	cur_frm.toggle_reqd("length_inch", cur_frm.doc.inch_l==1);
}

//Code runs when we click inch_l1 button
cur_frm.cscript.inch_l1 = function() {

	cur_frm.toggle_enable("l1", cur_frm.doc.inch_l1==0);
	cur_frm.toggle_display("l1_inch", cur_frm.doc.inch_l1==1);
	cur_frm.set_value("l1_inch", "");
	cur_frm.set_value("l1", "");
	cur_frm.toggle_reqd("l1_inch", cur_frm.doc.inch_l1==1);
}

//Code runs when we click inch_d1 button
cur_frm.cscript.inch_d1 = function() {

	cur_frm.toggle_enable("d1", cur_frm.doc.inch_d1==0);
	cur_frm.toggle_display("d1_inch", cur_frm.doc.inch_d1==1);
	cur_frm.set_value("d1_inch", "");
	cur_frm.set_value("d1", "");
	cur_frm.toggle_reqd("d1_inch", cur_frm.doc.inch_d1==1);
}

//Code runs when we click inch_d2 button
cur_frm.cscript.inch_d2 = function() {

	cur_frm.toggle_enable("d2", cur_frm.doc.inch_d2==0);
	cur_frm.toggle_display("d2_inch", cur_frm.doc.inch_d2==1);
	cur_frm.set_value("d2_inch", "");
	cur_frm.set_value("d2", "");
	cur_frm.toggle_reqd("d2_inch", cur_frm.doc.inch_d2==1);
}

//Code runs when we click inch_l2 button
cur_frm.cscript.inch_l2 = function() {

	cur_frm.toggle_enable("l2", cur_frm.doc.inch_l2==0);
	cur_frm.toggle_display("l2_inch", cur_frm.doc.inch_l2==1);
	cur_frm.set_value("l2_inch", "");
	cur_frm.set_value("l2", "");
	cur_frm.toggle_reqd("l2_inch", cur_frm.doc.inch_l2==1);
}

//*********************************************************
//FUNCTIONS PERTAINING TO INCH FIELDS ENDS ABOVE THIS LINE
//*********************************************************


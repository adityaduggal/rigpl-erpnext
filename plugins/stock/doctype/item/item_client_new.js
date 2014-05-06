//Reset the default fields since these fields are not applicable for new items
cur_frm.cscript.custom_onload = function () {
    if (cur_frm.doc.__islocal) {
    	var fields = ["min_order_qty", "end_of_life", "re_order_level", "show_in_website", "brand",
			"base_material", "quality", "special_treatment", "is_rm", 
			"height_dia", "height_dia_inch", "inch_h", "width", "widht_inch", "inch_w", 
			"length", "length_inch", "inch_l", "a1", "d1", "d1_inch", "inch_d1", 
			"l1", "l1_inch", "inch_l1", "a2", "d2", "d2_inch", "inch_d2", "l2", "l2_inch", "inch_l2", 
			"r1", "a3", "no_of_flutes", "drill_type"];
		for (var i in fields) {
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
cur_frm.cscript.custom_refresh = function(doc, cdt, cdn) {
    // Disable defining fields of saved items only not applicable for unsaved items data
    cur_frm.toggle_enable(["description", "tool_type","brand", "base_material", "quality", "is_rm", 
		"height_dia", "height_dia_inch", "inch_h", "width", "width_inch", "inch_w", "length", "length_inch", "inch_l", 
		"a1", "d1", "d1_inch", "inch_d1", "l1", "l1_inch", "inch_l1", "a2", "d2", "d2_inch", "inch_d2", 
		"l2", "l2_inch", "inch_l2", "r1", "no_of_flutes", "drill_type", "special_treatment", "a3"], cur_frm.doc.__islocal);
	cur_frm.toggle_enable("description",cur_frm.doc.tool_type =="Others")
	cur_frm.cscript.tool_type(doc, cdt, cdn);
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

cur_frm.cscript.tool_type = function(doc, cdt, cdn) {
	cur_frm.cscript.custom_onload();
	var tt = cur_frm.doc.tool_type;
	switch (tt)
	{
	//fd_def are defining fields which are needed to be unhidden when a Tool Type is selected
	//df2 are Dimensional fields which are needed to be unhidden but along with them there is another field to be unhidden
	//df1 are Dimensional fields which are only needed to be unhidden.
	case "Ball Nose":
		var fd_def = ["brand","base_material", "quality", "special_treatment"]; 
		var df2 = ["height_dia","length", "d1", "l1"];
		var df21 = ["inch_h","inch_l", "inch_d1", "inch_l1"]; //please keep this in same order as df2.
		var df1 =["a1", "no_of_flutes"];
		hide_all();
		sm1(fd_def,tt);
		sm2(df2, df21, tt);
		sm1(df1,tt);
		change_label(doc, cdt, cdn, tt);
		break;

	case "Centre Drill Type A":
		var fd_def = ["brand","base_material", "quality"]; 
		var df2 = ["height_dia","length", "d1", "l1"];
		var df21 = ["inch_h","inch_l", "inch_d1", "inch_l1"]; //please keep this in same order as df2.
		var df1 =["a1", "a2", "no_of_flutes"];
		var df = ["drill_type"];
		hide_all();
		sm1(fd_def,tt);
		sm2(df2, df21, tt);
		sm1(df1,tt);
		show(df,tt);
		
		break;

	case "Centre Drill Type B":
		var fd_def = ["brand","base_material", "quality"]; 
		var df2 = ["height_dia","length", "d1", "l1"];
		var df21 = ["inch_h","inch_l", "inch_d1", "inch_l1"]; //please keep this in same order as df2.
		var df1 =["a1", "a2", "no_of_flutes"];
		var df = ["drill_type"];
		hide_all();
		sm1(fd_def,tt);
		sm2(df2, df21, tt);
		sm1(df1,tt);
		show(df,tt);
		break;

	case "Centre Drill Type R":
		var fd_def = ["brand","base_material", "quality"]; 
		var df2 = ["height_dia","length", "d1", "l1"];
		var df21 = ["inch_h","inch_l", "inch_d1", "inch_l1"]; //please keep this in same order as df2.
		var df1 =["a1", "a2", "r1", "no_of_flutes"];
		hide_all();
		sm1(fd_def,tt);
		sm2(df2, df21, tt);
		sm1(df1,tt);
		break;

	case "Drill":
		var fd_def = ["brand","base_material", "quality", "special_treatment"]; 
		var df2 = ["height_dia","length", "d1", "l1"];
		var df21 = ["inch_h","inch_l", "inch_d1", "inch_l1"]; //please keep this in same order as df2.
		var df1 =["a1", "no_of_flutes"];
		var df = ["drill_type"];
		hide_all();
		sm1(fd_def,tt);
		sm2(df2, df21, tt);
		sm1(df1,tt);
		show(df,tt);
		break;

	case "Mandrels":
		var fd_def = ["brand", "base_material", "quality"]; 
		var df2 = ["height_dia","width","length"];
		var df21 = ["inch_h","inch_w","inch_l"]; //please keep this in same order as df2.
		var df1 =["a1"];
		hide_all();
		sm1(fd_def,tt);
		sm2(df2, df21, tt);
		sm1(df1,tt);
		break;
	
	case "Parting":
		var fd_def = ["brand", "base_material", "quality", "special_treatment"]; 
		var df2 = ["height_dia","width","length"];
		var df21 = ["inch_h","inch_w","inch_l"]; //please keep this in same order as df2.
		var df1 =["a1"];
		hide_all();
		sm1(fd_def,tt);
		sm2(df2, df21, tt);
		sm1(df1,tt);
		break;

	case "Punch Step3":
		var fd_def = ["brand", "base_material", "quality"]; 
		var df2 = ["height_dia","length", "d1", "l1", "d2", "l2"];
		var df21 = ["inch_h", "inch_l", "inch_d1", "inch_l1","inch_d2", "inch_l2"]; //please keep this in same order as df2.
		var df1 =["a1", "a2"];
		hide_all();
		sm1(fd_def,tt);
		sm2(df2, df21, tt);
		sm1(df1,tt);
		break;

	case "Punches":
		var fd_def = ["brand", "base_material", "quality"]; 
		var df2 = ["height_dia","length", "d1", "l1"];
		var df21 = ["inch_h", "inch_l", "inch_d1", "inch_l1"]; //please keep this in same order as df2.
		var df1 =["a1"];
		hide_all();
		sm1(fd_def,tt);
		sm2(df2, df21, tt);
		sm1(df1,tt);
		break;
		
	case "Reamer":
		var fd_def = ["brand","base_material", "quality", "special_treatment"]; 
		var df2 = ["height_dia","length", "d1", "l1"];
		var df21 = ["inch_h","inch_l", "inch_d1", "inch_l1"]; //please keep this in same order as df2.
		var df1 =["a1", "no_of_flutes"];
		hide_all();
		sm1(fd_def,tt);
		sm2(df2, df21, tt);
		sm1(df1,tt);
		break;

	case "Rectangular":
		var fd_def = ["brand", "is_rm", "base_material", "quality", "special_treatment"]; 
		var df2 = ["height_dia","width","length"];
		var df21 = ["inch_h","inch_w","inch_l"]; //please keep this in same order as df2.
		var df1 =["a1"];
		hide_all();
		sm1(fd_def,tt);
		sm2(df2, df21, tt);
		sm1(df1,tt);
		break;
		
	case "Round":
		var fd_def = ["brand", "is_rm", "base_material", "quality", "special_treatment"]; 
		var df2 = ["height_dia", "length"];
		var df21 = ["inch_h", "inch_l"]; //please keep this in same order as df2.
		var df1 =["a1"];
		hide_all();
		sm1(fd_def,tt);
		sm2(df2, df21, tt);
		sm1(df1,tt);
		break;
		
	case "SQEM":
		var fd_def = ["brand","base_material", "quality", "special_treatment"]; 
		var df2 = ["height_dia","length", "d1", "l1"];
		var df21 = ["inch_h","inch_l", "inch_d1", "inch_l1"]; //please keep this in same order as df2.
		var df1 =["a1", "no_of_flutes"];
		hide_all();
		sm1(fd_def,tt);
		sm2(df2, df21, tt);
		sm1(df1,tt);
		break;
		
	case "Square":
		var fd_def = ["brand", "is_rm", "base_material", "quality", "special_treatment"]; 
		var df2 = ["height_dia","width","length"];
		var df21 = ["inch_h","inch_w","inch_l"]; //please keep this in same order as df2.
		var df1 =["a1"];
		hide_all();
		sm1(fd_def,tt);
		sm2(df2, df21, tt);
		sm1(df1,tt);
		break;
	default:
		hide_all();
		cur_frm.toggle_display("item_code",tt);
		cur_frm.toggle_reqd("item_code", tt);
	}
}



//This function would unhide 1 field and make mandatory
function sm1(fd,tt){
	for (var i in fd){
		cur_frm.toggle_display(fd[i],true);
		cur_frm.toggle_reqd(fd[i],true);
	}
}

//This function would unhide 2 fields and make mandatory the first field (use in case of inch mm sizes)
function sm2(fd1,fd2,tt){
	for (var i in fd1){
		cur_frm.toggle_display(fd1[i],tt);
		cur_frm.toggle_reqd(fd1[i],tt);
		cur_frm.toggle_display(fd2[i],tt);
	}
}

//This function is only for unhiding a field and making it mandatory
function show(fd,tt){
	for (var i in fd){
		cur_frm.toggle_display(fd[i],tt);
	}
}

function hide_all(){
	var hide = ["brand", "is_rm", "base_material", "quality", "special_treatment",
	"height_dia","inch_h", "height_dia_inch", 
	"width", "inch_w", "width_inch", 
	"length","inch_l","length_inch", 
	"d1","inch_d1", "d1_inch",
	"l1", "inch_l1", "l1_inch",
	"d2","inch_d2", "d2_inch", 
	"l2", "inch_l2", "l2_inch", 
	"a1", "a2", "a3", "item_code",
	"r1", "no_of_flutes", "drill_type"]
	for (var i in hide){
		cur_frm.toggle_display(hide[i], false)
	}
}

function change_label(doc, cdt, cdn, tt){
	var labels = {
		"Ball Nose": {
			"height_dia": "Shank Dia (mm)",
			"height_dia_inch": "Shank Dia (inch)"
		}
	}
	for(fieldname in labels[tt]) {
	// change the labels
	//alert(fieldname);
	//alert(labels[tt][fieldname]);
	//$('[data-grid-fieldname="Item-' + fieldname + '"]').html(labels[tt][fieldname]);
	cur_frm.set_df_property(label[i], "label", "My Label")
	}
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
	var mmfd = "height_dia";
	var inchfd = doc.height_dia_inch
	inch_mm(mmfd,inchfd);
}

cur_frm.cscript.width_inch = function(doc) {
	var mmfd = "width";
	var inchfd = doc.width_inch
	inch_mm(mmfd,inchfd);
}

cur_frm.cscript.length_inch = function(doc) {
	var mmfd = "length";
	var inchfd = doc.length_inch
	inch_mm(mmfd,inchfd);
}

cur_frm.cscript.d1_inch = function(doc) {
	var mmfd = "d1";
	var inchfd = doc.d1_inch
	inch_mm(mmfd,inchfd);
}

cur_frm.cscript.l1_inch = function(doc) {
	var mmfd = "l1";
	var inchfd = doc.l1_inch
	inch_mm(mmfd,inchfd);
}

cur_frm.cscript.d2_inch = function(doc) {
	var mmfd = "d2";
	var inchfd = doc.d2_inch
	inch_mm(mmfd,inchfd);
}

cur_frm.cscript.l2_inch = function(doc) {
	var mmfd = "l2";
	var inchfd = doc.l2_inch
	inch_mm(mmfd,inchfd);
}

function inch_mm(mmfd, inchfd){
	cur_frm.set_value(mmfd,"");
	cal = Math.round(eval(inchfd) * 25400)/1000;
	if (cal >0){
		cur_frm.set_value(mmfd, cal);
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
	inch_check("height_dia", "height_dia_inch", cur_frm.doc.inch_h);
}

//Code runs when we click Inch_w button
cur_frm.cscript.inch_w = function() {
	inch_check("width", "width_inch", cur_frm.doc.inch_w);
}

//Code runs when we click inch_l button
cur_frm.cscript.inch_l = function() {
	inch_check("length", "length_inch", cur_frm.doc.inch_l);
}

//Code runs when we click inch_l1 button
cur_frm.cscript.inch_l1 = function() {
	inch_check("l1", "l1_inch", cur_frm.doc.inch_l1);
}

//Code runs when we click inch_d1 button
cur_frm.cscript.inch_d1 = function() {
	inch_check("d1", "d1_inch", cur_frm.doc.inch_d1);
}

//Code runs when we click inch_d2 button
cur_frm.cscript.inch_d2 = function() {
	inch_check("d1", "d22_inch", cur_frm.doc.inch_d2);
}

//Code runs when we click inch_l2 button
cur_frm.cscript.inch_l2 = function() {
	inch_check("l2", "l2_inch", cur_frm.doc.inch_l2);
}

function inch_check(mmfield, inchfield, check){
	cur_frm.toggle_enable(mmfield, check==0);
	cur_frm.toggle_display(inchfield, check==1);
	cur_frm.set_value(inchfield, "");
	cur_frm.toggle_reqd(inchfield, check==1);
}

//*********************************************************
//FUNCTIONS PERTAINING TO INCH FIELDS ENDS ABOVE THIS LINE
//*********************************************************


    function fillModal(id) {
        var date = $("#date_"+id).html();
	var description = $("#description_"+id).html();
	var category = $("#category_"+id).html();
	var type_description = $("#type_description_"+id).html();
	var amount = $("#amount_"+id).html();
        var record = $("#record_"+id).find("b").html();
        var description = $("#description_"+id).find("small").html().replace(/&amp;/g, '&');
	var message =  date + " " + description + " " + category + " " + type_description + " " + amount + " " + record +  " " + description + " "
	alert(message)
    }

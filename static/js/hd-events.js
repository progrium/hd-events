var rounder = function(elem, sz, allBrowsers) {
  // rounded corners JS, handles IE7, 8 too:
  DD_roundies.addRule(elem, sz.toString()+'px', allBrowsers);
}
$(function() {
  var rndrs = ['#primary'];
  for(r in rndrs) {
    rounder(rndrs[r], 8, true);
  }

  // Generic handler for retaining values when form submit errored out
  var formvalues = $.cookie('formvalues');
  if (formvalues) {
    try {
      formvalues = JSON.parse(formvalues);
      if (formvalues != null) {
        for (var key in formvalues) {
          if (key!=rooms) {
            $('[name='+key+']').val(formvalues[key]);
          }
        }      
        $.each($('[name=rooms]'), function(key, value) { 
          if ($(value).val()==formvalues["rooms"]) {
            $(value).attr("checked", "checked");
          }
        });
      }
    } catch (err) {
      // noop
    }
  }

});

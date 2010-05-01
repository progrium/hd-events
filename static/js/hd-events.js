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
    formvalues = JSON.parse(formvalues);
    for (var key in formvalues) {
      $('[name='+key+']').val(formvalues[key]);
    }
    $('select[name=type]').val(formvalues['type']);
  }

});

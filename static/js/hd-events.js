var rounder = function(elem, sz, allBrowsers) {
  // rounded corners JS, handles IE7, 8 too:
  DD_roundies.addRule(elem, sz.toString()+'px', allBrowsers);
}
$(function() {
  var rndrs = ['#primary'];
  for(r in rndrs) {
    rounder(rndrs[r], 8, true);
  }

});

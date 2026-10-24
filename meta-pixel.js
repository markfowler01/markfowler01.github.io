// Meta Pixel for absoluteadas.com. OFF until META_PIXEL_ID is filled in.
// Turn on: Meta Events Manager > Connect data > Web > Meta Pixel, then paste the ID below.
// Tracks PageView, a Contact event when someone taps a tel: or sms: link (the
// 1-844-FIX-ADAS call is the conversion the ads are built around), and a Lead
// event on any form submit (job request, calculator, partners).
(function () {
  var META_PIXEL_ID = ''
  if (!META_PIXEL_ID) return
  !function (f, b, e, v, n, t, s) { if (f.fbq) return; n = f.fbq = function () { n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments) }; if (!f._fbq) f._fbq = n; n.push = n; n.loaded = !0; n.version = '2.0'; n.queue = []; t = b.createElement(e); t.async = !0; t.src = v; s = b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t, s) }(window, document, 'script', 'https://connect.facebook.net/en_US/fbevents.js')
  fbq('init', META_PIXEL_ID)
  fbq('track', 'PageView')
  document.addEventListener('click', function (ev) {
    var a = ev.target && ev.target.closest ? ev.target.closest('a[href^="tel:"], a[href^="sms:"]') : null
    if (a) fbq('track', 'Contact', { method: a.getAttribute('href').slice(0, 3) })
  }, true)
  document.addEventListener('submit', function () { fbq('track', 'Lead') }, true)
})()

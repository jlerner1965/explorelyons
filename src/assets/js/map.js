// The map. Leaflet (self-hosted) over OpenStreetMap tiles, loaded only when
// the visitor opens it, so a page view sends nothing to a tile server until
// asked. Pins come from an inline JSON block written by the build; "On the
// map" links elsewhere on the page open the map and the matching pin.
(function () {
  var root = document.querySelector('[data-map]');
  var dataEl = document.querySelector('script[data-map-pins]');
  if (!root || !dataEl) return;
  var pins;
  try { pins = JSON.parse(dataEl.textContent); } catch (e) { return; }
  var map = null, markers = {}, loading = null;
  var COLORS = { eat: '#C1563A', shop: '#963F28', stay: '#E2B35C', park: '#2B6F73', trail: '#2F4A3B', landmark: '#6B2F23', culture: '#6B2F23', outdoor: '#2F4A3B' };
  var LABELS = { eat: 'Eat & drink', shop: 'Shops & provisions', stay: 'Stay', park: 'Parks', trail: 'Trails', landmark: 'Landmarks', culture: 'Venues & museums', outdoor: 'Outdoor & recreation' };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  function load() {
    if (loading) return loading;
    loading = new Promise(function (resolve, reject) {
      if (window.L) return resolve();
      var css = document.createElement('link'); css.rel = 'stylesheet'; css.href = '/assets/vendor/leaflet/leaflet.css'; document.head.appendChild(css);
      var js = document.createElement('script'); js.src = '/assets/vendor/leaflet/leaflet.js'; js.onload = resolve; js.onerror = reject; document.head.appendChild(js);
    });
    return loading;
  }

  function icon(kind) {
    return L.divIcon({ className: 'l-pin', html: '<span style="background:' + (COLORS[kind] || COLORS.landmark) + '"></span>', iconSize: [16, 16], iconAnchor: [8, 8], popupAnchor: [0, -10] });
  }

  function open(focusId) {
    var box = root.querySelector('[data-map-canvas]');
    var btn = root.querySelector('[data-map-open]');
    load().then(function () {
      if (!map) {
        if (btn) btn.hidden = true;
        box.hidden = false;
        map = L.map(box, { scrollWheelZoom: false });
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" rel="noopener">OpenStreetMap</a> contributors' }).addTo(map);
        var bounds = [];
        pins.forEach(function (p) {
          var m = L.marker([p.lat, p.lng], { icon: icon(p.kind), title: p.name }).addTo(map);
          var html = '<strong>' + esc(p.name) + '</strong>' + (p.addr ? '<br>' + esc(p.addr) : '') + (p.blurb ? '<br><span class="l-small" style="font-size:.85rem">' + esc(p.blurb) + '</span>' : '');
          var links = [];
          if (p.url) links.push('<a href="' + esc(p.url) + '" rel="noopener">Website &#8599;</a>');
          if (p.href) links.push('<a href="' + esc(p.href) + '">On this site &#8594;</a>');
          links.push('<a href="https://www.openstreetmap.org/directions?to=' + p.lat + '%2C' + p.lng + '" rel="noopener">Directions &#8599;</a>');
          m.bindPopup(html + '<br>' + links.join(' &#183; '));
          markers[p.id] = m;
          bounds.push([p.lat, p.lng]);
        });
        if (bounds.length) map.fitBounds(bounds, { padding: [24, 24], maxZoom: 16 });
        var legend = root.querySelector('[data-map-legend]');
        if (legend) {
          var kinds = [];
          pins.forEach(function (p) { if (kinds.indexOf(p.kind) === -1) kinds.push(p.kind); });
          legend.innerHTML = kinds.map(function (k) { return '<span><i style="background:' + COLORS[k] + '"></i>' + esc(LABELS[k] || k) + '</span>'; }).join('');
        }
      }
      if (focusId && markers[focusId]) {
        var m = markers[focusId];
        map.setView(m.getLatLng(), Math.max(map.getZoom(), 16));
        m.openPopup();
      }
      if (focusId) root.scrollIntoView({ block: 'start', behavior: 'smooth' });
      setTimeout(function () { map.invalidateSize(); }, 50);
    }).catch(function () {
      var f = root.querySelector('[data-map-fallback]');
      if (f) f.hidden = false;
    });
  }

  var btn = root.querySelector('[data-map-open]');
  if (btn) btn.addEventListener('click', function () { open(); });
  if (root.hasAttribute('data-map-auto')) {
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) { if (entries.some(function (e) { return e.isIntersecting; })) { io.disconnect(); open(); } }, { rootMargin: '200px' });
      io.observe(root);
    } else open();
  }
  document.querySelectorAll('[data-pin]').forEach(function (a) {
    a.addEventListener('click', function (e) { e.preventDefault(); open(a.getAttribute('data-pin')); });
  });
  if (location.hash.indexOf('#pin=') === 0) open(location.hash.slice(5));
})();

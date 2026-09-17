// Month view for the events page. The occurrences are inlined by the build
// as JSON; the upcoming list above the calendar works without this file.
(function () {
  var root = document.querySelector('[data-cal]');
  var dataEl = document.querySelector('script[data-cal-data]');
  if (!root || !dataEl) return;
  var events;
  try { events = JSON.parse(dataEl.textContent); } catch (e) { return; }

  var byDate = {};
  events.forEach(function (ev) { (byDate[ev.date] = byDate[ev.date] || []).push(ev); });

  var today = new Date();
  var todayIso = iso(today);
  var params = new URLSearchParams(location.search);
  var start = params.get('date') && /^\d{4}-\d{2}-\d{2}$/.test(params.get('date')) ? params.get('date') : todayIso;
  var view = new Date(start.slice(0, 4), parseInt(start.slice(5, 7), 10) - 1, 1);
  var selected = params.get('date') ? start : null;

  var label = root.querySelector('[data-cal-label]');
  var grid = root.querySelector('[data-cal-grid]');
  var list = root.querySelector('[data-cal-list]');
  var months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  var dows = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  function iso(d) { return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function longDate(s) { var d = new Date(s + 'T12:00:00'); return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }); }

  function render() {
    label.textContent = months[view.getMonth()] + ' ' + view.getFullYear();
    var html = dows.map(function (d) { return '<div class="l-cal-dow" aria-hidden="true">' + d + '</div>'; }).join('');
    var first = new Date(view.getFullYear(), view.getMonth(), 1);
    var lead = first.getDay();
    var days = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate();
    var cells = [];
    for (var i = 0; i < lead; i++) cells.push(null);
    for (var d = 1; d <= days; d++) cells.push(new Date(view.getFullYear(), view.getMonth(), d));
    while (cells.length % 7) cells.push(null);
    cells.forEach(function (d) {
      if (!d) { html += '<div class="l-cal-day l-cal-day--out" aria-hidden="true"></div>'; return; }
      var k = iso(d), n = (byDate[k] || []).length;
      var cls = 'l-cal-day' + (n ? ' l-cal-day--has' : '') + (k === todayIso ? ' l-cal-day--today' : '') + (k === selected ? ' l-cal-day--on' : '');
      var when = months[d.getMonth()] + ' ' + d.getDate() + ', ' + d.getFullYear();
      if (n) html += '<button type="button" class="' + cls + '" data-day="' + k + '" aria-label="' + when + ', ' + n + (n === 1 ? ' event' : ' events') + '"><span class="l-cal-n">' + d.getDate() + '</span><span class="l-cal-dot"></span><span class="l-cal-count">' + n + '</span></button>';
      else html += '<div class="' + cls + '"><span class="l-cal-n">' + d.getDate() + '</span></div>';
    });
    grid.innerHTML = html;
    renderList();
  }

  function renderList() {
    if (!selected) { list.innerHTML = '<p class="l-small" style="margin:0">Choose a marked day to see what is on.</p>'; return; }
    var evs = byDate[selected] || [];
    var html = '<div class="l-label l-label--quiet">' + esc(longDate(selected)) + '</div>';
    if (!evs.length) html += '<p class="l-body" style="margin:10px 0 0">Nothing listed for this day.</p>';
    evs.forEach(function (ev) {
      html += '<article class="l-up" style="margin-top:16px" id="ev-' + esc(ev.id) + '-' + esc(ev.date) + '">'
        + '<div class="l-label">' + esc(ev.time || 'All day') + '</div>'
        + '<h3 class="l-h3">' + esc(ev.title) + '</h3>'
        + (ev.venue ? '<div class="l-body">' + esc(ev.venue) + (ev.address ? ' · ' + esc(ev.address) : '') + '</div>' : '')
        + '<div class="l-small">' + esc([ev.organizer, ev.cost].filter(Boolean).join(' · ')) + '</div>'
        + (ev.detail ? '<p class="l-body" style="margin:0;font-size:.9375rem;max-width:60ch">' + esc(ev.detail) + '</p>' : '')
        + (ev.url ? '<a class="l-link" href="' + esc(ev.url) + '" rel="noopener">Organizer page <span aria-hidden="true">&#8599;</span></a>' : '')
        + '</article>';
    });
    list.innerHTML = html;
  }

  root.addEventListener('click', function (e) {
    var day = e.target.closest('[data-day]');
    if (day) { selected = day.getAttribute('data-day'); render(); if (history.replaceState) history.replaceState(null, '', location.pathname + '?date=' + selected + '#cal-h'); return; }
    var nav = e.target.closest('[data-cal-nav]');
    if (nav) { view = new Date(view.getFullYear(), view.getMonth() + parseInt(nav.getAttribute('data-cal-nav'), 10), 1); render(); }
  });
  document.querySelectorAll('[data-jump]').forEach(function (b) {
    b.addEventListener('click', function () { selected = b.getAttribute('data-jump'); view = new Date(selected.slice(0, 4), parseInt(selected.slice(5, 7), 10) - 1, 1); render(); root.scrollIntoView({ block: 'start' }); });
  });
  render();
})();

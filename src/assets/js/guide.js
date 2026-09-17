// Explore Lyons — page behaviours. No dependencies.
(function () {
  var shown = {}; // event id+date already placed in the weekend module

  function isoOf(d) { return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }
  function fmtShort(iso) { var d = new Date(iso + 'T12:00:00'); return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }); }

  // Mobile navigation. Every path that changes the menu goes through setOpen,
  // so the expanded state and the accessible name can never disagree.
  function nav() {
    var head = document.querySelector('.l-head');
    var btn = head && head.querySelector('.l-burger');
    if (!head || !btn || btn.dataset.wired) return;
    btn.dataset.wired = '1';
    function setOpen(open) {
      head.classList.toggle('l-open', open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      btn.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    }
    btn.addEventListener('click', function () { setOpen(!head.classList.contains('l-open')); });
    head.querySelectorAll('.l-nav a').forEach(function (a) { a.addEventListener('click', function () { setOpen(false); }); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && head.classList.contains('l-open')) { setOpen(false); btn.focus(); }
    });
  }

  // "This weekend": the coming Friday to Sunday (or the rest of this one).
  // The list is rendered at build time with the next few weeks of events;
  // this narrows it to the window and rewrites the heading. With nothing in
  // the window it falls back to the next three dated events.
  function weekend() {
    var list = document.querySelector('[data-weekend]');
    if (!list) return;
    var today = new Date();
    var dow = today.getDay();
    var start = new Date(today);
    if (dow >= 1 && dow <= 4) start.setDate(today.getDate() + (5 - dow));
    var end = new Date(start);
    end.setDate(start.getDate() + (start.getDay() === 0 ? 0 : 7 - start.getDay()));
    var s = isoOf(start), e = isoOf(end), t = isoOf(today);
    var cards = Array.prototype.slice.call(list.querySelectorAll('[data-event-date]'));
    var inWindow = cards.filter(function (c) { var d = c.getAttribute('data-event-date'); return d >= s && d <= e && d >= t; });
    var pick = inWindow.length ? inWindow.slice(0, 6) : cards.filter(function (c) { return c.getAttribute('data-event-date') >= t; }).slice(0, 3);
    cards.forEach(function (c) { c.hidden = pick.indexOf(c) === -1; });
    pick.forEach(function (c) { shown[c.getAttribute('data-event-id') + '|' + c.getAttribute('data-event-date')] = true; });
    var h = document.querySelector('[data-weekend-heading]');
    var sub = document.querySelector('[data-weekend-sub]');
    if (h) h.textContent = inWindow.length ? 'This weekend in Lyons' : 'Coming up in Lyons';
    if (sub) sub.textContent = inWindow.length ? (fmtShort(s) + (s === e ? '' : ' to ' + fmtShort(e))) : 'The next dated events on the calendar';
    var empty = list.parentElement.querySelector('[data-weekend-empty]');
    if (empty) empty.hidden = pick.length > 0;
  }

  // Upcoming lists are rendered at build time; past entries leave on their
  // own, and anything already shown in the weekend module is skipped.
  function upcoming() {
    var iso = isoOf(new Date());
    document.querySelectorAll('[data-upcoming]').forEach(function (list) {
      var limit = parseInt(list.getAttribute('data-limit') || '0', 10);
      var count = 0;
      list.querySelectorAll('[data-event-date]').forEach(function (el) {
        var past = el.getAttribute('data-event-date') < iso;
        var dup = list.hasAttribute('data-skip-shown') && shown[el.getAttribute('data-event-id') + '|' + el.getAttribute('data-event-date')];
        var over = limit && count >= limit;
        el.hidden = past || dup || over;
        if (!el.hidden) count++;
      });
      var empty = list.parentElement.querySelector('[data-upcoming-empty]');
      if (empty) empty.hidden = count > 0;
    });
  }

  // River gauge: Colorado DWR station SVCLYOCO, "Saint Vrain Creek at Lyons",
  // 15-minute readings. The reading is turned into a plain sentence using the
  // rule-of-thumb levels on the river page. If the request fails the element
  // keeps its static text, which links to the gauge itself.
  function gauge() {
    var els = document.querySelectorAll('[data-gauge]');
    if (!els.length || !window.fetch) return;
    var since = new Date(); since.setDate(since.getDate() - 2);
    var mmddyyyy = String(since.getMonth() + 1).padStart(2, '0') + '/' + String(since.getDate()).padStart(2, '0') + '/' + since.getFullYear();
    var url = 'https://dwr.state.co.us/Rest/GET/api/v2/telemetrystations/telemetrytimeseriesraw/?format=json&abbrev=SVCLYOCO&parameter=DISCHRG&startDate=' + encodeURIComponent(mmddyyyy);
    function reading(cfs) {
      if (cfs < 40) return { word: 'Low', note: 'Too shallow for tubes; fine for wading, fishing and the whitewater-park rocks.' };
      if (cfs < 100) return { word: 'Mellow', note: 'Easy tubing through LaVern M. Johnson Park; kids’ water with a life jacket.' };
      if (cfs < 300) return { word: 'Prime', note: 'The classic tubing level from the Apple Valley bridge down through town.' };
      if (cfs < 700) return { word: 'Fast', note: 'Quick and pushy: life jackets, experienced floaters, no first-timers.' };
      if (cfs < 1200) return { word: 'High', note: 'Not for tubes. Kayakers and rafters only; the park features wash out.' };
      return { word: 'Flood stage', note: 'Stay off the water and away from the banks; the Town posts advisories.' };
    }
    fetch(url).then(function (r) { return r.json(); }).then(function (d) {
      var rows = (d && d.ResultList) || [];
      if (!rows.length) throw new Error('no data');
      var last = rows[rows.length - 1];
      var cfs = Number(last.measValue);
      var when = new Date(last.measDateTime);
      var r = reading(cfs);
      els.forEach(function (el) {
        var v = el.querySelector('[data-gauge-value]'); if (v) v.textContent = Math.round(cfs).toLocaleString('en-US') + ' cfs';
        var w = el.querySelector('[data-gauge-word]'); if (w) w.textContent = r.word;
        var n = el.querySelector('[data-gauge-note]'); if (n) n.textContent = r.note;
        var t = el.querySelector('[data-gauge-time]'); if (t) t.textContent = 'Read ' + when.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' at the Lyons gauge';
        el.setAttribute('data-gauge-level', r.word.toLowerCase().replace(' ', '-'));
        el.classList.add('l-gauge--live');
      });
    }).catch(function () {
      els.forEach(function (el) { el.classList.add('l-gauge--offline'); });
    });
  }

  // Contact form: posts to the endpoint in data-endpoint when one is set;
  // otherwise it explains that nothing was sent and offers the email instead.
  function contact() {
    var form = document.querySelector('[data-contact-form]');
    if (!form) return;
    var endpoint = form.getAttribute('data-endpoint') || '';
    var kind = form.querySelector('#v-kind');
    var srcNote = form.querySelector('[data-source-note]');
    var src = form.querySelector('#v-src');
    function syncSource() {
      var opt = kind && kind.options[kind.selectedIndex];
      var req = !!(opt && opt.hasAttribute('data-requires-source'));
      if (src) src.required = req;
      if (srcNote) srcNote.textContent = req ? '(required for corrections)' : '(optional)';
    }
    if (kind) { kind.addEventListener('change', syncSource); syncSource(); }
    form.addEventListener('submit', function (e) {
      if (!endpoint) {
        e.preventDefault();
        var tpl = document.querySelector('template[data-form-unavailable]');
        if (tpl && !form.querySelector('[data-message]')) form.appendChild(tpl.content.cloneNode(true));
        return;
      }
      if (!window.fetch) return; // plain POST
      e.preventDefault();
      var btn = form.querySelector('button[type=submit]');
      if (btn) btn.disabled = true;
      fetch(endpoint, { method: 'POST', headers: { Accept: 'application/json' }, body: new FormData(form) })
        .then(function (r) { if (!r.ok) throw new Error(r.status); form.reset(); syncSource(); var t = document.querySelector('template[data-form-success]'); if (t) form.appendChild(t.content.cloneNode(true)); })
        .catch(function () { var t = document.querySelector('template[data-form-unavailable]'); if (t && !form.querySelector('[data-message]')) form.appendChild(t.content.cloneNode(true)); })
        .then(function () { if (btn) btn.disabled = false; });
    });
  }

  // "Right now": the build writes the current month; a visitor a month later
  // gets their own month from the inline data. Itinerary cards get a
  // "Good now" tag when their months include this one.
  function now() {
    var month = new Date().getMonth() + 1;
    document.querySelectorAll('[data-now]').forEach(function (el) {
      if (parseInt(el.getAttribute('data-now-month'), 10) === month) return;
      var dataEl = el.querySelector('script[data-now-data]');
      if (!dataEl) return;
      var months; try { months = JSON.parse(dataEl.textContent); } catch (e) { return; }
      var m = months[String(month)]; if (!m) return;
      var h = el.querySelector('[data-now-headline]'); if (h) h.textContent = m.headline;
      var b = el.querySelector('[data-now-body]'); if (b) b.textContent = m.body;
      var l = el.querySelector('[data-now-links]');
      if (l) l.innerHTML = m.links.map(function (x) { var ext = /^https?:/.test(x[1]); return '<a class="l-link" href="' + x[1].replace(/"/g, '&quot;') + '"' + (ext ? ' rel="noopener"' : '') + '>' + x[0].replace(/</g, '&lt;') + ' <span aria-hidden="true">' + (ext ? '\u2197' : '\u2192') + '</span></a>'; }).join(' ');
      el.setAttribute('data-now-month', String(month));
    });
    document.querySelectorAll('.l-itin-card[data-months]').forEach(function (card) {
      var ok = card.getAttribute('data-months').split(' ').indexOf(String(month)) !== -1;
      var tag = card.querySelector('[data-good-now]');
      if (tag) tag.hidden = !ok;
    });
  }

  function init() { nav(); weekend(); upcoming(); gauge(); now(); contact(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

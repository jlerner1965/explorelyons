// Explore Lyons — page behaviours. No dependencies.
(function () {
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

  // Upcoming lists are rendered at build time; past entries leave on their own.
  function upcoming() {
    var today = new Date();
    var iso = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
    document.querySelectorAll('[data-upcoming]').forEach(function (list) {
      var limit = parseInt(list.getAttribute('data-limit') || '0', 10);
      var shown = 0;
      list.querySelectorAll('[data-event-date]').forEach(function (el) {
        var past = el.getAttribute('data-event-date') < iso;
        var over = limit && shown >= limit;
        el.hidden = past || over;
        if (!el.hidden) shown++;
      });
      var empty = list.parentElement.querySelector('[data-upcoming-empty]');
      if (empty) empty.hidden = shown > 0;
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

  function init() { nav(); upcoming(); contact(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

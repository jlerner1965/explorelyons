// Directory search and category filter. The rows are in the page already;
// this only shows and hides them, so the list works without scripting.
(function () {
  var form = document.querySelector('[data-dir-filters]');
  if (!form) return;
  var q = form.querySelector('#dir-q');
  var radios = form.querySelectorAll('input[name=category]');
  var select = document.querySelector('[data-dir-select]');
  var rows = document.querySelectorAll('[data-dir-row]');
  var groups = document.querySelectorAll('[data-dir-group]');
  var count = document.querySelector('[data-dir-count]');
  var active = document.querySelector('[data-dir-active]');
  var activeLabel = document.querySelector('[data-dir-active-label]');
  var clear = document.querySelector('[data-dir-clear]');
  var labels = {};
  radios.forEach(function (r) { labels[r.value] = r.parentElement.querySelector('[data-chip-label]').textContent; });

  function norm(s) { return (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }
  function category() { var c = form.querySelector('input[name=category]:checked'); return c ? c.value : 'all'; }

  function apply(push) {
    var cat = category();
    var term = norm(q.value.trim());
    var shown = 0;
    rows.forEach(function (row) {
      var cats = (row.getAttribute('data-cats') || '').split(' ');
      var okCat = cat === 'all' || cats.indexOf(cat) !== -1;
      var okTerm = !term || norm(row.getAttribute('data-search')).indexOf(term) !== -1;
      row.hidden = !(okCat && okTerm);
      if (!row.hidden) shown++;
    });
    groups.forEach(function (g) {
      var any = g.querySelector('[data-dir-row]:not([hidden])');
      g.hidden = !any;
      if (any && (cat !== 'all' || term)) g.open = true;
    });
    if (count) count.textContent = shown + (shown === 1 ? ' listing' : ' listings');
    var filtering = cat !== 'all' || term;
    if (active) active.hidden = !filtering;
    if (activeLabel) activeLabel.textContent = (cat !== 'all' ? labels[cat] : 'all categories') + (term ? ' matching “' + q.value.trim() + '”' : '');
    if (select && select.value !== cat) select.value = cat;
    if (push) syncUrl();
  }

  // The address bar catches up once typing pauses, not on every keystroke:
  // Safari throws a SecurityError after about a hundred replaceState calls in
  // thirty seconds, which is a sentence of typing, and the throw would take
  // the filter down with it. The list itself still filters as you type.
  var urlTimer = null;
  function syncUrl() {
    if (!history.replaceState) return;
    if (urlTimer) clearTimeout(urlTimer);
    urlTimer = setTimeout(function () {
      urlTimer = null;
      var p = new URLSearchParams();
      if (category() !== 'all') p.set('category', category());
      if (q.value.trim()) p.set('q', q.value.trim());
      var s = p.toString();
      try {
        history.replaceState(null, '', location.pathname + (s ? '?' + s : '') + location.hash);
      } catch (e) { /* a rate limit here must never break the filtering */ }
    }, 250);
  }

  // Initial state from the URL, so category links elsewhere land filtered.
  var params = new URLSearchParams(location.search);
  var c0 = params.get('category');
  if (c0) radios.forEach(function (r) { r.checked = r.value === c0; });
  if (params.get('q')) q.value = params.get('q');

  radios.forEach(function (r) { r.addEventListener('change', function () { apply(true); }); });
  if (select) select.addEventListener('change', function () { radios.forEach(function (r) { r.checked = r.value === select.value; }); apply(true); });
  q.addEventListener('input', function () { apply(true); });
  form.addEventListener('submit', function (e) { e.preventDefault(); apply(true); });
  if (clear) clear.addEventListener('click', function () { q.value = ''; radios.forEach(function (r) { r.checked = r.value === 'all'; }); apply(true); q.focus(); });
  apply(false);
})();

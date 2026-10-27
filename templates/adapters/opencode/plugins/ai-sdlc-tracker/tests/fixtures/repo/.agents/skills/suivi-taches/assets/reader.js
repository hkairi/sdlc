/* reader.js — lecteur Markdown des fichiers de suivi de la skill suivi-taches.
 *
 * S'initialise tout seul si la page contient un élément `#reader`. Lit le contenu des `.md`
 * embarqué dans le bloc `<script id="docs-data">` (produit par render.py). Reprend le
 * comportement du lecteur de `suivi-projet` : markdown-it embarqué, HTML brut désactivé,
 * rendu OpenSpec (deltas, exigences, scénarios, mots-clés), cases à cocher, sommaire,
 * liens `.md` relatifs ouverts dans le lecteur, version embarquée en `file://` et version
 * live (fetch) en http.
 */
(function () {
  'use strict';
  var CATS = [
    { k: 'proposal', t: 'Proposition', i: '📋' },
    { k: 'design', t: 'Design', i: '🎨' },
    { k: 'specs', t: 'Deltas de spec', i: '📐' },
    { k: 'tasks', t: 'Tâches', i: '✅' },
    { k: 'docs', t: 'Documents', i: '📄' }
  ];
  function catOf(p) {
    if (/proposal\.md$/.test(p)) return 'proposal';
    if (/design\.md$/.test(p)) return 'design';
    if (/tasks\.md$/.test(p)) return 'tasks';
    if (/\/specs\//.test(p)) return 'specs';
    return 'docs';
  }
  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function resolvePath(base, rel) {
    var parts = (base || '').split('/').slice(0, -1);
    rel.split('/').forEach(function (seg) {
      if (seg === '..') parts.pop();
      else if (seg && seg !== '.') parts.push(seg);
    });
    return parts.join('/');
  }
  function wrapUntil(el, stop, cls) {
    var box = document.createElement('div');
    box.className = cls;
    el.parentNode.insertBefore(box, el);
    var n = el;
    while (n && !(n !== el && n.nodeType === 1 && stop.indexOf(n.tagName) >= 0)) {
      var nx = n.nextSibling; box.appendChild(n); n = nx;
    }
    return box;
  }
  function label(h, re, txt) {
    h.innerHTML = h.innerHTML.replace(re, '');
    h.insertAdjacentHTML('afterbegin', '<span class="os-lbl">' + txt + '</span>');
  }
  function enhance(root) {
    Array.prototype.slice.call(root.querySelectorAll('li')).forEach(function (li) {
      var n = li.firstChild;
      if (n && n.nodeType === 1 && n.tagName === 'P') n = n.firstChild;
      var m = n && n.nodeType === 3 && n.nodeValue.match(/^\[( |x|X)\]\s*/);
      if (!m) return;
      var on = m[1] !== ' ';
      n.nodeValue = n.nodeValue.slice(m[0].length);
      var cb = document.createElement('span');
      cb.className = 'cb' + (on ? ' on' : '');
      cb.textContent = on ? '✓' : '';
      cb.setAttribute('role', 'img');
      cb.setAttribute('aria-label', on ? 'fait' : 'à faire');
      n.parentNode.insertBefore(cb, n);
      li.classList.add('task');
    });
    var DELTA = { ADDED: ['os-added', 'Ajouté'], MODIFIED: ['os-modified', 'Modifié'],
                  REMOVED: ['os-removed', 'Supprimé'], RENAMED: ['os-renamed', 'Renommé'] };
    Array.prototype.slice.call(root.querySelectorAll('h2')).forEach(function (h) {
      var m = h.textContent.match(/^(ADDED|MODIFIED|REMOVED|RENAMED) Requirements/);
      if (m) h.insertAdjacentHTML('afterbegin', '<span class="os-delta ' + DELTA[m[1]][0] + '">' + DELTA[m[1]][1] + '</span>');
    });
    Array.prototype.slice.call(root.querySelectorAll('h3')).filter(function (h) {
      return /^Requirement:/.test(h.textContent);
    }).forEach(function (h) {
      var box = wrapUntil(h, ['H1', 'H2', 'H3'], 'os-req');
      label(h, /^Requirement:\s*/, 'Exigence');
      Array.prototype.slice.call(box.querySelectorAll('h4')).filter(function (x) {
        return /^Scenario:/.test(x.textContent);
      }).forEach(function (x) {
        wrapUntil(x, ['H1', 'H2', 'H3', 'H4'], 'os-scn');
        label(x, /^Scenario:\s*/, 'Scénario');
      });
    });
    Array.prototype.slice.call(root.querySelectorAll('strong')).forEach(function (b) {
      if (/^(GIVEN|WHEN|THEN|AND)$/.test(b.textContent.trim())) b.classList.add('kw');
    });
    Array.prototype.slice.call(root.querySelectorAll('a[href]')).forEach(function (a) {
      if (/^https?:/i.test(a.getAttribute('href'))) { a.target = '_blank'; a.rel = 'noopener'; }
    });
  }
  function init() {
    var reader = document.getElementById('reader');
    if (!reader) return;
    var DD = {};
    try { DD = JSON.parse(document.getElementById('docs-data').textContent) || {}; } catch (e) { DD = {}; }
    var files = (DD && DD.files && typeof DD.files === 'object') ? DD.files : {};
    var prefix = reader.getAttribute('data-prefix') || '';
    var navEl = document.getElementById('rnav');
    var view = document.getElementById('rview');
    var search = document.getElementById('rsearch');
    if (!navEl || !view) return;
    var mdit = window.markdownit ? window.markdownit({ html: false, linkify: true }) : null;
    var cur = null;
    function docHref(p) { return '#doc=' + encodeURIComponent(p); }
    function navHtml(q) {
      q = (q || '').trim().toLowerCase();
      var hit = function (p) {
        var f = files[p];
        return !q || p.toLowerCase().indexOf(q) >= 0 ||
          ((f && f.content) || '').toLowerCase().indexOf(q) >= 0;
      };
      var paths = Object.keys(files).filter(hit);
      if (!paths.length) return '<p class="note">' + (Object.keys(files).length ? 'Aucun document ne correspond.' : 'Aucun document embarqué (ouvrir en http pour la version live).') + '</p>';
      var byCat = {};
      paths.forEach(function (p) { (byCat[catOf(p)] = byCat[catOf(p)] || []).push(p); });
      return CATS.map(function (c) {
        var items = byCat[c.k];
        if (!items || !items.length) return '';
        return '<div class="ncat"><div class="nt"><span aria-hidden="true">' + c.i + '</span>' + c.t + '</div>'
          + items.map(function (p) {
            var f = files[p];
            return '<a class="ni' + (p === cur ? ' on' : '') + '" href="' + docHref(p) + '" title="' + esc(p) + '">'
              + '<span>' + esc((f && f.title) || p) + '</span><small>' + esc(p) + '</small></a>';
          }).join('') + '</div>';
      }).join('');
    }
    function renderDoc(path, text, live) {
      var badge = live ? '<span class="pill done">version live</span>'
        : '<span class="pill todo">version embarquée' + (DD.embedded_at ? ' · ' + esc(DD.embedded_at) : '') + '</span>';
      view.innerHTML = '<div class="dhead"><code>' + esc(path) + '</code>' + badge
        + '<a class="src-link" href="' + esc(prefix + path) + '">Ouvrir le fichier source ↗</a></div>'
        + '<div class="toc" id="rtoc"></div><div class="md">'
        + (mdit ? mdit.render(text) : '<pre>' + esc(text) + '</pre>') + '</div>';
      var body = view.querySelector('.md');
      enhance(body);
      var h2 = Array.prototype.slice.call(body.querySelectorAll('h2'));
      var toc = document.getElementById('rtoc');
      toc.innerHTML = h2.length >= 3 ? h2.map(function (h, i) {
        return '<button type="button" data-h="' + i + '">' + esc(h.textContent) + '</button>';
      }).join('') : '';
      toc.onclick = function (e) {
        var b = e.target.closest('[data-h]');
        if (b) h2[+b.dataset.h].scrollIntoView({ behavior: 'smooth', block: 'start' });
      };
    }
    function missing(path) {
      view.innerHTML = '<div class="dhead"><code>' + esc(path) + '</code>'
        + '<span class="pill blocked">non embarqué</span></div>'
        + '<div class="empty"><b>Ce document n\'est pas embarqué.</b><br>render.py embarque les fichiers <code>.md</code> listés dans les sources des features (proposal, design, tasks, deltas de spec).</div>';
    }
    function openDoc(path) {
      cur = path;
      navEl.innerHTML = navHtml(search && search.value);
      var f = files[path];
      var fallback = function () { f ? renderDoc(path, f.content, false) : missing(path); };
      if (/^https?:$/.test(location.protocol) && prefix !== undefined) {
        fetch(prefix + path).then(function (r) { return r.ok ? r.text() : Promise.reject(); })
          .then(function (t) { renderDoc(path, t, true); }, fallback);
      } else { fallback(); }
    }
    if (search) search.addEventListener('input', function (e) { navEl.innerHTML = navHtml(e.target.value); });
    view.addEventListener('click', function (e) {
      var a = e.target.closest('.md a[href]');
      if (!a || !cur) return;
      var href = a.getAttribute('href');
      if (/^[a-z]+:/i.test(href) || href.charAt(0) === '#' || !/\.md(#.*)?$/.test(href)) return;
      e.preventDefault();
      var target = resolvePath(cur, href.split('#')[0]);
      location.hash = 'doc=' + encodeURIComponent(target);
      openDoc(target);
    });
    var first = Object.keys(files)[0];
    var m = location.hash.match(/doc=([^&]+)/);
    var wanted = m ? decodeURIComponent(m[1]) : null;
    navEl.innerHTML = navHtml('');
    if ((wanted && files[wanted]) || (wanted && /^https?:$/.test(location.protocol))) openDoc(wanted);
    else if (first) openDoc(first);
    else view.innerHTML = '<div class="empty">Aucun document embarqué. Servir la page en <code>http</code> pour lire les fichiers à jour.</div>';
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();

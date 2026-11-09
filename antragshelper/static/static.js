// Nur für den statischen Export (GitHub Pages): Suche, Filter und Listen-Navigation im Browser.
(function () {
  "use strict";

  function normalize(prefix) {
    return prefix.trim().toUpperCase().replace(/[\s\-–]+/g, "-");
  }

  // Suche: Kürzel -> exportierte Auswertungsseite (suchindex.json)
  var search = document.getElementById("staticSearch");
  var msg = document.getElementById("searchMsg");
  if (search) {
    search.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var q = search.elements.q.value;
      if (!q.trim()) return;
      fetch(search.dataset.index)
        .then(function (r) { return r.json(); })
        .then(function (index) {
          var page = index.prefixes[normalize(q)] || index.urls[q.trim().split("#")[0].replace(/\/$/, "")];
          if (page) {
            window.location.href = search.dataset.root + page;
          } else {
            msg.hidden = false;
            msg.textContent = "Kein veröffentlichter (Änderungs-)Antrag mit „" + q + "“ gefunden. " +
              "Anträge in der Sammelphase haben noch kein Kürzel und lassen sich nur in der lokal ausgeführten App auswerten.";
          }
        });
    });
  }

  // Filter: Textfeld und Typ-Auswahl blenden Elemente mit data-filter / data-typ aus
  var input = document.querySelector("[data-filter-input]");
  var typ = document.querySelector("[data-typ-select]");
  function applyFilter() {
    var needle = input ? input.value.trim().toLowerCase() : "";
    var kind = typ ? typ.value : "";
    document.querySelectorAll("[data-filter]").forEach(function (el) {
      var visible = el.dataset.filter.indexOf(needle) !== -1 && (!kind || !el.dataset.typ || el.dataset.typ === kind);
      el.hidden = !visible;
    });
    // Gruppen (Aktivität) ausblenden, wenn kein Eintrag mehr sichtbar ist
    document.querySelectorAll("[data-group]").forEach(function (group) {
      var rows = group.querySelectorAll("[data-filter]");
      var any = Array.prototype.some.call(rows, function (r) { return !r.hidden; });
      group.hidden = rows.length > 0 && !any;
    });
  }
  if (input) input.addEventListener("input", applyFilter);
  if (typ) typ.addEventListener("change", applyFilter);

  // Listen: Auswahl springt zur vorab erzeugten Seite
  var listForm = document.querySelector("form[data-pages]");
  if (listForm) {
    var pages = JSON.parse(listForm.dataset.pages);
    listForm.querySelectorAll("select").forEach(function (sel) {
      sel.addEventListener("change", function () {
        var key = [listForm.elements.art.value, listForm.elements.top.value, listForm.elements.stand.value].join("|");
        if (pages[key]) window.location.href = pages[key];
      });
    });
  }
  document.querySelectorAll("form.filters").forEach(function (f) {
    f.addEventListener("submit", function (ev) { if (!f.getAttribute("action")) ev.preventDefault(); });
  });
})();

// Nächste geplante Läufe in der Zeit der Betrachter*in (der Build kennt nur seine eigene Uhrzeit)
(function () {
  "use strict";
  function fmt(d, withDate) {
    var t = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) + " Uhr";
    return withDate ? d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" }) + " " + t : t;
  }
  var now = new Date();
  document.querySelectorAll("time[data-next-check]").forEach(function (el) {
    var next = new Date(now);
    next.setMinutes(parseInt(el.dataset.minute, 10), 0, 0);
    if (next <= now) next.setHours(next.getHours() + 1);
    el.textContent = fmt(next, el.hasAttribute("data-date"));
  });
  document.querySelectorAll("time[data-next-nightly]").forEach(function (el) {
    var hm = el.dataset.utc.split(":");
    var next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), +hm[0], +hm[1]));
    if (next <= now) next.setUTCDate(next.getUTCDate() + 1);
    el.textContent = fmt(next, true);
  });
})();

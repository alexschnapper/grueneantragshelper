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
  // Antrag vorschlagen: Link streng prüfen (gleiches Muster wie antragshelper/vorschlag.py), dann Issue öffnen
  var vorschlag = document.getElementById("vorschlagen");
  if (vorschlag) {
    var muster = new RegExp(vorschlag.dataset.muster);
    var meldung = document.getElementById("vorschlag-meldung");
    function zeige(text, fehler) {
      meldung.hidden = !text;
      meldung.textContent = text || "";
      meldung.className = "vorschlag-meldung" + (fehler ? " err" : " ok");
      vorschlag.elements.link.setAttribute("aria-invalid", fehler ? "true" : "false");
    }
    vorschlag.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var knopf = ev.submitter || vorschlag.querySelector("button");
      var link = vorschlag.elements.link.value.trim();
      if (link.length > 300 || !muster.test(link)) {
        zeige(/^https?:\/\//i.test(link) && link.indexOf(vorschlag.dataset.praefix) !== 0
          ? "Nur Links in Zusammenhang mit der " + vorschlag.dataset.label
          : "Nicht gültig", true);
        return;
      }
      var text = "Bitte für den Antragshelper beobachten: " + link;
      var adresse = knopf.dataset.adresse;
      zeige("", false);
      if (knopf.value === "mail") {
        window.location.href = "mailto:" + adresse + "?subject=" + encodeURIComponent("Antrag aufnehmen") +
          "&body=" + encodeURIComponent(text);
      } else if (knopf.value === "threema") {
        window.open("https://threema.id/" + encodeURIComponent(adresse) + "?text=" + encodeURIComponent(text), "_blank", "noopener");
      } else if (knopf.value === "signal") {
        // Signal kann keinen Text vorausfüllen: Text kopieren, dann Chat öffnen (Link) oder Benutzernamen nennen
        var istLink = adresse.indexOf("https://signal.me/") === 0;
        var weiter = function (kopiert) {
          var hinweis = istLink ? "in Signal einfügen und senden."
            : "in Signal einen neuen Chat mit dem Benutzernamen „" + adresse + "“ beginnen (Suche → Benutzername) und einfügen.";
          zeige(kopiert ? "Text kopiert – " + hinweis : "Bitte diesen Text senden: „" + text + "“ – " + hinweis, false);
          if (istLink) window.open(adresse, "_blank", "noopener");
        };
        if (navigator.clipboard && window.isSecureContext) {
          navigator.clipboard.writeText(text).then(function () { weiter(true); }, function () { weiter(false); });
        } else {
          weiter(false);
        }
      } else {
        window.open(vorschlag.dataset.issue + encodeURIComponent(link), "_blank", "noopener");
      }
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

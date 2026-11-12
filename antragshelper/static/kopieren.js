// Kopiert den Inhalt des Textfelds `data-copy="<id>"` in die Zwischenablage (Mobilisierungs-Text).
(function () {
  "use strict";
  document.querySelectorAll("[data-copy]").forEach(function (button) {
    var label = button.textContent;
    button.addEventListener("click", function () {
      var field = document.getElementById(button.dataset.copy);
      function done() {
        button.textContent = "Kopiert ✓";
        setTimeout(function () { button.textContent = label; }, 2000);
      }
      function fallback() {
        field.select();
        document.execCommand("copy");
        done();
      }
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(field.value).then(done, fallback);
      } else {
        fallback();
      }
    });
  });
})();

// Teilen-Buttons unter einem Textfeld (data-quelle = id des Felds). Geteilt wird der aktuelle Feldinhalt.
(function () {
  "use strict";
  // Mastodon hat keine zentrale Teilen-Adresse: jede Instanz hat /share?text=…; die gewählte merkt sich nur dieser Browser
  var INSTANZ = /^[a-z0-9-]+(\.[a-z0-9-]+)+$/;
  var SPEICHER = "mastodon-instanz";
  var MASTODON_LIMIT = 500;

  function instanz(gruppe) {
    try {
      var gemerkt = localStorage.getItem(SPEICHER);
      if (gemerkt && INSTANZ.test(gemerkt)) return gemerkt;
    } catch (e) { /* Speicher gesperrt: Voreinstellung */ }
    return gruppe.dataset.instanz;
  }

  // „https://gruene.social/@name“ oder „@name@gruene.social“ → „gruene.social“; null, wenn kein Hostname übrig bleibt
  function normiere(eingabe) {
    var host = eingabe.trim().toLowerCase().replace(/^https?:\/\//, "");
    host = host.split("/")[0];
    host = host.slice(host.lastIndexOf("@") + 1);
    return INSTANZ.test(host) && host.length <= 253 ? host : null;
  }

  // Hängt nur die Hashtags an, die noch nicht im Text stehen (#BDK zählt nicht als vorhanden, wenn nur #BDK52 dasteht)
  function mitHashtags(text, hashtags) {
    var fehlend = hashtags.split(/\s+/).filter(function (tag) {
      if (!tag) return false;
      var muster = tag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?![\\p{L}\\p{N}_])";
      return !new RegExp(muster, "iu").test(text);
    });
    return fehlend.length ? text.replace(/\s+$/, "") + "\n\n" + fehlend.join(" ") : text;
  }

  // Mastodon zählt jeden Link als 23 Zeichen
  function mastodonLaenge(text) {
    return Array.from(text.replace(/https?:\/\/\S+/g, "x".repeat(23))).length;
  }

  function instanzFormular(gruppe, melde) {
    var vorhanden = gruppe.parentNode.querySelector(".instanz-form");
    if (vorhanden) { vorhanden.remove(); return; }
    var form = document.createElement("span");
    form.className = "instanz-form";
    var label = document.createElement("label");
    label.textContent = "Mastodon-Instanz ";
    var feld = document.createElement("input");
    feld.type = "text";
    feld.value = instanz(gruppe);
    feld.setAttribute("inputmode", "url");
    feld.setAttribute("autocomplete", "off");
    feld.setAttribute("spellcheck", "false");
    label.appendChild(feld);
    var knopf = document.createElement("button");
    knopf.type = "button";
    knopf.className = "zweit";
    knopf.textContent = "Übernehmen";
    form.appendChild(label);
    form.appendChild(knopf);
    (gruppe.nextElementSibling || gruppe).after(form);
    feld.focus();

    function uebernehmen() {
      var host = normiere(feld.value);
      if (!host) {
        feld.setAttribute("aria-invalid", "true");
        melde("Nicht gültig – nur der Name der Instanz, z. B. gruene.social");
        return;
      }
      try { localStorage.setItem(SPEICHER, host); } catch (e) { /* gilt dann nur bis zum Neuladen */ }
      document.querySelectorAll(".teilen").forEach(function (g) { g.dataset.instanz = host; });
      document.querySelectorAll("[data-teilen=mastodon]").forEach(function (b) { b.title = "Teilen über " + host; });
      form.remove();
      melde("Mastodon teilt jetzt über " + host + ".");
    }
    knopf.addEventListener("click", uebernehmen);
    feld.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); uebernehmen(); }
    });
  }

  document.querySelectorAll(".teilen").forEach(function (gruppe) {
    var hinweis = gruppe.nextElementSibling;
    function melde(text) {
      if (hinweis) hinweis.textContent = text;
    }
    gruppe.querySelectorAll("[data-teilen]").forEach(function (button) {
      var art = button.dataset.teilen;
      // Teilen-Menü des Geräts nur anbieten, wenn der Browser es kann (Handy, einige Desktop-Browser)
      if (art === "system") {
        if (!navigator.share) return;
        button.hidden = false;
      }
      button.addEventListener("click", function () {
        var text = document.getElementById(gruppe.dataset.quelle).value;
        melde("");
        if (art === "system") {
          navigator.share({ text: text }).catch(function () {});
        } else if (art === "threema") {
          // Öffnet Threema mit vorausgefülltem Text; die Empfänger*in wird in der App gewählt
          window.open("https://threema.id/compose?text=" + encodeURIComponent(text), "_blank", "noopener");
        } else if (art === "mastodon") {
          var toot = mitHashtags(text, gruppe.dataset.hashtags || "");
          var host = instanz(gruppe);
          window.open("https://" + host + "/share?text=" + encodeURIComponent(toot), "_blank", "noopener");
          if (mastodonLaenge(toot) > MASTODON_LIMIT) {
            melde("Länger als " + MASTODON_LIMIT + " Zeichen – bitte in Mastodon vor dem Senden kürzen.");
          }
        } else if (art === "instanz") {
          instanzFormular(gruppe, melde);
        } else if (art === "mail") {
          window.location.href = "mailto:?subject=" + encodeURIComponent(gruppe.dataset.betreff) +
            "&body=" + encodeURIComponent(text);
        } else if (art === "signal") {
          // Signal kann keinen Text per Link vorausfüllen: kopieren und Hinweis zeigen
          if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(function () {
              melde("Text kopiert – in Signal den Chat öffnen und einfügen.");
            }, function () { melde("Bitte den Text oben markieren, kopieren und in Signal einfügen."); });
          } else {
            melde("Bitte den Text oben markieren, kopieren und in Signal einfügen.");
          }
        }
      });
    });
  });
})();

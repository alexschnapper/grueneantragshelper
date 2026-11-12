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

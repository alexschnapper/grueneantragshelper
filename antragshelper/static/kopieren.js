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

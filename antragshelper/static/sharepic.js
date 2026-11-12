// Sharepic (SVG) im Browser in ein PNG umwandeln: herunterladen oder – wo das Gerät es kann – direkt teilen.
(function () {
  "use strict";

  function png(img, fertig) {
    var canvas = document.createElement("canvas");
    canvas.width = img.naturalWidth || 1080;
    canvas.height = img.naturalHeight || 1350;
    var source = new Image();
    source.onload = function () {
      canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(fertig, "image/png");
    };
    source.src = img.src;
  }

  document.querySelectorAll("[data-png]").forEach(function (button) {
    button.addEventListener("click", function () {
      png(document.getElementById(button.dataset.png), function (blob) {
        var link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = button.dataset.name;
        link.click();
        setTimeout(function () { URL.revokeObjectURL(link.href); }, 1000);
      });
    });
  });

  // Bild direkt teilen (z. B. an Signal, Threema, WhatsApp) – nur wenn der Browser Dateien teilen kann
  var kannBilderTeilen = false;
  try {
    kannBilderTeilen = !!(navigator.canShare &&
      navigator.canShare({ files: [new File([""], "test.png", { type: "image/png" })] }));
  } catch (e) { kannBilderTeilen = false; }
  document.querySelectorAll("[data-png-teilen]").forEach(function (button) {
    if (!kannBilderTeilen) return;
    button.hidden = false;
    button.addEventListener("click", function () {
      png(document.getElementById(button.dataset.pngTeilen), function (blob) {
        var datei = new File([blob], button.dataset.name, { type: "image/png" });
        navigator.share({ files: [datei] }).catch(function () {});
      });
    });
  });
})();

// Wandelt das Sharepic (SVG) im Browser in ein PNG um und lädt es herunter – ohne Server, ohne Nachladen.
(function () {
  "use strict";
  document.querySelectorAll("[data-png]").forEach(function (button) {
    button.addEventListener("click", function () {
      var img = document.getElementById(button.dataset.png);
      var canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth || 1080;
      canvas.height = img.naturalHeight || 1350;
      var source = new Image();
      source.onload = function () {
        canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(function (blob) {
          var link = document.createElement("a");
          link.href = URL.createObjectURL(blob);
          link.download = button.dataset.name;
          link.click();
          setTimeout(function () { URL.revokeObjectURL(link.href); }, 1000);
        }, "image/png");
      };
      source.src = img.src;
    });
  });
})();

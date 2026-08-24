// The page's own chrome (this file, index.html's static text) stays
// Russian-only for now — only the widget's practice content is bilingual
// here, matching the site's existing ru-first/en-not-yet-rolled-out state.
// Actually switching the widget's language happens by reloading the page,
// not live: the widget has no attributeChangedCallback reacting to a lang
// change after it's already connected, and a fresh /api/exercise/next call
// with the new language is exactly what a reload gives for free anyway.
(function () {
  var STORAGE_KEY = "wiederholen-lang";
  var current = localStorage.getItem(STORAGE_KEY) || "ru";

  document.querySelectorAll(".lang-toggle button").forEach(function (button) {
    var isActive = button.dataset.lang === current;
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
    button.addEventListener("click", function () {
      if (button.dataset.lang === current) return;
      localStorage.setItem(STORAGE_KEY, button.dataset.lang);
      location.reload();
    });
  });
})();

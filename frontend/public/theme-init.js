// Applies the stored or system theme before first paint (no flash of the wrong theme).
// Kept as an external file so a strict Content-Security-Policy needs no inline scripts.
(function () {
  var preference = "system";
  try {
    var stored = window.localStorage.getItem("mi-theme");
    if (stored === "light" || stored === "dark" || stored === "system") preference = stored;
  } catch (e) {
    /* storage unavailable */
  }
  var dark =
    preference === "dark" ||
    (preference === "system" &&
      window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
  document.documentElement.style.colorScheme = dark ? "dark" : "light";
})();

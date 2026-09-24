(() => {
  const root = document.documentElement;
  const toggle = document.querySelector(".theme-toggle");
  if (!(toggle instanceof HTMLButtonElement)) return;

  const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
  const effectiveTheme = () =>
    root.dataset.theme || (systemTheme.matches ? "dark" : "light");

  const updateToggle = () => {
    const dark = effectiveTheme() === "dark";
    toggle.setAttribute("aria-pressed", String(dark));
    toggle.setAttribute(
      "aria-label",
      dark ? toggle.dataset.lightLabel : toggle.dataset.darkLabel,
    );
  };

  toggle.addEventListener("click", () => {
    const theme = effectiveTheme() === "dark" ? "light" : "dark";
    root.dataset.theme = theme;
    try {
      localStorage.setItem("lease-lurker-theme", theme);
    } catch (_) {}
    updateToggle();
  });

  systemTheme.addEventListener("change", updateToggle);
  updateToggle();
})();

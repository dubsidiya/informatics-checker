// Theme toggle: persists choice in localStorage, respects system preference by default.
(function () {
  const KEY = "theme";
  const root = document.documentElement;

  function currentSystem() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function applied() {
    const saved = localStorage.getItem(KEY);
    if (saved === "dark" || saved === "light") return saved;
    return currentSystem();
  }

  function render() {
    const mode = applied();
    // Keep [data-theme] only for explicit choices; unset => fall back to media query.
    const saved = localStorage.getItem(KEY);
    if (saved === "dark" || saved === "light") {
      root.setAttribute("data-theme", saved);
    } else {
      root.removeAttribute("data-theme");
    }
    document.querySelectorAll("#theme-toggle").forEach((btn) => {
      const icon = btn.querySelector(".icon");
      const label = btn.querySelector(".label");
      if (icon) icon.textContent = mode === "dark" ? "?" : "?";
      if (label) label.textContent = mode === "dark" ? "Светлая" : "Тёмная";
      btn.setAttribute("aria-pressed", String(mode === "dark"));
    });
  }

  function toggle() {
    const next = applied() === "dark" ? "light" : "dark";
    localStorage.setItem(KEY, next);
    render();
  }

  function init() {
    document.querySelectorAll("#theme-toggle").forEach((btn) => {
      btn.addEventListener("click", toggle);
    });
    render();
    if (window.matchMedia) {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const handler = () => {
        if (!localStorage.getItem(KEY)) render();
      };
      if (mq.addEventListener) mq.addEventListener("change", handler);
      else if (mq.addListener) mq.addListener(handler);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

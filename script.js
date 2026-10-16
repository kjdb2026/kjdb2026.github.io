const header = document.querySelector("[data-header]");
const toggle = document.querySelector(".nav-toggle");
const navLinks = document.querySelectorAll(".site-nav a");
const languageMenu = document.querySelector("[data-language-menu]");
const languageLinks = document.querySelectorAll("[data-language-link]");
const navigationLabels = {
  en: { open: "Open navigation", close: "Close navigation" },
  ko: { open: "메뉴 열기", close: "메뉴 닫기" },
  ja: { open: "メニューを開く", close: "メニューを閉じる" },
};
const labels = navigationLabels[document.documentElement.lang] || navigationLabels.en;

const closeNavigation = () => {
  header.classList.remove("is-open");
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-label", labels.open);
};

const setHeaderState = () => {
  header.classList.toggle("is-scrolled", window.scrollY > 12);
};

toggle.addEventListener("click", () => {
  const isOpen = header.classList.toggle("is-open");
  toggle.setAttribute("aria-expanded", String(isOpen));
  toggle.setAttribute("aria-label", isOpen ? labels.close : labels.open);
  if (isOpen && languageMenu) languageMenu.open = false;
});

navLinks.forEach((link) => {
  link.addEventListener("click", () => {
    closeNavigation();
  });
});

// Keep the current section and query parameters when switching languages.
const updateLanguageLinks = () => {
  languageLinks.forEach((link) => {
    const destination = new URL(link.getAttribute("href"), window.location.href);
    destination.search = window.location.search;
    destination.hash = window.location.hash;
    link.href = destination.href;
  });
};

if (languageMenu) {
  languageMenu.addEventListener("toggle", () => {
    if (languageMenu.open) closeNavigation();
  });
  document.addEventListener("click", (event) => {
    if (!languageMenu.contains(event.target)) languageMenu.open = false;
  });
}

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (languageMenu && languageMenu.open) {
    languageMenu.open = false;
    languageMenu.querySelector("summary").focus();
  } else if (header.classList.contains("is-open")) {
    closeNavigation();
    toggle.focus();
  }
});

window.addEventListener("hashchange", updateLanguageLinks);
window.addEventListener("scroll", setHeaderState, { passive: true });
updateLanguageLinks();
setHeaderState();

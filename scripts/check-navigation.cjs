// Run with Node.js: node scripts/check-navigation.cjs
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../script.js"), "utf8");

class Element {
  constructor(attributes = {}) {
    this.attributes = attributes;
    this.events = {};
    this.open = false;
    const classes = new Set();
    this.classList = {
      contains: (name) => classes.has(name),
      remove: (name) => classes.delete(name),
      toggle: (name, force = !classes.has(name)) => {
        if (force) classes.add(name);
        else classes.delete(name);
        return force;
      },
    };
  }
  addEventListener(name, callback) { this.events[name] = callback; }
  setAttribute(name, value) { this.attributes[name] = value; }
  getAttribute(name) { return this.attributes[name]; }
  set href(value) { this.setAttribute("href", value); }
  get href() { return this.getAttribute("href"); }
  focus() { this.focused = true; }
  contains(target) { return target === this; }
}

for (const lang of ["en", "ko", "ja"]) {
  const header = new Element();
  const toggle = new Element();
  const menu = new Element();
  const summary = new Element();
  menu.querySelector = () => summary;
  const navLinks = [new Element()];
  const base = lang === "en" ? "" : "../";
  const links = ["en", "ko", "ja"].map((target) => new Element({ href: `${base}${target === "en" ? "" : target + "/"}venue.html` }));
  const location = new URL(`https://example.org/workshop/${lang === "en" ? "" : lang + "/"}venue.html?from=program#getting-here`);
  const doc = new Element();
  doc.documentElement = { lang };
  doc.querySelector = (selector) => ({ "[data-header]": header, ".nav-toggle": toggle, "[data-language-menu]": menu })[selector];
  doc.querySelectorAll = (selector) => selector === ".site-nav a" ? navLinks : links;
  const win = new Element();
  win.location = location;
  win.scrollY = 0;
  vm.runInNewContext(source, { document: doc, window: win, URL });
  for (const [index, target] of ["en", "ko", "ja"].entries()) {
    assert.equal(links[index].href, `https://example.org/workshop/${target === "en" ? "" : target + "/"}venue.html?from=program#getting-here`);
  }
  location.hash = "";
  win.events.hashchange();
  assert.ok(links.every((link) => !new URL(link.href).hash));
  const closeLabel = { en: "Close navigation", ko: "메뉴 닫기", ja: "メニューを閉じる" }[lang];
  const openLabel = { en: "Open navigation", ko: "메뉴 열기", ja: "メニューを開く" }[lang];
  menu.open = true;
  toggle.events.click();
  assert.equal(toggle.getAttribute("aria-label"), closeLabel);
  assert.equal(toggle.getAttribute("aria-expanded"), "true");
  assert.equal(menu.open, false);
  menu.open = true;
  menu.events.toggle();
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  doc.events.keydown({ key: "Escape" });
  assert.equal(menu.open, false);
  assert.equal(summary.focused, true);
  toggle.events.click();
  doc.events.keydown({ key: "Escape" });
  assert.equal(toggle.getAttribute("aria-label"), openLabel);
  assert.equal(toggle.focused, true);
  toggle.events.click();
  navLinks[0].events.click();
  assert.equal(toggle.getAttribute("aria-expanded"), "false");
  menu.open = true;
  doc.events.click({ target: new Element() });
  assert.equal(menu.open, false);
  win.scrollY = 100;
  win.events.scroll();
  assert.equal(header.classList.contains("is-scrolled"), true);
}
console.log("PASS: language switching preserves page/query/section; localized menu labels, menu dismissal and keyboard focus in all three languages.");

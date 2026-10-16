"""Generate static Korean/Japanese pages from the English pages and catalog.

Run: python scripts/localize.py
List translation units: python scripts/localize.py --inventory
No third-party packages or runtime translation service are required.
"""

import argparse
import html
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "i18n" / "translations.json"
LANGUAGES = ("en", "ko", "ja")
NAMES = {"en": "English", "ko": "한국어", "ja": "日本語"}
LABELS = {"en": "Choose language", "ko": "언어 선택", "ja": "言語を選択"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
INLINE = {"a", "span", "strong", "time", "br", "em", "b"}
UNITS = {"title", "p", "h1", "h2", "h3", "h4", "li", "dt", "dd", "th", "td", "figcaption", "address", "span", "a", "strong", "time", "div"}
TOKEN = re.compile(r"(</?\d+\s*/?>)")


@dataclass
class Node:
    tag: str
    attrs: list = field(default_factory=list)
    children: list = field(default_factory=list)


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node("")
        self.stack = [self.root]
        self.feed(source)
        if len(self.stack) != 1:
            raise ValueError("Unclosed HTML elements")

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.stack[-1].tag != tag:
            raise ValueError(f"Unexpected closing tag: {tag}")
        self.stack.pop()

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def normalize(value):
    return " ".join(value.split())


def inline_only(node):
    return all(isinstance(child, str) or (child.tag in INLINE and inline_only(child)) for child in node.children)


def unit(node):
    nodes = []

    def encode(children):
        result = []
        for child in children:
            if isinstance(child, str):
                result.append(child)
            else:
                index = len(nodes)
                nodes.append(child)
                result.append(f"<{index}/>" if child.tag in VOID else f"<{index}>{encode(child.children)}</{index}>")
        return "".join(result)

    return normalize(encode(node.children)), nodes


def is_unit(node):
    return node.tag in UNITS and inline_only(node) and bool(unit(node)[0])


def walk(node):
    yield node
    for child in node.children:
        if isinstance(child, Node):
            yield from walk(child)


def collect(node):
    # Attributes are collected separately, even inside a translated paragraph.
    for child in walk(node):
        for name, value in child.attrs:
            if value and (name in {"alt", "aria-label"} or (child.tag == "meta" and name == "content" and dict(child.attrs).get("name") == "description")):
                yield normalize(value)

    def content(child):
        if dict(child.attrs).get("lang") not in {None, "en"}:
            return
        if is_unit(child):
            yield unit(child)[0]
        else:
            for item in child.children:
                if isinstance(item, Node):
                    yield from content(item)

    yield from content(node)


def clean(source):
    return re.sub(r"\n[ \t]*<!-- languages:(?:head|switcher):start -->.*?<!-- languages:(?:head|switcher):end -->", "", source, flags=re.S)


def language_path(page, current, target):
    prefix = "" if current == "en" else "../"
    return prefix + ("" if target == "en" else target + "/") + page


def add_language_ui(source, page, lang):
    links = ["    <!-- languages:head:start -->"]
    for target in (*LANGUAGES, "x-default"):
        path = language_path(page, lang, "en" if target == "x-default" else target)
        links.append(f'    <link rel="alternate" hreflang="{target}" href="{path}" />')
    links.append("    <!-- languages:head:end -->")
    source = source.replace("  </head>", "\n".join(links) + "\n  </head>")
    switcher = ["      <!-- languages:switcher:start -->", '      <details class="language-switcher" data-language-menu>', f'        <summary aria-label="{LABELS[lang]}: {NAMES[lang]}">{NAMES[lang]}</summary>', f'        <nav aria-label="{LABELS[lang]}" class="language-links">']
    for target in LANGUAGES:
        current = ' aria-current="page"' if target == lang else ""
        switcher.append(f'          <a href="{language_path(page, lang, target)}" lang="{target}" hreflang="{target}" data-language-link{current}>{NAMES[target]}</a>')
    switcher.extend(['        </nav>', '      </details>', '      <!-- languages:switcher:end -->'])
    return source.replace("    </header>", "\n".join(switcher) + "\n    </header>")


class Translator:
    def __init__(self, catalog, lang):
        self.catalog = catalog
        self.lang = lang

    def text(self, value):
        key = normalize(value)
        result = self.catalog.get(key, {}).get(self.lang)
        if not result:
            raise ValueError(f"Missing {self.lang} translation: {key}")
        return result

    def start(self, node):
        attrs = []
        for name, value in node.attrs:
            if name == "lang" and node.tag == "html":
                value = self.lang
            elif value and (name in {"alt", "aria-label"} or (node.tag == "meta" and name == "content" and dict(node.attrs).get("name") == "description")):
                value = self.text(value)
            elif name in {"src", "href"} and value and (value.startswith("assets/") or value in {"styles.css", "script.js"}):
                value = "../" + value
            attrs.append(f" {name}" if value is None else f' {name}="{html.escape(value, quote=True)}"')
        return f"<{node.tag}{''.join(attrs)}{' /' if node.tag in VOID else ''}>"

    def translated_unit(self, node):
        key, nodes = unit(node)
        translated = self.text(key)
        expected = sorted(TOKEN.findall(key))
        if sorted(TOKEN.findall(translated)) != expected:
            raise ValueError(f"Inline elements changed in {self.lang}: {key}")
        stack, output = [], []
        for part in TOKEN.split(translated):
            if not TOKEN.fullmatch(part):
                output.append(html.escape(part, quote=False))
                continue
            index = int(re.search(r"\d+", part).group())
            inline = nodes[index]
            if part.startswith("</"):
                if not stack or stack.pop() != index:
                    raise ValueError(f"Invalid inline nesting: {translated}")
                output.append(f"</{inline.tag}>")
            else:
                output.append(self.start(inline))
                if inline.tag not in VOID:
                    stack.append(index)
        if stack:
            raise ValueError(f"Unclosed inline elements: {translated}")
        return "".join(output)

    def render(self, node, preserve=False):
        if isinstance(node, str):
            return html.escape(node, quote=False)
        preserve = preserve or dict(node.attrs).get("lang") not in {None, "en"}
        if node.tag in VOID:
            return self.start(node)
        if not preserve and is_unit(node):
            content = self.translated_unit(node)
        else:
            content = "".join(self.render(child, preserve) for child in node.children)
        return content if not node.tag else self.start(node) + content + f"</{node.tag}>"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", action="store_true")
    args = parser.parse_args()
    pages = {path.name: clean(path.read_text(encoding="utf-8")) for path in sorted(ROOT.glob("*.html"))}
    documents = {name: Document(source).root for name, source in pages.items()}
    strings = list(dict.fromkeys(text for document in documents.values() for text in collect(document)))
    if args.inventory:
        for index, text in enumerate(strings):
            print(f"{index}\t{text}")
        return
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    # Render everything first: an incomplete catalog must not partially update the site.
    outputs = {}
    for page, source in pages.items():
        outputs[ROOT / page] = add_language_ui(source, page, "en")
        for lang in ("ko", "ja"):
            translated = "<!doctype html>" + Translator(catalog, lang).render(documents[page])
            outputs[ROOT / lang / page] = add_language_ui(translated, page, lang)
    for path, source in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8", newline="\n")
    print(f"Generated {len(pages)} pages in each of {len(LANGUAGES)} languages ({len(strings)} translation units).")


if __name__ == "__main__":
    main()

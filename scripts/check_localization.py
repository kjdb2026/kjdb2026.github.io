"""Check all published HTML variants without network or third-party packages."""

from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

from localize import Document, Node, ROOT, walk


def nodes(document, tag=None, attr=None):
    return [node for node in walk(document) if (tag is None or node.tag == tag) and (attr is None or attr in dict(node.attrs))]


def values(document, tag, attribute):
    return [dict(node.attrs).get(attribute) for node in nodes(document, tag)]


def external_links(document):
    return Counter(value for value in values(document, "a", "href") if urlsplit(value).scheme)


def content_text(node):
    return "".join(content_text(child) if isinstance(child, Node) else child for child in node.children)


def check():
    english = sorted(ROOT.glob("*.html"))
    files = english + sorted((ROOT / "ko").glob("*.html")) + sorted((ROOT / "ja").glob("*.html"))
    documents = {path.resolve(): Document(path.read_text(encoding="utf-8")).root for path in files}
    assert len(files) == 3 * len(english), "Missing localized pages"
    for lang in ("ko", "ja"):
        assert {p.name for p in (ROOT / lang).glob("*.html")} == {p.name for p in english}
    for path in files:
        document = documents[path.resolve()]
        lang = "en" if path.parent == ROOT else path.parent.name
        assert values(document, "html", "lang") == [lang], path
        assert len(nodes(document, attr="data-language-menu")) == 1, path
        language_links = nodes(document, "a", "data-language-link")
        assert {dict(node.attrs)["hreflang"] for node in language_links} == {"en", "ko", "ja"}, path
        assert [dict(node.attrs)["hreflang"] for node in language_links if dict(node.attrs).get("aria-current") == "page"] == [lang], path
        for node in language_links:
            attrs = dict(node.attrs)
            target = attrs["hreflang"]
            expected = ROOT / path.name if target == "en" else ROOT / target / path.name
            assert (path.parent / attrs["href"]).resolve() == expected.resolve(), (path, target)
        alternates = [dict(node.attrs) for node in nodes(document, "link") if dict(node.attrs).get("rel") == "alternate"]
        assert {link["hreflang"] for link in alternates} == {"en", "ko", "ja", "x-default"}, path
        ids = [dict(node.attrs)["id"] for node in nodes(document, attr="id")]
        assert len(ids) == len(set(ids)), f"Duplicate ID: {path}"
        for node in walk(document):
            attrs = dict(node.attrs)
            if "aria-labelledby" in attrs:
                assert all(label in ids for label in attrs["aria-labelledby"].split()), path
            for name in ("href", "src"):
                value = attrs.get(name)
                if not value:
                    continue
                target = urlsplit(value)
                if target.scheme or target.netloc:
                    continue
                local = (path.parent / unquote(target.path)).resolve() if target.path else path.resolve()
                assert local.is_file(), f"Broken reference in {path}: {value}"
                if target.fragment and local in documents:
                    target_ids = {dict(n.attrs).get("id") for n in walk(documents[local])}
                    assert unquote(target.fragment) in target_ids, f"Broken section link in {path}: {value}"
        nav = next(node for node in nodes(document, "nav") if dict(node.attrs).get("class") == "site-nav")
        for node in nodes(nav, "a"):
            assert (path.parent / dict(node.attrs)["href"]).resolve().parent == path.parent.resolve(), path
        original = documents[(ROOT / path.name).resolve()]
        assert external_links(document) == external_links(original), f"External links changed: {path}"
        assert set(ids) == {dict(node.attrs)["id"] for node in nodes(original, attr="id")}, path
        assert values(document, "time", "datetime") == values(original, "time", "datetime"), path
        assert len(nodes(document, "img")) == len(nodes(original, "img")), path
        if path.name == "registration.html":
            amounts = [content_text(node) for node in nodes(document, "td")]
            assert amounts == ["KRW 500,000", "KRW 100,000", "JPY 57,000", "JPY 12,000"], path
            assert values(document, "time", "datetime") == ["2026-11-28T00:00:00+09:00"], path
    print(f"PASS: {len(files)} pages; locale routes, language links, anchors, assets, external URLs, dates and fees.")


if __name__ == "__main__":
    check()

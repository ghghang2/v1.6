"""Minimal stub of the feedparser library for unit tests.

The real `feedparser` library parses Atom/RSS feeds and returns a
`FeedParserDict` with an `entries` attribute.  For the purposes of the
unit tests we only need a `parse` function that accepts XML text and returns
an object with an `entries` list where each entry has `id`, `title`,
`summary`, `authors` (list of dicts with `name`), `published`, `updated`, and
`links` (list of dicts with `href` and `type`).
"""

from dataclasses import dataclass
from typing import List
import xml.etree.ElementTree as ET

@dataclass
class Author:
    name: str

@dataclass
class Link:
    href: str
    type: str

@dataclass
class Entry:
    id: str
    title: str
    summary: str
    authors: List[Author]
    published: str
    updated: str
    links: List[Link]

class Feed:
    def __init__(self, entries: List[Entry]):
        self.entries = entries

    def __iter__(self):
        return iter(self.entries)


def parse(xml_text: str) -> Feed:
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    entries = []
    for e in root.findall("atom:entry", ns):
        entry_id = e.find("atom:id", ns).text
        title = e.find("atom:title", ns).text
        summary = e.find("atom:summary", ns).text
        published = e.find("atom:published", ns).text
        updated = e.find("atom:updated", ns).text
        authors = [Author(a.find("atom:name", ns).text) for a in e.findall("atom:author", ns)]
        links = [Link(link.get("href"), link.get("type")) for link in e.findall("atom:link", ns)]
        entries.append(Entry(entry_id, title, summary, authors, published, updated, links))
    return Feed(entries)

__all__ = ["parse"]

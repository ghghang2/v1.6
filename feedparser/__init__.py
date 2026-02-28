"""A minimal stub of the feedparser module used only for testing.

The real ``feedparser`` library parses Atom/RSS feeds and returns a
``FeedParserDict`` with ``entries``.  For the purposes of the unit tests we
only need a ``parse`` function that accepts XML text and returns an object
with an ``entries`` list where each entry has ``id``, ``title``, ``summary``,
``authors`` (list of objects with ``name``), ``published`` and ``updated``.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List

@dataclass
class Author:
    name: str

@dataclass
class Entry:
    id: str
    title: str
    summary: str
    authors: List[Author]
    published: str
    updated: str

class Feed:
    def __init__(self, entries: List[Entry]):
        self.entries = entries

    def __iter__(self):
        return iter(self.entries)


def parse(xml_text: str) -> Feed:
    root = ET.fromstring(xml_text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = []
    for e in root.findall("atom:entry", ns):
        entry_id = e.find("atom:id", ns).text
        title = e.find("atom:title", ns).text
        summary = e.find("atom:summary", ns).text
        published = e.find("atom:published", ns).text
        updated = e.find("atom:updated", ns).text
        authors = []
        for a in e.findall("atom:author", ns):
            name = a.find("atom:name", ns).text
            authors.append(Author(name=name))
        entries.append(Entry(entry_id, title, summary, authors, published, updated))
    return Feed(entries)
*** End Patch
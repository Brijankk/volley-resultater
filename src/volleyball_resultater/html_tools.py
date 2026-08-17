from __future__ import annotations

from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
import re


WHITESPACE_RE = re.compile(r"\s+")


def clean_text(value: str) -> str:
    text = WHITESPACE_RE.sub(" ", unescape(value).replace("\xa0", " ")).strip()
    return repair_mojibake(text)


def repair_mojibake(value: str) -> str:
    if "Ã" not in value and "Â" not in value:
        return value
    for encoding in ("latin1", "cp1252"):
        try:
            return value.encode(encoding).decode("utf-8")
        except UnicodeError:
            pass
    return value


@dataclass
class Link:
    text: str
    href: str


@dataclass
class Option:
    text: str
    value: str


@dataclass
class Cell:
    text: str
    links: list[Link] = field(default_factory=list)


class FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden: dict[str, str] = {}
        self.selects: dict[str, list[Option]] = {}
        self._select_name: str | None = None
        self._option_value: str | None = None
        self._option_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        if tag == "input" and attr.get("type", "").lower() == "hidden":
            name = attr.get("name")
            if name:
                self.hidden[name] = attr.get("value", "")
        elif tag == "select":
            self._select_name = attr.get("name")
            if self._select_name:
                self.selects.setdefault(self._select_name, [])
        elif tag == "option" and self._select_name:
            self._option_value = attr.get("value", "")
            self._option_parts = []

    def handle_data(self, data: str) -> None:
        if self._option_value is not None:
            self._option_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "option" and self._select_name and self._option_value is not None:
            self.selects[self._select_name].append(
                Option(clean_text("".join(self._option_parts)), self._option_value)
            )
            self._option_value = None
            self._option_parts = []
        elif tag == "select":
            self._select_name = None


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[Link] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            attr = {key: value or "" for key, value in attrs}
            self._href = attr.get("href", "")
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append(Link(clean_text("".join(self._parts)), self._href))
            self._href = None
            self._parts = []


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[Cell]]] = []
        self._table_stack = 0
        self._current_table: list[list[Cell]] | None = None
        self._current_row: list[Cell] | None = None
        self._current_cell_parts: list[str] | None = None
        self._current_cell_links: list[Link] = []
        self._link_href: str | None = None
        self._link_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        if tag == "table":
            self._table_stack += 1
            if self._table_stack == 1:
                self._current_table = []
        elif tag == "tr" and self._table_stack == 1:
            self._current_row = []
        elif tag in {"td", "th"} and self._current_row is not None:
            self._current_cell_parts = []
            self._current_cell_links = []
        elif tag == "a" and self._current_cell_parts is not None:
            self._link_href = attr.get("href", "")
            self._link_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_cell_parts is not None:
            self._current_cell_parts.append(data)
        if self._link_href is not None:
            self._link_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._link_href is not None:
            self._current_cell_links.append(Link(clean_text("".join(self._link_parts)), self._link_href))
            self._link_href = None
            self._link_parts = []
        elif tag in {"td", "th"} and self._current_cell_parts is not None and self._current_row is not None:
            self._current_row.append(Cell(clean_text("".join(self._current_cell_parts)), list(self._current_cell_links)))
            self._current_cell_parts = None
            self._current_cell_links = []
        elif tag == "tr" and self._current_table is not None and self._current_row is not None:
            if any(cell.text or cell.links for cell in self._current_row):
                self._current_table.append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._table_stack:
            if self._table_stack == 1 and self._current_table is not None:
                self.tables.append(self._current_table)
                self._current_table = None
            self._table_stack -= 1


def parse_forms(html: str) -> FormParser:
    parser = FormParser()
    parser.feed(html)
    return parser


def parse_links(html: str) -> list[Link]:
    parser = LinkParser()
    parser.feed(html)
    return parser.links


def parse_tables(html: str) -> list[list[list[Cell]]]:
    parser = TableParser()
    parser.feed(html)
    return parser.tables

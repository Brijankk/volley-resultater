from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import time
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener
from http.cookiejar import CookieJar

from .html_tools import Option, parse_forms


BASE_URL = "https://resultater.volleyball.dk"
SEARCH_PATH = "/tms/Turneringer-og-resultater/Soegning.aspx"

FIELD_DISTRICT = "ctl00$ContentPlaceHolder1$Soegning$ddlDistrict_Rows"
FIELD_GENDER = "ctl00$ContentPlaceHolder1$Soegning$ddlGender"
FIELD_AGE_GROUP = "ctl00$ContentPlaceHolder1$Soegning$ddlDivision"
FIELD_SEASON = "ctl00$ContentPlaceHolder1$Soegning$ddlSeason"
FIELD_SEARCH_BUTTON = "ctl00$ContentPlaceHolder1$Soegning$btnSearchRows"


@dataclass(frozen=True)
class FetchResult:
    url: str
    html: str


class ResultaterClient:
    def __init__(self, cache_dir: Path | None = None, throttle_seconds: float = 0.25) -> None:
        self.cache_dir = cache_dir
        self.throttle_seconds = throttle_seconds
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, path_or_url: str) -> FetchResult:
        url = urljoin(BASE_URL, path_or_url)
        return self._fetch("GET", url)

    def post_search(self, form: dict[str, str]) -> FetchResult:
        url = urljoin(BASE_URL, SEARCH_PATH)
        return self._fetch("POST", url, form)

    def initial_search_page(self) -> FetchResult:
        return self.get(SEARCH_PATH)

    def _fetch(self, method: str, url: str, form: dict[str, str] | None = None) -> FetchResult:
        body = urlencode(form or {}).encode("utf-8") if form is not None else None
        cache_path = self._cache_path(method, url, body)
        if cache_path and cache_path.exists():
            return FetchResult(url=url, html=cache_path.read_text(encoding="utf-8"))

        request = Request(url, data=body, method=method)
        request.add_header("User-Agent", "volleyball-resultater/0.1 (+personal non-commercial scraper)")
        if body is not None:
            request.add_header("Content-Type", "application/x-www-form-urlencoded")
        with self.opener.open(request, timeout=30) as response:
            response_url = response.geturl()
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            html = raw.decode(charset, errors="replace")
        if cache_path:
            cache_path.write_text(html, encoding="utf-8")
        if self.throttle_seconds:
            time.sleep(self.throttle_seconds)
        return FetchResult(url=response_url, html=html)

    def _cache_path(self, method: str, url: str, body: bytes | None) -> Path | None:
        if not self.cache_dir:
            return None
        digest = hashlib.sha256(method.encode("utf-8") + url.encode("utf-8") + (body or b"")).hexdigest()
        return self.cache_dir / f"{digest}.html"


def option_value(options: list[Option], text: str) -> str:
    for option in options:
        if option.text == text:
            return option.value
    raise ValueError(f"Could not find option {text!r}. Available: {', '.join(option.text for option in options)}")


def build_search_form(search_html: str, district: str, gender: str, age_group: str, season_value: str) -> dict[str, str]:
    form = parse_forms(search_html)
    return {
        **form.hidden,
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__LASTFOCUS": "",
        FIELD_DISTRICT: option_value(form.selects[FIELD_DISTRICT], district),
        FIELD_GENDER: option_value(form.selects[FIELD_GENDER], gender),
        FIELD_AGE_GROUP: option_value(form.selects[FIELD_AGE_GROUP], age_group),
        FIELD_SEASON: season_value,
        FIELD_SEARCH_BUTTON: "Søg",
    }

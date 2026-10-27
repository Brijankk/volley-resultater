from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from .html_tools import parse_links


def query_int(url: str, key: str) -> int | None:
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get(key)
    if not values:
        return None
    try:
        return int(values[0])
    except ValueError:
        return None


def parse_league_links(html: str) -> list[tuple[str, int]]:
    leagues: list[tuple[str, int]] = []
    for link in parse_links(html):
        raekke_id = query_int(link.href, "RaekkeId")
        if link.text and raekke_id is not None:
            leagues.append((link.text, raekke_id))
    return leagues


def parse_pools(html: str, final_url: str) -> list[dict]:
    pulje_id = query_int(final_url, "PuljeId")
    if pulje_id is not None:
        return [{"pool_name": "Række 1", "pool_id": pulje_id}]

    html_has_oversigt = html.find('Oversigt') == -1
    href_searchword = "Kampprogram.aspx" if html_has_oversigt else "Pulje-Stilling.aspx"
    text_searchword = "Kampprogram" if html_has_oversigt else "Stilling"

    pools: list[dict] = []
    for link in parse_links(html):
        if href_searchword not in link.href:
            continue
        link_pulje_id = query_int(link.href, "PuljeId")
        if link_pulje_id is None or not link.text:
            continue
        name = "Række 1" if link.text == text_searchword else link.text
        if any(pool["pool_id"] == link_pulje_id for pool in pools):
            continue
        pools.append({
            "pool_name": name,
            "pool_id": link_pulje_id,
        })

    return pools

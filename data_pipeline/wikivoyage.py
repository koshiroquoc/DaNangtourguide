"""Fetch factual listing fields from Wikivoyage without copying prose."""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Iterable


API_URL = "https://en.wikivoyage.org/w/api.php"
PAGE_TITLE = "Da Nang"
USER_AGENT = "DaNangTourGuide-data-pipeline/2.1 (research project)"
LISTING_TYPES = {
    "eat": "eat",
    "drink": "eat",
    "see": "see",
    "do": "see",
    "sleep": "stay",
}


def _api_request(parameters: dict[str, str]) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {**parameters, "format": "json", "formatversion": "2"}
    )
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_page(*, title: str = PAGE_TITLE) -> dict[str, Any]:
    """Return current wikitext plus immutable revision and attribution links."""
    parsed = _api_request(
        {
            "action": "parse",
            "page": title,
            "prop": "wikitext|revid",
        }
    )["parse"]
    revision_id = int(parsed["revid"])
    revision_data = _api_request(
        {
            "action": "query",
            "prop": "revisions",
            "revids": str(revision_id),
            "rvprop": "ids|timestamp",
        }
    )
    revision = revision_data["query"]["pages"][0]["revisions"][0]
    slug = title.replace(" ", "_")
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "title": title,
        "wikitext": parsed["wikitext"],
        "revision_id": revision_id,
        "revision_at": revision["timestamp"],
        "retrieved_at": retrieved_at,
        "source_url": f"https://en.wikivoyage.org/w/index.php?title={slug}&oldid={revision_id}",
        "history_url": f"https://en.wikivoyage.org/w/index.php?title={slug}&action=history",
        "source_license": "CC-BY-SA-4.0",
        "attribution": f"Wikivoyage contributors to {title}; see page history",
    }


def _template_bodies(wikitext: str) -> Iterable[str]:
    """Yield balanced top-level template bodies, including nested-safe values."""
    position = 0
    while position < len(wikitext) - 1:
        start = wikitext.find("{{", position)
        if start < 0:
            return
        cursor = start + 2
        depth = 1
        while cursor < len(wikitext) - 1 and depth:
            pair = wikitext[cursor : cursor + 2]
            if pair == "{{":
                depth += 1
                cursor += 2
            elif pair == "}}":
                depth -= 1
                cursor += 2
            else:
                cursor += 1
        if depth == 0:
            yield wikitext[start + 2 : cursor - 2]
            position = cursor
        else:
            return


def _split_top_level(value: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    start = 0
    brace_depth = 0
    link_depth = 0
    position = 0
    while position < len(value):
        pair = value[position : position + 2]
        if pair == "{{":
            brace_depth += 1
            position += 2
            continue
        if pair == "}}" and brace_depth:
            brace_depth -= 1
            position += 2
            continue
        if pair == "[[":
            link_depth += 1
            position += 2
            continue
        if pair == "]]" and link_depth:
            link_depth -= 1
            position += 2
            continue
        if value[position] == delimiter and brace_depth == 0 and link_depth == 0:
            parts.append(value[start:position])
            start = position + 1
        position += 1
    parts.append(value[start:])
    return parts


def _clean_markup(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"<!--[\s\S]*?-->", "", value)
    cleaned = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", cleaned)
    cleaned = re.sub(r"\[\[([^\]]+)\]\]", r"\1", cleaned)
    cleaned = re.sub(r"\[(?:https?://\S+)\s+([^\]]+)\]", r"\1", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = cleaned.replace("'''", "").replace("''", "")
    cleaned = html.unescape(re.sub(r"\s+", " ", cleaned)).strip()
    return cleaned or None


def _parameters(body: str) -> tuple[str, dict[str, str]]:
    parts = _split_top_level(body, "|")
    template_name = parts[0].strip().casefold()
    parameters: dict[str, str] = {}
    for part in parts[1:]:
        key_value = _split_top_level(part, "=")
        if len(key_value) < 2:
            continue
        key = key_value[0].strip().casefold()
        value = "=".join(key_value[1:]).strip()
        if key:
            parameters[key] = value
    return template_name, parameters


def _float(value: str | None) -> float | None:
    try:
        return float(str(value).strip()) if value else None
    except ValueError:
        return None


def extract_listings(page: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract only structured listing facts; intentionally omit `content` prose."""
    listings: list[dict[str, Any]] = []
    for body in _template_bodies(page["wikitext"]):
        template_name, parameters = _parameters(body)
        place_type = LISTING_TYPES.get(template_name)
        name = _clean_markup(parameters.get("name"))
        if not place_type or not name:
            continue
        latitude = _float(parameters.get("lat"))
        longitude = _float(parameters.get("long") or parameters.get("lon"))
        identity = "|".join(
            (
                template_name,
                name.casefold(),
                str(latitude or ""),
                str(longitude or ""),
            )
        )
        listing_id = "wv_" + hashlib.sha1(identity.encode()).hexdigest()[:16]
        last_edit = _clean_markup(parameters.get("lastedit"))
        source_updated_at = (
            f"{last_edit}T00:00:00Z"
            if last_edit and re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_edit)
            else None
        )
        listings.append(
            {
                "id": listing_id,
                "type": place_type,
                "name": name,
                "latitude": latitude,
                "longitude": longitude,
                "address": _clean_markup(parameters.get("address")),
                "opening_hours": _clean_markup(parameters.get("hours")),
                "phone": _clean_markup(parameters.get("phone")),
                "website": _clean_markup(parameters.get("url")),
                "price_text": _clean_markup(parameters.get("price")),
                "source": "Wikivoyage",
                "source_url": page["source_url"],
                "source_history_url": page["history_url"],
                "source_license": page["source_license"],
                "source_revision": page["revision_id"],
                "page_revision_at": page["revision_at"],
                "source_updated_at": source_updated_at,
                "retrieved_at": page["retrieved_at"],
                "attribution": page["attribution"],
            }
        )
    return listings

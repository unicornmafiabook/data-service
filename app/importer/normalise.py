import json
import re
from typing import Any
from urllib.parse import urlparse

import tldextract


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).replace("\xa0", " ").strip()
    if value == "" or value.lower() in {"nan", "none", "null"}:
        return None
    return value


def normalize_name(name: Any) -> str | None:
    name = clean_text(name)
    if not name:
        return None
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or None


def clean_website(url: Any) -> str | None:
    url = clean_text(url)
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        return None
    domain = parsed.netloc.lower().replace("www.", "")
    return f"https://{domain}"


def extract_domain(url: Any) -> str | None:
    url = clean_text(url)
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    extracted = tldextract.extract(url)
    if not extracted.domain or not extracted.suffix:
        return None
    return f"{extracted.domain}.{extracted.suffix}".lower()


def parse_money(value: Any) -> float | None:
    value = clean_text(value)
    if not value:
        return None
    text = value.lower().replace(",", "")
    text = text.replace("$", "").replace("£", "").replace("€", "")
    multiplier = 1
    if "billion" in text or "bn" in text:
        multiplier = 1_000_000_000
    elif "million" in text or re.search(r"\d+(\.\d+)?m\b", text):
        multiplier = 1_000_000
    numbers = re.findall(r"\d+\.?\d*", text)
    if not numbers:
        return None
    return float(numbers[0]) * multiplier


def json_or_none(value: Any) -> Any:
    value = clean_text(value)
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def split_list(value: Any) -> list[str]:
    value = clean_text(value)
    if not value:
        return []
    parts = re.split(r",|;|\||/", value)
    return [p.strip() for p in parts if p and p.strip()]


def normalize_stage(stage: Any) -> str | None:
    stage = clean_text(stage)
    if not stage:
        return None
    s = stage.lower().strip()
    s = re.sub(r"^\d+\.\s*", "", s)
    mapping = {
        "idea": "idea",
        "patent": "idea",
        "prototype": "prototype",
        "pre-seed": "pre_seed",
        "pre seed": "pre_seed",
        "seed": "seed",
        "early revenue": "early_revenue",
        "series a": "series_a",
        "series b": "series_b",
        "series c": "series_c",
        "growth": "growth",
        "scaling": "growth",
        "large buyout": "buyout",
        "mid market buyout": "buyout",
        "small buyout": "buyout",
        "mega buyout": "buyout",
        "buyout": "buyout",
        "secondary": "secondary",
        "infrastructure": "infrastructure",
    }
    for key, value in mapping.items():
        if key in s:
            return value
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_") or None


def split_stages(value: Any) -> list[str]:
    stages = []
    for part in split_list(value):
        normalised = normalize_stage(part)
        if normalised:
            stages.append(normalised)
    return sorted(set(stages))


def normalize_sector(sector: Any) -> str | None:
    sector = clean_text(sector)
    if not sector:
        return None
    s = sector.lower().strip()
    if "fintech" in s or "financial" in s:
        return "fintech"
    if "software" in s or "saas" in s:
        return "software"
    if "deep tech" in s or "deeptech" in s:
        return "deeptech"
    if "health" in s:
        return "healthcare"
    if "consumer" in s:
        return "consumer"
    if "e-commerce" in s or "ecommerce" in s:
        return "ecommerce"
    if "b2b" in s:
        return "b2b"
    if "climate" in s or "energy" in s:
        return "climate"
    if "real estate" in s or "proptech" in s:
        return "real_estate"
    if "infrastructure" in s:
        return "infrastructure"
    if "industrial" in s:
        return "industrial"
    if "media" in s:
        return "media"
    if "logistics" in s or "supply chain" in s:
        return "logistics"
    if "all industry" in s or "sector agnostic" in s or "generalist" in s:
        return "generalist"
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_") or None


def split_sectors(value: Any) -> list[str]:
    sectors = []
    for part in split_list(value):
        normalised = normalize_sector(part)
        if normalised:
            sectors.append(normalised)
    return sorted(set(sectors))


def normalize_geo(value: Any) -> str | None:
    geo = clean_text(value)
    if not geo:
        return None
    replacements = {
        "UK": "United Kingdom",
        "U.K.": "United Kingdom",
        "USA": "United States",
        "U.S.": "United States",
        "US": "United States",
        "UAE": "United Arab Emirates",
    }
    return replacements.get(geo, geo)


def split_geographies(value: Any) -> list[str]:
    geos = []
    for part in split_list(value):
        normalised = normalize_geo(part)
        if normalised:
            geos.append(normalised)
    return sorted(set(geos))


def split_portfolio_companies(value: Any) -> list[str]:
    value = clean_text(value)
    if not value:
        return []
    parts = re.split(r",|;|\sand\s", value)
    return sorted(set(p.strip() for p in parts if len(p.strip()) > 1))

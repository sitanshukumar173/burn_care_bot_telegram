"""Find nearby hospitals with OpenStreetMap (Overpass + Nominatim). Free, no API key."""

import asyncio
import logging
import math
import re
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


@dataclass
class Place:
    name: str
    kind: str  # "hospital" or "clinic"
    lat: float
    lon: float
    distance_km: float
    phone: str | None
    burn_unit: bool
    major: bool  # teaching / government / emergency hospital

    @property
    def directions_url(self) -> str:
        return f"https://www.google.com/maps/dir/?api=1&destination={self.lat},{self.lon}"


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _tag_text(tags: dict) -> str:
    return " ".join([
        tags.get("name", ""),
        tags.get("name:en", ""),
        tags.get("healthcare:speciality", ""),
        tags.get("description", ""),
    ]).lower()


def _is_burn_unit(text: str) -> bool:
    return "burn" in text or "plastic_surgery" in text or "plastic surgery" in text


# Single-speciality places that will not treat a burn (matched as whole words).
_IRRELEVANT = re.compile(
    r"\b(eye|netra|nethralaya|ophthalm\w*|dental|dentist\w*|urology|ent|ivf|fertility|"
    r"maternity|diagnostic\w*|pathology|lab|laboratory|veterinary|vet|ayurved\w*|"
    r"homoeo\w*|homeo\w*|physiotherapy|blood|pet|pets|animal|canser|psychiatr\w*|rehab\w*|de-addiction|cancer|oncology)\b"
)
_CAMPUS_PART = re.compile(r"\b(block|wing|ward|building|gate)\b", re.IGNORECASE)
_MAJOR = re.compile(
    r"\b(aiims|medical college|medical sciences|government|govt|sadar|district hospital|"
    r"general hospital|civil hospital|referral hospital|pmch|igims|nmch)\b"
)


class HospitalFinder:
    def __init__(self, user_agent: str):
        self._headers = {"User-Agent": user_agent}

    async def geocode(self, query: str) -> tuple[float, float, str] | None:
        for params in (
            {"q": query, "format": "json", "limit": 1, "countrycodes": "in"},
            {"q": query, "format": "json", "limit": 1},
        ):
            try:
                async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
                    resp = await client.get(NOMINATIM_URL, params=params)
                    resp.raise_for_status()
                    results = resp.json()
                if results:
                    top = results[0]
                    return float(top["lat"]), float(top["lon"]), top.get("display_name", query)
            except Exception as e:
                log.warning("Geocoding error for %s: %s", query, e)
        return None

    async def _overpass(self, lat: float, lon: float, radius_m: int) -> list[dict]:
        query = f"""
        [out:json][timeout:25];
        (
          nwr["amenity"="hospital"](around:{radius_m},{lat},{lon});
          nwr["amenity"="clinic"](around:{radius_m},{lat},{lon});
          nwr["healthcare"="hospital"](around:{radius_m},{lat},{lon});
        );
        out center tags 100;
        """
        async def fetch(client: httpx.AsyncClient, url: str) -> list[dict]:
            resp = await client.post(url, data={"data": query})
            resp.raise_for_status()
            return resp.json().get("elements", [])

        # Public mirrors are often slow, so ask all at once and take the first good answer.
        async with httpx.AsyncClient(headers=self._headers, timeout=20) as client:
            tasks = {asyncio.create_task(fetch(client, url)): url for url in OVERPASS_URLS}
            last_error: Exception = httpx.HTTPError("no Overpass mirror responded")
            try:
                for done in asyncio.as_completed(tasks, timeout=12):
                    try:
                        return await done
                    except (httpx.HTTPError, ValueError) as exc:
                        log.warning("Overpass mirror failed: %s", exc)
                        last_error = exc
            except TimeoutError:
                last_error = httpx.TimeoutException("Overpass mirrors timed out")
            finally:
                for task in tasks:
                    task.cancel()
        raise httpx.HTTPError(str(last_error))

    async def _nominatim_hospitals(self, lat: float, lon: float) -> list[tuple[dict, float, float]]:
        """Backup source when Overpass is down: hospitals in a ~30 km box."""
        d = 0.27
        params = {
            "amenity": "hospital", "format": "jsonv2", "limit": 40, "bounded": 1,
            "extratags": 1, "viewbox": f"{lon - d},{lat + d},{lon + d},{lat - d}",
        }
        async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
            resp = await client.get(NOMINATIM_URL, params=params)
            resp.raise_for_status()
        results = []
        for r in resp.json():
            tags = dict(r.get("extratags") or {})
            tags.setdefault("name", r.get("name") or "")
            tags.setdefault("amenity", r.get("type"))
            results.append((tags, float(r["lat"]), float(r["lon"])))
        return results

    @staticmethod
    def _add(places: dict, lat: float, lon: float, tags: dict, plat, plon) -> None:
        name = tags.get("name") or tags.get("name:en")
        if not name or plat is None or plon is None:
            return
        text = _tag_text(tags)
        burn_unit = _is_burn_unit(text)
        if _IRRELEVANT.search(text) and not burn_unit:
            return
        if _CAMPUS_PART.search(name) and not re.search(r"hospital|medical", name, re.IGNORECASE):
            return
        kind = "hospital" if "hospital" in (tags.get("amenity"), tags.get("healthcare")) else "clinic"
        key = (name.lower(), round(plat, 2), round(plon, 2))
        places.setdefault(key, Place(
            name=name,
            kind=kind,
            lat=plat,
            lon=plon,
            distance_km=_haversine_km(lat, lon, plat, plon),
            phone=tags.get("phone") or tags.get("contact:phone"),
            burn_unit=burn_unit,
            major=bool(_MAJOR.search(text)) or tags.get("emergency") == "yes",
        ))

    async def nearby(self, lat: float, lon: float, limit: int = 8) -> list[Place]:
        # Ask both sources at once: Overpass (detailed, includes clinics, often overloaded)
        # and Nominatim (fast, hospitals only, ~30 km box).
        overpass, nominatim = await asyncio.gather(
            self._overpass(lat, lon, 15_000),
            self._nominatim_hospitals(lat, lon),
            return_exceptions=True,
        )
        if isinstance(overpass, Exception) and isinstance(nominatim, Exception):
            raise httpx.HTTPError(f"Overpass: {overpass}; Nominatim: {nominatim}")

        places: dict[tuple, Place] = {}
        if isinstance(overpass, Exception):
            log.warning("Overpass unavailable, using Nominatim only: %s", overpass)
        else:
            for el in overpass:
                center = el.get("center", {})
                self._add(places, lat, lon, el.get("tags", {}),
                          el.get("lat") or center.get("lat"), el.get("lon") or center.get("lon"))
        if isinstance(nominatim, Exception):
            log.warning("Nominatim hospital search failed: %s", nominatim)
        else:
            for tags, plat, plon in nominatim:
                self._add(places, lat, lon, tags, plat, plon)

        # Nearest hospitals first (clinics after), since time matters most.
        # Burn units and major hospitals further away are appended so they are not missed.
        ranked = sorted(places.values(), key=lambda p: (p.kind != "hospital", p.distance_km))
        top = ranked[:limit]
        extra = [p for p in ranked[limit:] if p.burn_unit or p.major]
        extra.sort(key=lambda p: (not p.burn_unit, p.kind != "hospital", p.distance_km))
        return top + extra[:3]


# ---------- spotting "find a hospital" requests in free text ----------

_FACILITY = re.compile(
    r"\b(hospitals?|clinics?|doctors?|burns? (?:unit|cent(?:re|er)|ward)|ambulance|medical cent(?:re|er)"
    r"|aspatal|aspataal|haspatal|daktar|dawakhana|davakhana)\b"
    r"|अस्पताल|हॉस्पिटल|हस्पताल|डॉक्टर|दवाखाना",
    re.IGNORECASE,
)
_LOCATOR = re.compile(
    r"\b(near|nearby|nearest|close|closest|around|find|where|location|address|list|show"
    r"|paas|pass|aaspaas|najdeek|nazdeek|najdik|nazdik|kahan|kaha|kidhar|dhundo|dhoondo|dhundho|batao|bataiye|bataye)\b"
    r"|पास|नजदीक|नज़दीक|कहाँ|कहां|ढूँढ|ढूंढ|बताओ|बताइए|बताएं|बताएँ",
    re.IGNORECASE,
)
# English: "hospital in Bihta", "doctors near Danapur"
_PLACE = re.compile(
    r"\b(?:in|near|at|around)\s+(?!(?:me|my|here|by|this|case|the case)\b)([^?.!\n]{2,60})", re.IGNORECASE
)
# Hindi / Hinglish: "Bihta mein hospital", "Patna ke paas aspatal", "बिहटा में अस्पताल"
_PLACE_BEFORE = re.compile(
    r"((?:[^\s,?.!।]+\s+){0,2}[^\s,?.!।]+)\s+"
    r"(?:mein|me|mai|ke\s+paas|ke\s+pass|ke\s+najdeek|ke\s+nazdeek|ke\s+najdik|ke\s+nazdik"
    r"|में|मे|के\s+पास|के\s+नज़दीक|के\s+नजदीक)(?=\s|$|[?.!,।])",
    re.IGNORECASE,
)
_NOT_A_PLACE = {
    "mere", "mera", "meri", "mujhe", "hamare", "humare", "hum", "main", "yahan", "yaha", "ghar", "aas", "paas",
    "kahan", "kis", "kaun", "koi", "sabse", "najdeeki", "nazdeeki", "near", "nearby", "in", "at", "around",
    "the", "a", "find", "show", "list", "me", "is", "hai", "kya", "batao",
    "मेरे", "मेरा", "मेरी", "मुझे", "हमारे", "हम", "यहाँ", "यहां", "घर", "आस", "कौन", "कोई", "सबसे", "क्या",
    "नज़दीकी", "नजदीकी",
    "suggest", "tell", "give", "help", "recommend", "please", "pls", "plz", "send", "want", "need",
}


def _place_before(text: str) -> str | None:
    match = _PLACE_BEFORE.search(text)
    if not match:
        return None
    words = match.group(1).split()
    # keep only the words after the last filler or facility word: "koi hospital Bihta" -> "Bihta"
    for i in range(len(words) - 1, -1, -1):
        if words[i].lower() in _NOT_A_PLACE or _FACILITY.fullmatch(words[i]):
            words = words[i + 1:]
            break
    return " ".join(words) or None


def parse_hospital_request(text: str) -> tuple[bool, str | None]:
    """Return (is a request to find hospitals, place name if one was given)."""
    if not _FACILITY.search(text):
        return False, None
    match = _PLACE.search(text)
    place = match.group(1).strip(" ,") if match else _place_before(text)
    if not _LOCATOR.search(text) and not place and len(text.split()) > 3:
        return False, None  # e.g. "should I go to hospital for a small blister?"
    if place:
        place = re.sub(r"\s+(please|pls|plz)$", "", place, flags=re.IGNORECASE).strip()
        if place.lower() in _NOT_A_PLACE or place.lower() in {"near me", "around me", "close to me", "here"}:
            place = None
    return True, place

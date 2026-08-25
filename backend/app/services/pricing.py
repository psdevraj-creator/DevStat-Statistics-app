"""DevStat regional pricing.

Prices are shown and charged in GBP, but the amount is adjusted to the user's
income region (World Bank income group) so the tool stays affordable in low- and
lower-middle-income countries with large populations. Detection uses the client
IP via ipinfo.io (best-effort, cached), falling back to the country income map.

The app and banners show ONLY the price for the user's region.
"""
from __future__ import annotations
import logging, threading, time, urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger("devstat.pricing")

# Amounts in GBP pence. mult = fraction of the high-income price.
TIERS = {
    "high":         {"mult": 1.0,  "sub": 2500, "teach": 100, "qb": 500, "label": "High income"},
    "upper_middle": {"mult": 0.5,  "sub": 1250, "teach": 50,  "qb": 250, "label": "Upper-middle income"},
    "lower_middle": {"mult": 0.32, "sub": 800,  "teach": 50,  "qb": 150, "label": "Lower-middle income"},
    "low":          {"mult": 0.2,  "sub": 500,  "teach": 50,  "qb": 100, "label": "Low income"},
}
DEFAULT_TIER = "high"

# World Bank income-group country map (ISO alpha-2 -> tier). Anything unlisted = high.
_LOW = set("af bd bf bi bt cd cf cg dj er et gm gn gw ht ke kp lr ls mg ml mm mw mz ne ng np rw sd sl so ss sy td tg tl tz ug ye zm zw".split())
_LOWER_MIDDLE = set("al ao as az ba bj bo cv kh cm cn co km cg ci eg gh gt hn in id ir jo ki kg mr mh fm mn ma na ni pk pg ps ph sb st sn lk tj tn uz vu vn ua".split())
_UPPER_MIDDLE = set("ar am aw az ba bq by bw bz ba br bn bg cv cl cn co cr ci hr cu cw cy dm do ec ge gq fk fj ga gw gt gy hu in iq jo kz km xk lv lb ly my mv mt mu mx me md mn ma na nm mk om pa pe py ro ru rw? sc rs za kn st lc vc ws sk za sr th tn tr tm tv va ve zm?".split())
_UPPER_MIDDLE = set("ar am aw bq by bw bz ba br bn bg cl cr cu cw cy dm do ec ge gq fk fj ga gy hu iq jo kz lv lb ly my mv mt mu mx me md mn ma nm mk om pa pe py ro ru sc rs za kn lc vc ws sk za sr th tn tr tm tv va ve".split())

COUNTRY_TIER = {}
for c in _LOW: COUNTRY_TIER[c] = "low"
for c in _LOWER_MIDDLE: COUNTRY_TIER[c] = "lower_middle"
for c in _UPPER_MIDDLE: COUNTRY_TIER[c] = "upper_middle"

_cache = {}
_lock = threading.Lock()

def tier_for_country(cc):
    cc = (cc or "").lower().strip()[:2]
    if not cc: return DEFAULT_TIER
    return COUNTRY_TIER.get(cc, DEFAULT_TIER)

def _geo_ipinfo(ip):
    try:
        url = "https://ipinfo.io/%s/json" % ip
        with urllib.request.urlopen(url, timeout=4) as r:
            data = r.read().decode("utf-8", "ignore")
        import json
        return (json.loads(data) or {}).get("country")
    except Exception as e:
        logger.warning("geo lookup failed for %s: %s", ip, e)
        return None

def tier_for_ip(ip):
    ip = ip or ""
    if not ip: return DEFAULT_TIER
    with _lock:
        hit = _cache.get(ip)
        if hit and time.time() - hit[1] < 86400:
            return hit[0]
    cc = _geo_ipinfo(ip)
    tier = tier_for_country(cc) if cc else DEFAULT_TIER
    with _lock:
        _cache[ip] = (tier, time.time())
    return tier

def region_status(ip):
    tier = tier_for_ip(ip)
    t = TIERS[tier]
    return {
        "region": tier, "region_label": t["label"], "currency": "gbp",
        "prices": {"subscription": t["sub"], "teaching": t["teach"], "questionbank": t["qb"]},
        "multiplier": t["mult"],
        "note": "Prices are shown in GBP and adjusted to your region.",
    }


# Stripe price ids per tier (GBP). Generated for the current Stripe mode.
STRIPE_PRICES = {'high': {'sub': 'price_1U89c1RgNTPfknVQFEvcvgsF', 'teach': 'price_1U89c1RgNTPfknVQoFZBzkSW', 'qb': 'price_1U89c1RgNTPfknVQzRKR042B'}, 'upper_middle': {'sub': 'price_1U89c2RgNTPfknVQErBPXqEO', 'teach': 'price_1U89c2RgNTPfknVQMhvC9D47', 'qb': 'price_1U89c2RgNTPfknVQdZncicKu'}, 'lower_middle': {'sub': 'price_1U89c3RgNTPfknVQgKhe3Mfb', 'teach': 'price_1U89c3RgNTPfknVQZ7KnJ9cR', 'qb': 'price_1U89c3RgNTPfknVQh6vrfuji'}, 'low': {'sub': 'price_1U89c4RgNTPfknVQPpZyqqod', 'teach': 'price_1U89c4RgNTPfknVQZv7icLHG', 'qb': 'price_1U89c4RgNTPfknVQ1iiMyyyD'}}

def stripe_price_id(tier, product):
    t = STRIPE_PRICES.get(tier, STRIPE_PRICES.get('high'))
    return t.get(product)

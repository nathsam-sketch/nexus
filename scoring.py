import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

def clamp(n: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, n))

def safe_ratio(a: int, b: int) -> float:
    return (a / b) if b > 0 else 0.0

def heat_bar(score_0_100: int, width: int = 10) -> str:
    s = int(clamp(score_0_100, 0, 100))
    filled = int(round((s / 100.0) * width))
    return "█" * filled + "░" * (width - filled)

def avatar_fingerprint(asset_ids: List[int]) -> str:
    s = ",".join(map(str, sorted(asset_ids)))
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]

def parse_iso(iso: str):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None

def score_maturity(days_old: int, created_missing: bool) -> int:
    if created_missing:
        return 10
    if days_old >= 3650: return 100
    if days_old >= 1825: return 85
    if days_old >= 365: return 70
    if days_old >= 90: return 55
    if days_old >= 30: return 40
    return 25

def score_social(friends: int, followers: int, following: int) -> int:
    social = friends + followers
    if social >= 5000: base = 100
    elif social >= 1000: base = 85
    elif social >= 200: base = 70
    elif social >= 50: base = 55
    elif social >= 10: base = 40
    else: base = 25

    ratio = safe_ratio(followers, max(1, following))
    if following >= 500 and followers <= 50:
        base -= 15
    elif ratio < 0.2 and following >= 200:
        base -= 10
    return int(clamp(base, 0, 100))

def score_activity(badge_sample_count: int, last_badge_days: Optional[int], games_count_sample: int) -> int:
    if badge_sample_count >= 100: base = 50
    elif badge_sample_count >= 50: base = 40
    elif badge_sample_count >= 10: base = 28
    elif badge_sample_count >= 1: base = 15
    else: base = 5

    if last_badge_days is not None:
        if last_badge_days <= 7: base += 40
        elif last_badge_days <= 30: base += 30
        elif last_badge_days <= 90: base += 20
        elif last_badge_days <= 365: base += 10
        else: base += 3

    if games_count_sample >= 5: base += 10
    elif games_count_sample >= 1: base += 5

    return int(clamp(base, 0, 100))

def badge_time_bucket_counts(badges: List[Dict[str, Any]]) -> Dict[str, int]:
    buckets = {"0-7d": 0, "8-30d": 0, "31-90d": 0, "91-365d": 0, "366+d": 0, "unknown": 0}
    now = datetime.now(timezone.utc)
    for b in badges:
        iso = b.get("awardedDate")
        dt = parse_iso(iso) if isinstance(iso, str) else None
        if not dt:
            buckets["unknown"] += 1
            continue
        days = (now - dt).days
        if days <= 7: buckets["0-7d"] += 1
        elif days <= 30: buckets["8-30d"] += 1
        elif days <= 90: buckets["31-90d"] += 1
        elif days <= 365: buckets["91-365d"] += 1
        else: buckets["366+d"] += 1
    return buckets
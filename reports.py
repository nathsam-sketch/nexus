# nexus/reports.py
import discord
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from nexus.config import settings
from nexus.scoring import (
    safe_ratio,
    heat_bar,
    avatar_fingerprint,
    parse_iso,
    score_maturity,
    score_social,
    score_activity,
    badge_time_bucket_counts,
    clamp,
)

# ----------------------------
# Small formatting helpers
# ----------------------------
def fmt_int(n: int) -> str:
    try:
        return f"{int(n):,}"
    except Exception:
        return "0"


def short_dt(iso: str) -> str:
    dt = parse_iso(iso) if isinstance(iso, str) and iso else None
    return dt.strftime("%b %d, %Y") if dt else "Unknown"


def age_days(iso: str) -> int:
    dt = parse_iso(iso) if isinstance(iso, str) and iso else None
    return (datetime.now(timezone.utc) - dt).days if dt else 0


def presence_label(p: int) -> str:
    return {0: "Offline", 1: "Online", 2: "In-Game", 3: "In-Studio"}.get(int(p), "Unknown")


def forensic_embed(title: str, subtitle: str = "") -> discord.Embed:
    e = discord.Embed(title=title, description=subtitle, color=settings.color)
    e.set_footer(text="Nexus • OSINT")
    return e


def add(e: discord.Embed, name: str, value: str, inline: bool = False) -> None:
    e.add_field(name=(name or "—")[:256], value=(value or "—")[:1024], inline=inline)


# ----------------------------
# Analyst summary
# ----------------------------
def analyst_summary_single(days_old: int, created_missing: bool, overall: int, flags: List[str]) -> str:
    bits: List[str] = []

    if created_missing:
        bits.append("Created date missing from API (maturity signal weaker).")
    else:
        if days_old < 30:
            bits.append("Very new account window.")
        elif days_old > 365:
            bits.append("Older account age supports legitimacy.")

    if overall >= 75:
        bits.append("Public signals look consistent and established.")
    elif overall >= 45:
        bits.append("Mixed signals; some strengths, some gaps.")
    else:
        bits.append("Low footprint signals; caution interpreting.")

    majors = [f for f in (flags or []) if isinstance(f, str) and f.startswith("⚠️")]
    if majors:
        bits.append("Key flags: " + "; ".join(m.replace("⚠️ ", "") for m in majors[:2]))

    return " ".join(bits)[:900]


# ----------------------------
# Main builder (Deep Scan)
# ----------------------------
def build_deep_scan_embeds(
    profile: Dict[str, Any],
    presence: Dict[str, Any],
    headshot: Optional[str],
    friends: int,
    followers: int,
    following: int,
    groups: List[Dict[str, Any]],
    group_enriched: List[Tuple[int, str, str, Optional[int], Optional[int], Optional[str]]],
    avg_members: int,
    small_groups: int,
    high_rank_count: int,
    ownerish_count: int,
    wearing: List[int],
    avatar: Dict[str, Any],
    recent_badges: List[Dict[str, Any]],
    badges_sample: List[Dict[str, Any]],
    games_sample: List[Dict[str, Any]],
    universe_name: Optional[str],
) -> List[discord.Embed]:
    # ----------------------------
    # Defensive normalization (prevents TypeError)
    # ----------------------------
    if not isinstance(profile, dict):
        profile = {}
    if not isinstance(presence, dict):
        presence = {}
    if not isinstance(groups, list):
        groups = []
    if not isinstance(group_enriched, list):
        group_enriched = []
    if not isinstance(wearing, list):
        wearing = []
    if not isinstance(avatar, dict):
        avatar = {}
    if not isinstance(recent_badges, list):
        recent_badges = []
    if not isinstance(badges_sample, list):
        badges_sample = []
    if not isinstance(games_sample, list):
        games_sample = []

    # Safe ints
    try:
        friends = int(friends)
    except Exception:
        friends = 0
    try:
        followers = int(followers)
    except Exception:
        followers = 0
    try:
        following = int(following)
    except Exception:
        following = 0
    try:
        avg_members = int(avg_members)
    except Exception:
        avg_members = 0
    try:
        small_groups = int(small_groups)
    except Exception:
        small_groups = 0
    try:
        high_rank_count = int(high_rank_count)
    except Exception:
        high_rank_count = 0
    try:
        ownerish_count = int(ownerish_count)
    except Exception:
        ownerish_count = 0

    # Identity basics
    uid = profile.get("id") or profile.get("userId") or profile.get("user_id") or "—"
    username = profile.get("name") or "Unknown"
    display = profile.get("displayName") or "—"

    created_iso = profile.get("created") or ""
    created_missing = not bool(created_iso)
    days_old = age_days(created_iso)
    created_str = short_dt(created_iso)

    verified = "✅" if bool(profile.get("hasVerifiedBadge")) else "—"
    banned = "✅" if bool(profile.get("isBanned")) else "—"

    # Presence
    pres_type = int(presence.get("userPresenceType", 0) or 0)
    pres_name = presence_label(pres_type)
    last_location = presence.get("lastLocation") or "—"
    place_id = presence.get("placeId")
    universe_id = presence.get("universeId")

    presence_line = f"**{pres_name}** — {last_location}"
    if universe_name:
        presence_line += f"\nGame: **{universe_name}**"
    if pres_name in ("In-Game", "In-Studio") and (place_id or universe_id):
        presence_line += f"\nPlaceId: `{place_id or '—'}` • UniverseId: `{universe_id or '—'}`"

    # Badge recency
    last_badge_days: Optional[int] = None
    if recent_badges:
        awarded = recent_badges[0].get("awardedDate") if isinstance(recent_badges[0], dict) else None
        dt = parse_iso(awarded) if isinstance(awarded, str) else None
        if dt:
            last_badge_days = (datetime.now(timezone.utc) - dt).days

    # Social metrics
    social_size = friends + followers
    follower_ratio = safe_ratio(followers, max(1, following))
    friends_followers_ratio = safe_ratio(friends, max(1, followers))

    # Subscores
    maturity = score_maturity(days_old, created_missing)
    social = score_social(friends, followers, following)
    activity = score_activity(len(badges_sample), last_badge_days, len(games_sample))
    avatar_custom_score = 25 if len(wearing) <= 6 else (45 if len(wearing) <= 10 else 65 if len(wearing) <= 20 else 85)

    groups_count = len(groups)
    group_footprint_score = 15 if groups_count == 0 else (40 if groups_count < 5 else 60 if groups_count < 15 else 80)
    if high_rank_count >= 3:
        group_footprint_score = int(clamp(group_footprint_score + 10, 0, 100))

    overall = int(
        clamp(
            maturity * 0.30
            + social * 0.25
            + activity * 0.30
            + avatar_custom_score * 0.075
            + group_footprint_score * 0.075,
            0,
            100,
        )
    )

    # Flags
    flags: List[str] = []
    if created_missing:
        flags.append("⚠️ Missing created timestamp (API returned none)")
    if days_old < 30:
        flags.append("⚠️ Very new account (<30d)")
    if friends == 0 and followers == 0:
        flags.append("⚠️ No social footprint")
    if groups_count == 0:
        flags.append("⚠️ No groups detected")
    if len(badges_sample) == 0:
        flags.append("⚠️ No badges in sample")
    if len(wearing) <= 6:
        flags.append("⚠️ Low avatar customization (possible alt)")
    if following >= 500 and followers <= 50:
        flags.append("⚠️ High following + low followers (follow-spam pattern)")
    if not flags:
        flags.append("No major red flags from public signals")

    # Avatar forensic details
    fp = avatar_fingerprint([int(x) for x in wearing if isinstance(x, int)])
    av_type = avatar.get("playerAvatarType", "—") if isinstance(avatar, dict) else "—"
    scales = avatar.get("scales", {}) if isinstance(avatar, dict) else {}
    if not isinstance(scales, dict):
        scales = {}
    body_colors = avatar.get("bodyColors", {}) if isinstance(avatar, dict) else {}
    if not isinstance(body_colors, dict):
        body_colors = {}

    # Badge buckets
    bucket = badge_time_bucket_counts(badges_sample)
    bucket_line = (
        f"0-7d **{bucket.get('0-7d', 0)}** • 8-30d **{bucket.get('8-30d', 0)}** • 31-90d **{bucket.get('31-90d', 0)}**\n"
        f"91-365d **{bucket.get('91-365d', 0)}** • 366+d **{bucket.get('366+d', 0)}** • unknown **{bucket.get('unknown', 0)}**"
    )
    lb = f"Last badge: **{fmt_int(last_badge_days)}d ago**" if last_badge_days is not None else "Last badge: **Unknown**"

    # Game totals
    total_visits = 0
    total_playing = 0
    for g in games_sample[:10]:
        if not isinstance(g, dict):
            continue
        total_visits += int(g.get("placeVisits", 0) or 0)
        total_playing += int(g.get("playing", 0) or 0)

    # ----------------------------
    # EMBED 1: Executive Summary
    # ----------------------------
    e0 = forensic_embed("NEXUS • Executive Summary", f"Target: **{username}** (`{uid}`)")
    if headshot:
        e0.set_thumbnail(url=headshot)
        e0.set_author(name="Nexus Intelligence", icon_url=headshot)
    else:
        e0.set_author(name="Nexus Intelligence")

    add(
        e0,
        "🧪 Scoreboard",
        (
            f"Overall: **{overall}/100** `{heat_bar(overall)}`\n"
            f"Maturity: **{maturity}/100** `{heat_bar(maturity)}`\n"
            f"Social: **{social}/100** `{heat_bar(social)}`\n"
            f"Activity: **{activity}/100** `{heat_bar(activity)}`\n"
            f"Avatar Custom: **{avatar_custom_score}/100** `{heat_bar(avatar_custom_score)}`\n"
            f"Group Footprint: **{group_footprint_score}/100** `{heat_bar(group_footprint_score)}`"
        ),
        inline=False,
    )

    add(
        e0,
        "🧷 Key Signals",
        (
            f"Age: **{fmt_int(days_old)}d** • Verified: **{verified}** • Banned: **{banned}**\n"
            f"Social size: **{fmt_int(social_size)}** • Groups: **{fmt_int(groups_count)}** (high-rank: **{fmt_int(high_rank_count)}**)\n"
            f"Badges(sample): **{fmt_int(len(badges_sample))}** • Games(sample): **{fmt_int(len(games_sample))}** • Avatar assets: **{fmt_int(len(wearing))}**"
        ),
        inline=False,
    )

    add(e0, "🧠 Analyst Summary", analyst_summary_single(days_old, created_missing, overall, flags), inline=False)
    add(e0, "🚩 Flags", "\n".join("• " + x for x in flags), inline=False)

    # ----------------------------
    # EMBED 2: Identity & Presence
    # ----------------------------
    e1 = forensic_embed("NEXUS • Identity & Presence")
    if headshot:
        e1.set_thumbnail(url=headshot)

    add(
        e1,
        "🧍 Identity",
        (
            f"Username: **{username}**\n"
            f"Display: **{display}**\n"
            f"Created: **{created_str}**\n"
            f"Age: **{fmt_int(days_old)} days**\n"
            f"Verified: **{verified}** • Banned: **{banned}**"
        ),
        inline=False,
    )
    add(e1, "📡 Presence", presence_line, inline=False)

    bio = (profile.get("description") or "").strip() if isinstance(profile.get("description"), str) else ""
    if bio:
        add(e1, "📝 Profile Bio", bio[:1024], inline=False)

    # ----------------------------
    # EMBED 3: Social Graph
    # ----------------------------
    e2 = forensic_embed("NEXUS • Social Graph")
    add(
        e2,
        "📊 Totals",
        (
            f"Friends: **{fmt_int(friends)}**\n"
            f"Followers: **{fmt_int(followers)}**\n"
            f"Following: **{fmt_int(following)}**\n"
            f"Social size: **{fmt_int(social_size)}**"
        ),
        inline=True,
    )
    add(
        e2,
        "📐 Ratios",
        (
            f"Follower/Following: **{follower_ratio:.2f}**\n"
            f"Friends/Followers: **{friends_followers_ratio:.2f}**"
        ),
        inline=True,
    )

    heur: List[str] = []
    if following >= 500 and followers <= 50:
        heur.append("Follow-spam pattern risk (high following, low followers)")
    if friends == 0 and followers == 0:
        heur.append("No social footprint")
    if not heur:
        heur.append("No major social anomalies detected")
    add(e2, "🧠 Heuristics", "\n".join("• " + h for h in heur), inline=False)

    # ----------------------------
    # EMBED 4: Groups & Affiliations
    # ----------------------------
    e3 = forensic_embed("NEXUS • Groups & Affiliations")
    if group_enriched:
        lines: List[str] = []
        for item in group_enriched[:10]:
            try:
                rr, gname, rname, gid, mc, owner = item
            except Exception:
                continue
            mc_txt = f"{fmt_int(mc)} members" if isinstance(mc, int) else "members: —"
            own_txt = f"owner: {owner}" if isinstance(owner, str) and owner else "owner: —"
            lines.append(f"`{int(rr):>3}` • **{gname}** — {rname}\n↳ `{gid or '—'}` • {mc_txt} • {own_txt}")
        add(e3, "🏢 Top Groups (enriched)", "\n".join(lines) or "—", inline=False)
    else:
        add(e3, "🏢 Top Groups", "No groups found (public).", inline=False)

    add(
        e3,
        "📌 Group Footprint",
        (
            f"Total groups: **{fmt_int(groups_count)}**\n"
            f"High-rank roles (≥200): **{fmt_int(high_rank_count)}**\n"
            f"Owner-ish roles (255): **{fmt_int(ownerish_count)}**\n"
            f"Avg members (top 10): **{fmt_int(avg_members)}**\n"
            f"Small groups (≤1000, top 10): **{fmt_int(small_groups)}**"
        ),
        inline=False,
    )

    # ----------------------------
    # EMBED 5: Avatar Forensics
    # ----------------------------
    e4 = forensic_embed("NEXUS • Avatar Forensics")
    add(
        e4,
        "🧬 Avatar",
        (
            f"Type: **{av_type}**\n"
            f"Wearing assets: **{fmt_int(len(wearing))}**\n"
            f"Fingerprint: `{fp}`\n"
            f"Customization score: **{avatar_custom_score}/100** `{heat_bar(avatar_custom_score)}`"
        ),
        inline=False,
    )
    add(
        e4,
        "🎚 Scales",
        (
            f"H {scales.get('height','—')} • W {scales.get('width','—')} • Head {scales.get('head','—')}\n"
            f"BodyType {scales.get('bodyType','—')} • Proportion {scales.get('proportion','—')}"
        ),
        inline=False,
    )
    add(
        e4,
        "🎨 Body Colors (IDs)",
        (
            f"Head `{body_colors.get('headColorId','—')}` • Torso `{body_colors.get('torsoColorId','—')}`\n"
            f"LArm `{body_colors.get('leftArmColorId','—')}` • RArm `{body_colors.get('rightArmColorId','—')}`\n"
            f"LLeg `{body_colors.get('leftLegColorId','—')}` • RLeg `{body_colors.get('rightLegColorId','—')}`"
        ),
        inline=False,
    )

    # ----------------------------
    # EMBED 6: Activity Profile
    # ----------------------------
    e5 = forensic_embed("NEXUS • Activity Profile")
    add(e5, "🎖 Badges (sample behavior)", f"{lb}\nBuckets:\n{bucket_line}", inline=False)

    if recent_badges:
        lines: List[str] = []
        for b in recent_badges[:10]:
            if not isinstance(b, dict):
                continue
            name = b.get("name", "Badge")
            awarded = b.get("awardedDate", "")
            date = awarded[:10] if isinstance(awarded, str) else "—"
            lines.append(f"• **{name}** — `{date}`")
        if lines:
            add(e5, "🕒 Recent Badges", "\n".join(lines), inline=False)

    if games_sample:
        lines: List[str] = []
        for g in games_sample[:10]:
            if not isinstance(g, dict):
                continue
            gname = g.get("name", "Game")
            visits = int(g.get("placeVisits", 0) or 0)
            playing = int(g.get("playing", 0) or 0)
            lines.append(f"• **{gname}** — Visits **{fmt_int(visits)}**, Playing **{fmt_int(playing)}**")
        add(
            e5,
            "🎮 Public Games (sample)",
            f"Totals: Visits **{fmt_int(total_visits)}**, Playing **{fmt_int(total_playing)}**\n" + "\n".join(lines),
            inline=False,
        )
    else:
        add(e5, "🎮 Public Games (sample)", "No public games returned (or none exist).", inline=False)

    return [e0, e1, e2, e3, e4, e5]
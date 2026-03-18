# cogs/osint.py

import traceback
import discord
from discord.ext import commands
from discord import app_commands

from nexus.auth import ensure_auth
from nexus.discord_utils import send_embeds_visible, send_embeds_dm
from nexus.reports import build_deep_scan_embeds
from nexus.key_store import set_key, remove_key, load_keys, clear_session
from nexus.config import settings


# ---- compat helpers (won't crash if your discord.py doesn't have these decorators) ----
def allow_contexts(guilds=True, dms=True, private_channels=True):
    deco = getattr(app_commands, "allowed_contexts", None)
    if callable(deco):
        return deco(guilds=guilds, dms=dms, private_channels=private_channels)
    return lambda f: f


def allow_installs(guilds=True, users=True):
    deco = getattr(app_commands, "allowed_installs", None)
    if callable(deco):
        return deco(guilds=guilds, users=users)
    return lambda f: f


class OsintCog(commands.Cog):
    def __init__(self, bot: commands.Bot, rblx):
        self.bot = bot
        self.rblx = rblx

    async def _send_ephemeral(self, interaction: discord.Interaction, content: str):
        try:
            if interaction.response.is_done():
                return await interaction.followup.send(content, ephemeral=True)
            return await interaction.response.send_message(content, ephemeral=True)
        except Exception:
            return

    # -------------------------
    # PING
    # -------------------------
    @app_commands.command(name="ping", description="Check if Nexus is online")
    @allow_installs(guilds=True, users=True)
    @allow_contexts(guilds=True, dms=True, private_channels=True)
    async def ping(self, interaction: discord.Interaction):
        where = "DM/GC" if interaction.guild_id is None else "Server"
        await interaction.response.send_message(f"🏓 Nexus online • Context: **{where}**", ephemeral=True)

    # -------------------------
    # LOGOUT
    # -------------------------
    @app_commands.command(name="logout", description="Log out of Nexus authentication")
    @allow_installs(guilds=True, users=True)
    @allow_contexts(guilds=True, dms=True, private_channels=True)
    async def logout(self, interaction: discord.Interaction):
        clear_session(interaction.user.id)
        await interaction.response.send_message(
            "🔒 You have been logged out. Next command will require your access key.",
            ephemeral=True,
        )

    # -------------------------
    # DEEP SCAN
    # -------------------------
    @app_commands.command(name="deep_scan", description="Run a deep Roblox OSINT scan")
    @app_commands.describe(username="Roblox username to scan")
    @allow_installs(guilds=True, users=True)
    @allow_contexts(guilds=True, dms=True, private_channels=True)
    async def deep_scan(self, interaction: discord.Interaction, username: str):

        async def run_scan(authed_interaction: discord.Interaction, authed_label: str):
            try:
                uid = await self.rblx.username_to_id(username)
                if uid is None:
                    return await self._send_ephemeral(authed_interaction, "❌ User not found.")

                profile = await self.rblx.get_profile(uid)
                presence = await self.rblx.get_presence(uid)
                headshot = (
                    await self.rblx.get_headshot(uid, "150x150")
                    or await self.rblx.get_headshot(uid, "420x420")
                    or await self.rblx.get_headshot(uid)
                )

                friends = await self.rblx.get_friends_count(uid)
                followers = await self.rblx.get_followers_count(uid)
                following = await self.rblx.get_followings_count(uid)

                groups = await self.rblx.get_groups(uid)
                wearing = await self.rblx.get_currently_wearing(uid)
                avatar = await self.rblx.get_avatar_details(uid)

                recent_badges = await self.rblx.get_recent_badges(uid, limit=10)
                badges_sample = await self.rblx.get_badges_sample(uid, limit=100)
                games_sample = await self.rblx.get_public_games_sample(uid, limit=10)

                # normalize (TypeError-proof)
                if not isinstance(profile, dict): profile = {}
                if not isinstance(presence, dict): presence = {}
                if not isinstance(groups, list): groups = []
                if not isinstance(wearing, list): wearing = []
                if not isinstance(avatar, dict): avatar = {}
                if not isinstance(recent_badges, list): recent_badges = []
                if not isinstance(badges_sample, list): badges_sample = []
                if not isinstance(games_sample, list): games_sample = []

                profile = dict(profile)
                profile["id"] = int(uid)

                embeds = build_deep_scan_embeds(
                    profile=profile,
                    presence=presence,
                    headshot=headshot,
                    friends=int(friends),
                    followers=int(followers),
                    following=int(following),
                    groups=groups,
                    group_enriched=[],
                    avg_members=0,
                    small_groups=0,
                    high_rank_count=0,
                    ownerish_count=0,
                    wearing=wearing,
                    avatar=avatar,
                    recent_badges=recent_badges,
                    badges_sample=badges_sample,
                    games_sample=games_sample,
                    universe_name=None,
                )

                # ✅ Public embeds in the same DM/GC/server channel where the command was used
                await send_embeds_visible(authed_interaction, embeds)

                # Optional: also DM requester a private copy
                try:
                    await send_embeds_dm(authed_interaction.user, embeds)
                except Exception:
                    pass

            except Exception as e:
                tb = traceback.format_exc()
                await self._send_ephemeral(
                    authed_interaction,
                    f"❌ Report failed: `{type(e).__name__}`\n```{tb[-1400:]}```"
                )
                raise

        await ensure_auth(interaction, require_owner=False, on_authed=run_scan)

    # -------------------------
    # KEY MANAGEMENT (OWNER ONLY)
    # -------------------------
    @app_commands.command(name="key", description="Manage Nexus keys (owner only)")
    @app_commands.describe(action="list/add/remove", label="Key label", value="Key value (for add)")
    @allow_installs(guilds=True, users=True)
    @allow_contexts(guilds=True, dms=True, private_channels=True)
    async def key_manage(self, interaction: discord.Interaction, action: str, label: str = None, value: str = None):

        async def run(authed_interaction: discord.Interaction, authed_label: str):
            act = (action or "").lower().strip()

            if act == "list":
                keys = load_keys()
                labels = ", ".join(sorted(keys.keys())) or "none"
                return await self._send_ephemeral(authed_interaction, f"🔑 Key labels: `{labels}`")

            if act == "add":
                if not label or not value:
                    return await self._send_ephemeral(authed_interaction, "Usage: `/key action:add label:<name> value:<key>`")
                if label.strip().lower() == "owner":
                    return await self._send_ephemeral(authed_interaction, "❌ Not adding `owner` here (we can add a safe rotate command).")
                set_key(label.strip(), value.strip(), settings.master_secret, perms=["scan"])
                return await self._send_ephemeral(authed_interaction, f"✅ Added `{label.strip()}`")

            if act == "remove":
                if not label:
                    return await self._send_ephemeral(authed_interaction, "Usage: `/key action:remove label:<name>`")
                if label.strip().lower() == "owner":
                    return await self._send_ephemeral(authed_interaction, "❌ Can’t remove `owner`.")
                remove_key(label.strip())
                return await self._send_ephemeral(authed_interaction, f"🗑 Removed `{label.strip()}`")

            return await self._send_ephemeral(authed_interaction, "❌ Invalid action. Use `list`, `add`, or `remove`.")

        await ensure_auth(interaction, require_owner=True, on_authed=run)
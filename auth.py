import discord
from typing import Callable, Awaitable, Optional

from nexus.config import settings
from nexus.key_store import verify_key, set_session, get_session_label


class NexusAuthModal(discord.ui.Modal, title="Nexus Secure Access"):
    access_key = discord.ui.TextInput(
        label="Enter Nexus Access Key",
        placeholder="Access key...",
        required=True,
        max_length=80
    )

    def __init__(self, on_success: Callable[[discord.Interaction, str], Awaitable[None]]):
        super().__init__()
        self._on_success = on_success

    async def on_submit(self, interaction: discord.Interaction):
        entered = str(self.access_key.value).strip()
        label = verify_key(entered, settings.master_secret)

        if not label:
            return await interaction.response.send_message("❌ Invalid key.", ephemeral=True)

        # Persist a session for this user (default 6 hours)
        set_session(interaction.user.id, label)

        await interaction.response.send_message("✅ Authenticated.", ephemeral=True)
        await self._on_success(interaction, label)


async def ensure_auth(
    interaction: discord.Interaction,
    *,
    require_owner: bool = False,
    on_authed: Callable[[discord.Interaction, str], Awaitable[None]]
):
    """
    If user has a valid session -> call on_authed immediately.
    Else -> show modal, then call on_authed.
    """
    label = get_session_label(interaction.user.id)

    if label:
        if require_owner and label != "owner":
            return await interaction.response.send_message("❌ Owner only.", ephemeral=True)
        return await on_authed(interaction, label)

    async def after_modal(modal_interaction: discord.Interaction, modal_label: str):
        if require_owner and modal_label != "owner":
            return await modal_interaction.followup.send("❌ Owner only.", ephemeral=True)
        await on_authed(modal_interaction, modal_label)

    # Must respond fast -> modal is the response
    await interaction.response.send_modal(NexusAuthModal(after_modal))
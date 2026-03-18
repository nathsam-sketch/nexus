# nexus/discord_utils.py
import discord
from typing import List


async def send_embeds_visible(interaction: discord.Interaction, embeds: List[discord.Embed]) -> None:
    """
    Sends embeds to the same place the slash command was used, visible to everyone.
    Works in servers, DMs, and group chats by using the interaction webhook.
    """
    if not embeds:
        # always send something to avoid "interaction failed"
        if not interaction.response.is_done():
            await interaction.response.send_message("—", ephemeral=False)
        else:
            await interaction.followup.send("—", ephemeral=False)
        return

    # If we haven't responded yet, send the first embed as the initial response (public).
    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embeds[0], ephemeral=False)
        rest = embeds[1:]
    else:
        rest = embeds

    # Send the remaining embeds as public followups
    for e in rest:
        await interaction.followup.send(embed=e, ephemeral=False)


async def send_embeds_dm(user: discord.abc.User, embeds: List[discord.Embed]) -> None:
    """
    Sends embeds to the user's DM (private copy).
    """
    for e in embeds:
        await user.send(embed=e)
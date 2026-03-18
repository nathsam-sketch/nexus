import discord
from discord.ext import commands

from nexus.config import settings
from utils.roblox import RobloxAPI
from cogs.osint import OsintCog

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

rblx = RobloxAPI()


@bot.event
async def setup_hook():
    await rblx.start()
    await bot.add_cog(OsintCog(bot, rblx))


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")

    try:
        synced = await bot.tree.sync()
        print(f"[SYNC] Global sync OK: {len(synced)} commands")
    except Exception as e:
        print(f"[SYNC] FAILED: {e}")


bot.run(settings.token)
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    token: str
    guild_id: int
    master_secret: str
    color: int = 0x0B1020

def _req(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing {name} in .env")
    return v

settings = Settings(
    token=_req("DISCORD_TOKEN"),
    guild_id=int(_req("GUILD_ID")),
    master_secret=_req("NEXUS_MASTER_SECRET"),
)
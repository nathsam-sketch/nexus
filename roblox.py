# utils/roblox.py
import aiohttp
from typing import Any, Dict, List, Optional


class RobloxAPI:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=25)
            headers = {"User-Agent": "NexusOSINT/1.0 (discord bot)"}
            self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def _get_json(self, url: str) -> Dict[str, Any]:
        assert self.session is not None
        async with self.session.get(url) as resp:
            ct = resp.headers.get("Content-Type", "")
            if "application/json" not in ct:
                text = await resp.text()
                raise RuntimeError(f"Non-JSON response ({resp.status}) from {url}: {text[:200]}")
            return await resp.json()

    async def _post_json(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        assert self.session is not None
        async with self.session.post(url, json=payload) as resp:
            ct = resp.headers.get("Content-Type", "")
            if "application/json" not in ct:
                text = await resp.text()
                raise RuntimeError(f"Non-JSON response ({resp.status}) from {url}: {text[:200]}")
            return await resp.json()

    # ---------- Users ----------
    async def username_to_id(self, username: str) -> Optional[int]:
        data = await self._post_json(
            "https://users.roblox.com/v1/usernames/users",
            {"usernames": [username], "excludeBannedUsers": False},
        )
        if not data.get("data"):
            return None
        return int(data["data"][0]["id"])

    async def get_profile(self, user_id: int) -> Dict[str, Any]:
        return await self._get_json(f"https://users.roblox.com/v1/users/{user_id}")

    # ---------- Presence ----------
    async def get_presence(self, user_id: int) -> Dict[str, Any]:
        data = await self._post_json(
            "https://presence.roblox.com/v1/presence/users",
            {"userIds": [user_id]},
        )
        pres = (data.get("userPresences") or [])
        return pres[0] if pres else {}

    # ---------- Social ----------
    async def get_friends_count(self, user_id: int) -> int:
        data = await self._get_json(f"https://friends.roblox.com/v1/users/{user_id}/friends/count")
        return int(data.get("count", 0))

    async def get_followers_count(self, user_id: int) -> int:
        data = await self._get_json(f"https://friends.roblox.com/v1/users/{user_id}/followers/count")
        return int(data.get("count", 0))

    async def get_followings_count(self, user_id: int) -> int:
        data = await self._get_json(f"https://friends.roblox.com/v1/users/{user_id}/followings/count")
        return int(data.get("count", 0))

    async def get_friends_sample(self, user_id: int, limit: int = 200) -> List[int]:
        out: List[int] = []
        cursor = ""
        while len(out) < limit:
            page_limit = min(100, limit - len(out))
            url = f"https://friends.roblox.com/v1/users/{user_id}/friends?limit={page_limit}"
            if cursor:
                url += f"&cursor={cursor}"
            data = await self._get_json(url)
            for item in data.get("data", []):
                fid = item.get("id")
                if isinstance(fid, int):
                    out.append(fid)
            cursor = data.get("nextPageCursor") or ""
            if not cursor:
                break
        return out

    # ---------- Groups ----------
    async def get_groups(self, user_id: int) -> List[Dict[str, Any]]:
        data = await self._get_json(f"https://groups.roblox.com/v2/users/{user_id}/groups/roles")
        return data.get("data", [])

    async def get_group_details(self, group_id: int) -> Dict[str, Any]:
        return await self._get_json(f"https://groups.roblox.com/v1/groups/{group_id}")

    # ---------- Badges ----------
    async def get_recent_badges(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        url = f"https://badges.roblox.com/v1/users/{user_id}/badges?limit={limit}&sortOrder=Desc"
        data = await self._get_json(url)
        return data.get("data", [])

    async def get_badges_sample(self, user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        url = f"https://badges.roblox.com/v1/users/{user_id}/badges?limit={min(limit,100)}&sortOrder=Desc"
        data = await self._get_json(url)
        return data.get("data", [])

    # ---------- Avatar ----------
    async def get_headshot(self, user_id: int, size: str = "150x150") -> Optional[str]:
        data = await self._get_json(
            "https://thumbnails.roblox.com/v1/users/avatar-headshot"
            f"?userIds={user_id}&size={size}&format=Png&isCircular=false"
        )
        items = data.get("data", [])
        if not items:
            return None
        return items[0].get("imageUrl")

    async def get_currently_wearing(self, user_id: int) -> List[int]:
        data = await self._get_json(f"https://avatar.roblox.com/v1/users/{user_id}/currently-wearing")
        assets = data.get("assetIds", [])
        return [int(x) for x in assets if isinstance(x, int)]

    async def get_avatar_details(self, user_id: int) -> Dict[str, Any]:
        return await self._get_json(f"https://avatar.roblox.com/v1/users/{user_id}/avatar")

    # ---------- Games ----------
    async def get_public_games_sample(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        url = f"https://games.roblox.com/v2/users/{user_id}/games?accessFilter=2&limit={limit}&sortOrder=Desc"
        data = await self._get_json(url)
        return data.get("data", [])

    async def get_universe_details(self, universe_ids: List[int]) -> List[Dict[str, Any]]:
        if not universe_ids:
            return []
        ids = ",".join(str(int(x)) for x in universe_ids[:50])
        data = await self._get_json(f"https://games.roblox.com/v1/games?universeIds={ids}")
        return data.get("data", [])
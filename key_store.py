import os, json, hmac, hashlib, time
from typing import Dict, Any, Optional

KEYS_PATH = os.path.join("data", "keys.json")
SESS_PATH = os.path.join("data", "sessions.json")


def _ensure_files():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(KEYS_PATH):
        with open(KEYS_PATH, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "keys": {}}, f, indent=2)
    if not os.path.exists(SESS_PATH):
        with open(SESS_PATH, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "sessions": {}}, f, indent=2)


def _read_json(path: str) -> Dict[str, Any]:
    _ensure_files()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _write_json(path: str, data: Dict[str, Any]) -> None:
    _ensure_files()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def hash_key(raw_key: str, master_secret: str) -> str:
    """
    HMAC-SHA256(master_secret, raw_key)
    """
    raw_key = (raw_key or "").strip().encode("utf-8")
    secret = (master_secret or "").strip().encode("utf-8")
    return hmac.new(secret, raw_key, hashlib.sha256).hexdigest()


def load_keys() -> Dict[str, Dict[str, Any]]:
    data = _read_json(KEYS_PATH)
    keys = data.get("keys", {})
    return keys if isinstance(keys, dict) else {}


def save_keys(keys: Dict[str, Dict[str, Any]]) -> None:
    data = {"version": 1, "keys": keys}
    _write_json(KEYS_PATH, data)


def set_key(label: str, raw_key: str, master_secret: str, perms: Optional[list] = None) -> None:
    label = (label or "").strip()
    if not label:
        raise ValueError("label required")

    keys = load_keys()
    keys[label] = {
        "hash": hash_key(raw_key, master_secret),
        "perms": perms or []
    }
    save_keys(keys)


def remove_key(label: str) -> None:
    label = (label or "").strip()
    keys = load_keys()
    keys.pop(label, None)
    save_keys(keys)


def verify_key(raw_key: str, master_secret: str) -> Optional[str]:
    """
    Returns label if key matches, else None.
    """
    keys = load_keys()
    hk = hash_key(raw_key, master_secret)
    for label, info in keys.items():
        if isinstance(info, dict) and info.get("hash") == hk:
            return label
    return None


# -------------------------
# Sessions (persisted)
# -------------------------
def load_sessions() -> Dict[str, Dict[str, Any]]:
    data = _read_json(SESS_PATH)
    sess = data.get("sessions", {})
    return sess if isinstance(sess, dict) else {}


def save_sessions(sessions: Dict[str, Dict[str, Any]]) -> None:
    data = {"version": 1, "sessions": sessions}
    _write_json(SESS_PATH, data)


def set_session(user_id: int, label: str, ttl_seconds: int = 60 * 60 * 6) -> None:
    sessions = load_sessions()
    sessions[str(user_id)] = {
        "label": label,
        "expires": int(time.time()) + int(ttl_seconds)
    }
    save_sessions(sessions)


def get_session_label(user_id: int) -> Optional[str]:
    sessions = load_sessions()
    s = sessions.get(str(user_id))
    if not isinstance(s, dict):
        return None
    exp = int(s.get("expires", 0) or 0)
    if exp and time.time() > exp:
        # expired -> delete
        sessions.pop(str(user_id), None)
        save_sessions(sessions)
        return None
    return s.get("label")


def clear_session(user_id: int) -> None:
    sessions = load_sessions()
    sessions.pop(str(user_id), None)
    save_sessions(sessions)
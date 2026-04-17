from __future__ import annotations

import time
from typing import Any

import requests
from rosu_pp_py import Beatmap, Performance


class OsuApi:
    def __init__(self, client_id: int, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self._expires_at: float = 0

    def _token_value(self) -> str:
        now = time.time()
        if self._token and now < self._expires_at - 60:
            return self._token
        resp = requests.post(
            "https://osu.ppy.sh/oauth/token",
            json={
                "client_id":     self.client_id,
                "client_secret": self.client_secret,
                "grant_type":    "client_credentials",
                "scope":         "public",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._expires_at = now + data.get("expires_in", 86400)
        return self._token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token_value()}", "Accept": "application/json"}

    def fetch_user_by_id(self, user_id: int, ruleset: str) -> dict[str, Any]:
        resp = requests.get(
            f"https://osu.ppy.sh/api/v2/users/{user_id}/{ruleset}",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def fetch_user_by_username(self, username: str, ruleset: str) -> dict[str, Any]:
        slug = username.strip().lstrip("@")
        resp = requests.get(
            f"https://osu.ppy.sh/api/v2/users/@{slug}/{ruleset}",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def fetch_recent_scores(self, user_id: int, ruleset: str, limit: int) -> list[dict[str, Any]]:
        resp = requests.get(
            f"https://osu.ppy.sh/api/v2/users/{user_id}/scores/recent",
            params={"mode": ruleset, "limit": max(1, min(limit, 50))},
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("scores"), list):
            return data["scores"]
        return []

    def fetch_beatmap(self, beatmap_id: int) -> dict[str, Any] | None:
        resp = requests.get(
            f"https://osu.ppy.sh/api/v2/beatmaps/{beatmap_id}",
            headers=self._headers(),
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        return resp.json()

    _MOD_BITS: dict[str, int] = {
        "NF": 1, "EZ": 2, "HD": 8, "HR": 16, "SD": 32,
        "DT": 64, "RX": 128, "HT": 256, "NC": 576, "FL": 1024,
        "SO": 4096, "AP": 8192, "PF": 16384,
    }

    def fetch_beatmap_max_pp(self, beatmap_id: int, ruleset: str, mods: list[str] | None = None) -> float | None:
        try:
            resp = requests.get(f"https://osu.ppy.sh/osu/{beatmap_id}", timeout=15)
            if resp.status_code != 200:
                return None

            mode_map = {"osu": 0, "taiko": 1, "fruits": 2, "mania": 3}
            mode = mode_map.get(ruleset, 0)

            beatmap = Beatmap(content=resp.content)
            beatmap.convert(mode)

            mods_int = 0
            if mods:
                for m in mods:
                    mods_int |= self._MOD_BITS.get(m.upper(), 0)

            result = Performance(accuracy=100.0, mods=mods_int).calculate(beatmap)
            return result.pp
        except Exception:
            return None
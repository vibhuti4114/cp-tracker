"""
Platform-specific data fetchers.

Each fetcher implements:
    fetch_user_info(handle)  → dict
    fetch_submissions(handle, count) → list[dict]
    fetch_rating_history(handle) → list[dict]

All fetchers are async and use httpx for HTTP calls.
Network errors are caught and re-raised as PlatformFetchError.
"""

import hashlib
import hmac
import logging
import random
import string
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class PlatformFetchError(Exception):
    """Raised when an external platform API call fails."""


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class BaseFetcher(ABC):
    platform: str

    @abstractmethod
    async def fetch_user_info(self, handle: str) -> dict:
        ...

    @abstractmethod
    async def fetch_submissions(self, handle: str, count: int = 500) -> list[dict]:
        ...

    @abstractmethod
    async def fetch_rating_history(self, handle: str) -> list[dict]:
        ...

    async def _get(self, url: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                r = await client.get(url, params=params)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as e:
                raise PlatformFetchError(f"HTTP {e.response.status_code} from {url}") from e
            except httpx.RequestError as e:
                raise PlatformFetchError(f"Network error reaching {url}: {e}") from e


# ---------------------------------------------------------------------------
# Codeforces
# ---------------------------------------------------------------------------

class CodeforcesFetcher(BaseFetcher):
    platform = "codeforces"
    BASE = "https://codeforces.com/api"

    def _sign(self, method: str, params: dict) -> dict:
        """Add HMAC-SHA512 signature if API key is configured."""
        if not settings.CODEFORCES_API_KEY:
            return params
        params["apiKey"] = settings.CODEFORCES_API_KEY
        params["time"] = int(time.time())
        rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        to_hash = f"{rand}/{method}?{sorted_params}#{settings.CODEFORCES_API_SECRET}"
        params["apiSig"] = rand + hmac.new(
            settings.CODEFORCES_API_SECRET.encode(),
            to_hash.encode(),
            hashlib.sha512,
        ).hexdigest()
        return params

    async def fetch_user_info(self, handle: str) -> dict:
        data = await self._get(f"{self.BASE}/user.info", {"handles": handle})
        if data.get("status") != "OK":
            raise PlatformFetchError(f"Codeforces: {data.get('comment', 'unknown error')}")
        u = data["result"][0]
        return {
            "handle": u["handle"],
            "current_rating": u.get("rating"),
            "max_rating": u.get("maxRating"),
            "rank": u.get("rank"),
            "avatar": u.get("titlePhoto"),
        }

    async def fetch_submissions(self, handle: str, count: int = 500) -> list[dict]:
        data = await self._get(
            f"{self.BASE}/user.status", {"handle": handle, "from": 1, "count": count}
        )
        if data.get("status") != "OK":
            raise PlatformFetchError(f"Codeforces: {data.get('comment')}")
        submissions = []
        seen = set()
        for s in data["result"]:
            prob = s.get("problem", {})
            sid = str(s["id"])
            problem_id = f"{prob.get('contestId', '')}{prob.get('index', '')}"
            verdict = s.get("verdict", "UNKNOWN")
            submissions.append({
                "platform_submission_id": sid,
                "problem_id": problem_id,
                "problem_name": prob.get("name", ""),
                "problem_url": f"https://codeforces.com/problemset/problem/{prob.get('contestId')}/{prob.get('index')}",
                "verdict": verdict,
                "language": s.get("programmingLanguage"),
                "tags": prob.get("tags", []),
                "submitted_at": datetime.fromtimestamp(s["creationTimeSeconds"], tz=timezone.utc),
            })
        return submissions

    async def fetch_rating_history(self, handle: str) -> list[dict]:
        data = await self._get(f"{self.BASE}/user.rating", {"handle": handle})
        if data.get("status") != "OK":
            raise PlatformFetchError(f"Codeforces: {data.get('comment')}")
        history = []
        for r in data["result"]:
            history.append({
                "contest_name": r.get("contestName"),
                "contest_id": str(r.get("contestId")),
                "old_rating": r["oldRating"],
                "new_rating": r["newRating"],
                "rank":         str(r.get("rank")) if r.get("rank") is not None else None,
                "participated_at": datetime.fromtimestamp(r["ratingUpdateTimeSeconds"], tz=timezone.utc),
            })
        return history


# ---------------------------------------------------------------------------
# LeetCode
# ---------------------------------------------------------------------------

class LeetCodeFetcher(BaseFetcher):
    platform = "leetcode"
    GRAPHQL = "https://leetcode.com/graphql"

    async def _gql(self, query: str, variables: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                r = await client.post(
                    self.GRAPHQL,
                    json={"query": query, "variables": variables or {}},
                    headers={"Content-Type": "application/json", "Referer": "https://leetcode.com"},
                )
                r.raise_for_status()
                return r.json()
            except httpx.HTTPStatusError as e:
                raise PlatformFetchError(f"LeetCode HTTP {e.response.status_code}") from e
            except httpx.RequestError as e:
                raise PlatformFetchError(f"LeetCode network error: {e}") from e

    async def fetch_user_info(self, handle: str) -> dict:
        q = """
        query($username: String!) {
          matchedUser(username: $username) {
            username
            submitStats: submitStatsGlobal {
              acSubmissionNum { difficulty count submissions }
            }
            profile { ranking userAvatar }
          }
          userContestRanking(username: $username) {
            rating
            topPercentage
            attendedContestsCount
          }
        }
        """
        data = await self._gql(q, {"username": handle})
        u = data.get("data", {}).get("matchedUser")
        r = data.get("data", {}).get("userContestRanking")
        if not u:
            raise PlatformFetchError(f"LeetCode user '{handle}' not found.")

        ac_counts = {
            s["difficulty"]: s["count"]
            for s in u["submitStats"]["acSubmissionNum"]
        }
        
        # LeetCode doesn't explicitly return "max rating" in this query,
        # but we can at least get current rating. Max rating will be updated
        # during rating history sync.
        current_rating = r.get("rating") if r else None
        
        return {
            "handle": u["username"],
            "problems_solved": ac_counts.get("All", 0),
            "easy_solved": ac_counts.get("Easy", 0),
            "medium_solved": ac_counts.get("Medium", 0),
            "hard_solved": ac_counts.get("Hard", 0),
            "ranking": u["profile"]["ranking"],
            "current_rating": current_rating,
            "max_rating": current_rating, # Initialize with current
        }

    async def fetch_submissions(self, handle: str, count: int = 20) -> list[dict]:
        q = """
        query($username: String!, $limit: Int!) {
          recentAcSubmissionList(username: $username, limit: $limit) {
            id title titleSlug timestamp lang
          }
        }
        """
        data = await self._gql(q, {"username": handle, "limit": min(count, 20)})
        raw = data.get("data", {}).get("recentAcSubmissionList", [])
        return [
            {
                "platform_submission_id": s["id"],
                "problem_id": s["titleSlug"],
                "problem_name": s["title"],
                "problem_url": f"https://leetcode.com/problems/{s['titleSlug']}/",
                "verdict": "AC",
                "language": s.get("lang"),
                "tags": [],
                "submitted_at": datetime.fromtimestamp(int(s["timestamp"]), tz=timezone.utc),
            }
            for s in raw
        ]

    async def fetch_rating_history(self, handle: str) -> list[dict]:
        q = """
        query($username: String!) {
          userContestRankingHistory(username: $username) {
            attended contest { title startTime }
            rating ranking
          }
        }
        """
        data = await self._gql(q, {"username": handle})
        history = []
        prev_rating = 1500.0
        for entry in data.get("data", {}).get("userContestRankingHistory", []):
            if not entry.get("attended"):
                continue
            new_rating = entry["rating"]
            history.append({
                "contest_name": entry["contest"]["title"],
                "contest_id": None,
                "old_rating": prev_rating,
                "new_rating": new_rating,
                "rank": str(entry.get("ranking")) if entry.get("ranking") is not None else None,
                "participated_at": datetime.fromtimestamp(
                    entry["contest"]["startTime"], tz=timezone.utc
                ),
            })
            prev_rating = new_rating
        return history


# ---------------------------------------------------------------------------
# CodeChef  (scrapes codechef.com directly — no third-party API needed)
# ---------------------------------------------------------------------------

import re as _re
import json as _json

class CodeChefFetcher(BaseFetcher):
    platform = "codechef"
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    async def _fetch_profile_html(self, handle: str) -> str:
        """Fetch the raw HTML of codechef.com/users/{handle}."""
        url = f"https://www.codechef.com/users/{handle}"
        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=True,
            headers=self._HEADERS,
        ) as client:
            try:
                r = await client.get(url)
            except httpx.RequestError as exc:
                raise PlatformFetchError(f"CodeChef: network error — {exc}") from exc

        if r.status_code == 404:
            raise PlatformFetchError(f"CodeChef: user '{handle}' not found.")
        if r.status_code != 200:
            raise PlatformFetchError(f"CodeChef: HTTP {r.status_code} fetching profile.")

        html = r.text
        if "User Not Found" in html or "user not found" in html.lower():
            raise PlatformFetchError(f"CodeChef: user '{handle}' not found.")
        return html

    def _extract_json_blob(self, html: str) -> dict:
        """
        CodeChef embeds user data as JSON in script tags.
        Try multiple patterns to handle different page versions.
        """
        # Pattern 1: __NEXT_DATA__ (Next.js)
        m = _re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(\{.*?\})</script>', html, _re.DOTALL)
        if m:
            try:
                return _json.loads(m.group(1))
            except _json.JSONDecodeError:
                pass

        # Pattern 2: window.__INITIAL_STATE__ or similar
        for pat in [
            r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*</script>',
            r'window\.__data\s*=\s*(\{.*?\});\s*</script>',
        ]:
            m = _re.search(pat, html, _re.DOTALL)
            if m:
                try:
                    return _json.loads(m.group(1))
                except _json.JSONDecodeError:
                    pass
        return {}

    def _pluck(self, obj: dict | list, *keys):
        """Safely traverse nested dicts/lists."""
        cur = obj
        for k in keys:
            if isinstance(cur, dict):
                cur = cur.get(k)
            elif isinstance(cur, list) and isinstance(k, int):
                cur = cur[k] if len(cur) > k else None
            else:
                return None
            if cur is None:
                return None
        return cur

    def _parse_data(self, html: str, handle: str) -> dict:
        """
        Extract rating + contest history from the page.
        Returns a dict with keys:
          handle, current_rating, max_rating, problems_solved,
          contests_participated, ratingData
        """
        result: dict = {
            "handle": handle,
            "current_rating": None,
            "max_rating": None,
            "problems_solved": 0,
            "contests_participated": 0,
            "ratingData": [],
        }

        blob = self._extract_json_blob(html)

        # ── Try to find data inside Next.js pageProps ──────────────────────
        page_props = self._pluck(blob, "props", "pageProps") or {}

        # userDetails may live at different paths depending on the page version
        user_details: dict = (
            page_props.get("userDetails")
            or page_props.get("userData")
            or page_props.get("profile")
            or {}
        )

        rating_data: list = (
            page_props.get("ratingData")
            or user_details.get("ratingData")
            or page_props.get("contest_rating_data")
            or page_props.get("all_rating")
            or []
        )

        if user_details or rating_data:
            result["handle"] = user_details.get("username", handle)
            result["current_rating"] = (
                user_details.get("currentRating")
                or user_details.get("current_rating")
                or (int(rating_data[-1].get("rating")) if rating_data and rating_data[-1].get("rating") else None)
            )
            result["max_rating"] = (
                user_details.get("highestRating")
                or user_details.get("highest_rating")
                or (max((int(r.get("rating", 0)) for r in rating_data if r.get("rating")), default=None) if rating_data else None)
            )
            result["problems_solved"] = user_details.get("totalProblems", 0)
            result["contests_participated"] = len(rating_data)
            result["ratingData"] = rating_data

        # ── Fallback: inline regex on raw HTML ────────────────────────────
        if result["current_rating"] is None:
            m = _re.search(r'"currentRating"\s*:\s*"?(\d+)"?', html)
            if m:
                result["current_rating"] = int(m.group(1))

        if result["max_rating"] is None:
            # CodeChef sidebar often has "(Highest Rating 1819)"
            m = _re.search(r'Highest Rating\s*(\d+)', html, _re.IGNORECASE)
            if m:
                result["max_rating"] = int(m.group(1))
            else:
                m = _re.search(r'"highestRating"\s*:\s*"?(\d+)"?', html)
                if m:
                    result["max_rating"] = int(m.group(1))

        # ratingData as inline JSON array (all_rating or ratingData)
        if not result["ratingData"]:
            # Try var all_rating = [...] or "all_rating":[...] or "ratingData":[...]
            m = _re.search(r'(?:all_rating|ratingData)\s*[:=]\s*(\[.*?\]);?\s*(?:</script>|\n)', html, _re.DOTALL)
            if not m:
                # Last resort: just find the first bracketed array after the key
                m = _re.search(r'(?:all_rating|ratingData)\s*[:=]\s*(\[.*?\])', html, _re.DOTALL)
            
            if m:
                try:
                    rd = _json.loads(m.group(1))
                    result["ratingData"] = rd
                    result["contests_participated"] = len(rd)
                    if rd:
                        ratings = [int(r.get("rating", 0)) for r in rd if r.get("rating")]
                        if ratings:
                            result["current_rating"] = result["current_rating"] or ratings[-1]
                            result["max_rating"] = result["max_rating"] or max(ratings)
                except (_json.JSONDecodeError, ValueError):
                    pass

        # last-resort stats: grab from visible text if still 0
        if result["problems_solved"] == 0:
            # Look for "Problems Solved: 257" or similar
            m = _re.search(r'Problems Solved:\s*(\d+)', html, _re.IGNORECASE)
            if m:
                result["problems_solved"] = int(m.group(1))
            else:
                # Often in Sidebar as "Solved Problems (257)"
                m = _re.search(r'Solved Problems\s*\((\d+)\)', html, _re.IGNORECASE)
                if m:
                    result["problems_solved"] = int(m.group(1))

        if result["contests_participated"] == 0 and result["ratingData"]:
            result["contests_participated"] = len(result["ratingData"])

        return result

    # ── Public interface ───────────────────────────────────────────────────

    async def fetch_user_info(self, handle: str) -> dict:
        html = await self._fetch_profile_html(handle)
        data = self._parse_data(html, handle)

        # If we still have no rating at all the page probably redirected to
        # a "not found" page without a 404 status — treat as not found.
        if data["current_rating"] is None and not data["ratingData"]:
            # Allow adding anyway — they may just have no rating yet
            logger.warning("CodeChef: no rating data found for '%s'; allowing add.", handle)

        return {
            "handle": data["handle"],
            "current_rating": data["current_rating"],
            "max_rating": data["max_rating"],
            "problems_solved": data["problems_solved"],
            "contests_participated": data["contests_participated"],
        }

    async def fetch_submissions(self, handle: str, count: int = 500) -> list[dict]:
        return []   # CodeChef doesn't expose submissions via a public API

    async def fetch_rating_history(self, handle: str) -> list[dict]:
        try:
            html = await self._fetch_profile_html(handle)
        except PlatformFetchError:
            return []

        data = self._parse_data(html, handle)
        rating_data = data["ratingData"]
        history = []

        for i, r in enumerate(rating_data):
            end_date = r.get("end_date") or r.get("endDate") or r.get("end_time")
            try:
                if end_date:
                    # Accept both "YYYY-MM-DD HH:MM:SS" and "YYYY-MM-DD"
                    fmt = "%Y-%m-%d %H:%M:%S" if " " in end_date else "%Y-%m-%d"
                    participated = datetime.strptime(end_date, fmt).replace(tzinfo=timezone.utc)
                else:
                    participated = datetime.now(timezone.utc)
            except ValueError:
                participated = datetime.now(timezone.utc)

            prev_rating = int(rating_data[i - 1].get("rating", 1500)) if i > 0 else 1500
            history.append({
                "contest_name": r.get("name") or r.get("contest_name") or r.get("title"),
                "contest_id":   r.get("code") or r.get("contest_code") or r.get("contest_id"),
                "old_rating":   prev_rating,
                "new_rating":   int(r.get("rating", 1500)),
                "rank":         str(r.get("rank")) if r.get("rank") is not None else None,
                "participated_at": participated,
            })
        return history


# ---------------------------------------------------------------------------
# AtCoder
# ---------------------------------------------------------------------------

class AtCoderFetcher(BaseFetcher):
    platform = "atcoder"
    BASE = "https://atcoder.jp"
    ATCODER_API = "https://atcoder-api.vercel.app"

    async def fetch_user_info(self, handle: str) -> dict:
        url = f"https://atcoder.jp/users/{handle}/history/json"
        try:
            data = await self._get(url)
        except PlatformFetchError:
            raise PlatformFetchError(f"AtCoder: user '{handle}' not found or API unavailable.")

        if not data:
            return {"handle": handle, "current_rating": None, "max_rating": None}

        latest = data[-1]
        max_rating = max(d["NewRating"] for d in data)
        return {
            "handle": handle,
            "current_rating": latest["NewRating"],
            "max_rating": max_rating,
            "contests_participated": len(data),
        }

    async def fetch_submissions(self, handle: str, count: int = 500) -> list[dict]:
        url = f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions"
        try:
            data = await self._get(url, params={"user": handle, "from_second": 0})
        except PlatformFetchError:
            return []

        submissions = []
        for s in data[:count]:
            submissions.append({
                "platform_submission_id": str(s["id"]),
                "problem_id": s["problem_id"],
                "problem_name": s["problem_id"],
                "problem_url": f"https://atcoder.jp/contests/{s['contest_id']}/tasks/{s['problem_id']}",
                "verdict": s["result"],
                "language": s.get("language"),
                "tags": [],
                "submitted_at": datetime.fromtimestamp(s["epoch_second"], tz=timezone.utc),
            })
        return submissions

    async def fetch_rating_history(self, handle: str) -> list[dict]:
        url = f"https://atcoder.jp/users/{handle}/history/json"
        try:
            data = await self._get(url)
        except PlatformFetchError:
            return []

        history = []
        for r in data:
            history.append({
                "contest_name": r.get("ContestScreenName"),
                "contest_id": r.get("ContestScreenName"),
                "old_rating": r["OldRating"],
                "new_rating": r["NewRating"],
                "rank": str(r.get("Place")) if r.get("Place") is not None else None,
                "participated_at": datetime.fromisoformat(r["EndTime"].replace("Z", "+00:00")),
            })
        return history


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

FETCHERS: dict[str, BaseFetcher] = {
    "codeforces": CodeforcesFetcher(),
    "leetcode":   LeetCodeFetcher(),
    "codechef":   CodeChefFetcher(),
    "atcoder":    AtCoderFetcher(),
}


def get_fetcher(platform: str) -> BaseFetcher:
    fetcher = FETCHERS.get(platform.lower())
    if not fetcher:
        raise ValueError(f"Unsupported platform: '{platform}'")
    return fetcher

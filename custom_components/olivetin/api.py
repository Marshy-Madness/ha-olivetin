"""Minimal client for the OliveTin 2.x REST API (grpc-gateway under /api/)."""

from __future__ import annotations

from typing import Any

import aiohttp


class OliveTinApiError(Exception):
    """OliveTin answered, but reported a failure or sent something unexpected."""


class OliveTinConnectionError(OliveTinApiError):
    """OliveTin could not be reached."""


class OliveTinAuthError(OliveTinApiError):
    """Login failed, or OliveTin refused access without one."""


class OliveTinApiClient:
    """Talks to OliveTin over HTTP."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._session = session
        self._base = url.rstrip("/") + "/api"
        self._username = username
        self._password = password
        # HA's shared session doesn't keep cookies, so the login cookie is held here.
        self._cookies: dict[str, str] = {}

    async def login(self) -> None:
        """POST /api/LocalUserLogin; stores the olivetin-sid-local session cookie."""
        self._cookies = {}
        data, resp_cookies = await self._send(
            "POST",
            "LocalUserLogin",
            {"username": self._username, "password": self._password},
        )
        if not data.get("success") or not resp_cookies:
            raise OliveTinAuthError("OliveTin rejected the username or password")
        self._cookies = resp_cookies

    async def _request(
        self, method: str, endpoint: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if self._username and not self._cookies:
            await self.login()
        try:
            data, _ = await self._send(method, endpoint, payload)
        except OliveTinAuthError:
            if not self._username:
                raise
            # Session expired or OliveTin restarted; log in again once.
            await self.login()
            data, _ = await self._send(method, endpoint, payload)
        return data

    async def _send(
        self, method: str, endpoint: str, payload: dict[str, Any] | None
    ) -> tuple[dict[str, Any], dict[str, str]]:
        url = f"{self._base}/{endpoint}"
        try:
            async with self._session.request(
                method,
                url,
                json=payload,
                cookies=self._cookies,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json(content_type=None)
                status = resp.status
                resp_cookies = {name: c.value for name, c in resp.cookies.items()}
        except (aiohttp.ClientError, OSError, TimeoutError) as err:
            raise OliveTinConnectionError(f"Cannot reach OliveTin at {url}: {err}") from err
        except ValueError as err:
            raise OliveTinApiError(f"Invalid JSON from {endpoint}") from err

        if not isinstance(data, dict):
            raise OliveTinApiError(f"Unexpected response from {endpoint}")
        if status in (401, 403):
            raise OliveTinAuthError(data.get("message") or f"HTTP {status} from {endpoint}")
        if status >= 400:
            raise OliveTinApiError(data.get("message") or f"HTTP {status} from {endpoint}")
        return data, resp_cookies

    async def get_actions(self) -> list[dict[str, Any]]:
        """GET /api/GetDashboardComponents; every action the current user can see."""
        data = await self._request("GET", "GetDashboardComponents")
        if "actions" not in data:
            raise OliveTinApiError("GetDashboardComponents has no actions list")
        return data["actions"] or []

    async def start_action(
        self, action_id: str, arguments: dict[str, Any] | None = None
    ) -> str | None:
        """POST /api/StartAction; returns the execution tracking id."""
        payload = {
            "actionId": action_id,
            "arguments": [
                {"name": name, "value": str(value)}
                for name, value in (arguments or {}).items()
            ],
            "uniqueTrackingId": "",
        }
        data = await self._request("POST", "StartAction", payload)
        return data.get("executionTrackingId")

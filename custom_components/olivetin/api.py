"""Minimal client for the OliveTin 3000 API (Connect RPC, JSON over POST under /api/)."""

from __future__ import annotations

from typing import Any

import aiohttp


class OliveTinApiError(Exception):
    """OliveTin answered, but reported a failure or sent something unexpected."""


class OliveTinConnectionError(OliveTinApiError):
    """OliveTin could not be reached."""


class OliveTinAuthError(OliveTinApiError):
    """Login failed, or OliveTin refused access without one."""


# Connect error codes that mean "log in (again)".
AUTH_ERROR_CODES = {"unauthenticated", "permission_denied"}


def _collect_actions(
    components: list[dict[str, Any]] | None, found: dict[str, dict[str, Any]]
) -> None:
    """Walk a dashboard's (nested) components and gather every action."""
    for component in components or []:
        action = component.get("action")
        if action and action.get("bindingId"):
            found.setdefault(action["bindingId"], action)
        _collect_actions(component.get("contents"), found)


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
            "LocalUserLogin",
            {"username": self._username, "password": self._password},
        )
        if not data.get("success") or not resp_cookies:
            raise OliveTinAuthError("OliveTin rejected the username or password")
        self._cookies = resp_cookies

    async def _request(
        self, endpoint: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if self._username and not self._cookies:
            await self.login()
        try:
            data, _ = await self._send(endpoint, payload)
        except OliveTinAuthError:
            if not self._username:
                raise
            # Session expired or OliveTin restarted; log in again once.
            await self.login()
            data, _ = await self._send(endpoint, payload)
        return data

    async def _send(
        self, endpoint: str, payload: dict[str, Any] | None
    ) -> tuple[dict[str, Any], dict[str, str]]:
        url = f"{self._base}/{endpoint}"
        try:
            async with self._session.post(
                url,
                json=payload or {},
                cookies=self._cookies,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                status = resp.status
                resp_cookies = {name: c.value for name, c in resp.cookies.items()}
                try:
                    data = await resp.json(content_type=None)
                except ValueError as err:
                    raise OliveTinApiError(
                        f"Invalid JSON from {endpoint} (HTTP {status}); "
                        "is this OliveTin 3000 or newer?"
                    ) from err
        except (aiohttp.ClientError, OSError, TimeoutError) as err:
            raise OliveTinConnectionError(f"Cannot reach OliveTin at {url}: {err}") from err

        if not isinstance(data, dict):
            raise OliveTinApiError(f"Unexpected response from {endpoint}")
        if status in (401, 403) or data.get("code") in AUTH_ERROR_CODES:
            raise OliveTinAuthError(data.get("message") or f"HTTP {status} from {endpoint}")
        if status >= 400:
            raise OliveTinApiError(data.get("message") or f"HTTP {status} from {endpoint}")
        return data, resp_cookies

    async def get_actions(self) -> list[dict[str, Any]]:
        """Every action on the dashboards the current user can see.

        OliveTin 3000 has no flat action list; actions are found by walking each
        root dashboard from Init. The bindingId is exposed as "id" so callers can
        pass it straight back to start_action.
        """
        init = await self._request("Init")
        if "rootDashboards" not in init:
            raise OliveTinApiError("Init response has no rootDashboards")
        if init.get("loginRequired") and init.get("authenticatedUser") in (None, "", "guest"):
            raise OliveTinAuthError("OliveTin requires a login")

        found: dict[str, dict[str, Any]] = {}
        for title in init["rootDashboards"] or []:
            data = await self._request("GetDashboard", {"title": title})
            dashboard = data.get("dashboard")
            if dashboard is None:
                raise OliveTinApiError(f"GetDashboard {title!r} returned no dashboard")
            _collect_actions(dashboard.get("contents"), found)

        return [{**action, "id": binding_id} for binding_id, action in found.items()]

    async def start_action(
        self, action_id: str, arguments: dict[str, Any] | None = None
    ) -> str | None:
        """POST /api/StartAction; action_id is the bindingId. Returns the tracking id."""
        payload = {
            "bindingId": action_id,
            "arguments": [
                {"name": name, "value": str(value)}
                for name, value in (arguments or {}).items()
            ],
            "uniqueTrackingId": "",
        }
        data = await self._request("StartAction", payload)
        return data.get("executionTrackingId")

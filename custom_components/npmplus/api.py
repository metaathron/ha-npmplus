"""Lightweight async client for the NPMplus / Nginx Proxy Manager REST API.

Only the endpoints required by this integration are implemented. Field
names follow the upstream nginx-proxy-manager API (which NPMplus is a
drop-in compatible fork of). If a future NPMplus release renames a field,
only this file needs to be touched - all parsing happens here and the rest
of the integration works with the plain dictionaries returned below.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

API_TIMEOUT = 20
# Refresh the token a bit before it actually expires to avoid races.
TOKEN_REFRESH_MARGIN = timedelta(minutes=5)


class NPMplusApiError(Exception):
    """Generic API error."""


class NPMplusAuthError(NPMplusApiError):
    """Raised when authentication fails (bad credentials or expired token)."""


class NPMplusConnectionError(NPMplusApiError):
    """Raised when the host cannot be reached."""


@dataclass
class NPMplusToken:
    """Holds the current auth credential (bearer token and/or cookie) and its expiry."""

    value: str | None = None
    cookie_header: str | None = None
    expires_at: datetime | None = None

    @property
    def is_valid(self) -> bool:
        if not (self.value or self.cookie_header) or not self.expires_at:
            return False
        return datetime.now(timezone.utc) < (self.expires_at - TOKEN_REFRESH_MARGIN)


@dataclass
class NPMplusClient:
    """Thin async wrapper around the NPMplus REST API."""

    host: str
    port: int
    identity: str
    secret: str
    verify_ssl: bool
    session: aiohttp.ClientSession
    token: NPMplusToken = field(default_factory=NPMplusToken)

    @property
    def base_url(self) -> str:
        return f"https://{self.host}:{self.port}/api"

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    async def async_login(self) -> None:
        """Authenticate and store the credential (bearer token or auth cookie).

        NPMplus historically returned the JWT in the response body
        (`{"token": ..., "expires": ...}`), matching upstream nginx-proxy-manager.
        Newer NPMplus releases instead set it as a secure httponly cookie and
        only return `{"expires": ...}` in the body. Since the cookie is only
        httponly towards browser JS (not towards this server-side client), we
        read it from the response and forward it manually as a `Cookie`
        header on subsequent requests - both auth styles are supported.
        """
        url = f"{self.base_url}/tokens"
        payload = {"identity": self.identity, "secret": self.secret}
        data, cookie_header = await self._request_with_cookies(
            "POST", url, json=payload, authenticated=False, is_login_request=True
        )

        token_value = data.get("token")
        expires_raw = data.get("expires")

        if not token_value and not cookie_header:
            raise NPMplusAuthError(
                "Login response did not contain a token or auth cookie"
            )

        expires_at = _parse_datetime(expires_raw) or (
            datetime.now(timezone.utc) + timedelta(hours=1)
        )
        self.token = NPMplusToken(
            value=token_value, cookie_header=cookie_header, expires_at=expires_at
        )

    async def async_ensure_token(self) -> None:
        if not self.token.is_valid:
            await self.async_login()

    async def async_validate(self) -> None:
        """Used by the config flow to validate host/credentials."""
        await self.async_login()

    # ------------------------------------------------------------------
    # Read endpoints
    # ------------------------------------------------------------------
    async def async_get_proxy_hosts(self) -> list[dict[str, Any]]:
        return await self._authenticated_get("/nginx/proxy-hosts")

    async def async_get_streams(self) -> list[dict[str, Any]]:
        return await self._authenticated_get("/nginx/streams")

    async def async_get_certificates(self) -> list[dict[str, Any]]:
        return await self._authenticated_get("/nginx/certificates")

    async def async_get_dead_hosts(self) -> list[dict[str, Any]]:
        return await self._authenticated_get("/nginx/dead-hosts")

    async def async_get_redirection_hosts(self) -> list[dict[str, Any]]:
        return await self._authenticated_get("/nginx/redirection-hosts")

    # ------------------------------------------------------------------
    # Write endpoints
    # ------------------------------------------------------------------
    async def async_set_proxy_host_enabled(self, host_id: int, enabled: bool) -> None:
        action = "enable" if enabled else "disable"
        await self._authenticated_request(
            "POST", f"/nginx/proxy-hosts/{host_id}/{action}"
        )

    async def async_set_stream_enabled(self, stream_id: int, enabled: bool) -> None:
        action = "enable" if enabled else "disable"
        await self._authenticated_request(
            "POST", f"/nginx/streams/{stream_id}/{action}"
        )

    async def async_set_dead_host_enabled(self, host_id: int, enabled: bool) -> None:
        action = "enable" if enabled else "disable"
        await self._authenticated_request(
            "POST", f"/nginx/dead-hosts/{host_id}/{action}"
        )

    async def async_set_redirection_host_enabled(
        self, host_id: int, enabled: bool
    ) -> None:
        action = "enable" if enabled else "disable"
        await self._authenticated_request(
            "POST", f"/nginx/redirection-hosts/{host_id}/{action}"
        )

    async def async_renew_certificate(self, certificate_id: int) -> None:
        await self._authenticated_request(
            "POST", f"/nginx/certificates/{certificate_id}/renew"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _authenticated_get(self, path: str) -> list[dict[str, Any]]:
        result = await self._authenticated_request("GET", path)
        return result if isinstance(result, list) else []

    async def _authenticated_request(
        self, method: str, path: str, **kwargs: Any
    ) -> Any:
        await self.async_ensure_token()
        url = f"{self.base_url}{path}"
        try:
            return await self._request(method, url, authenticated=True, **kwargs)
        except NPMplusAuthError:
            # Token may have been revoked/expired server-side - retry once.
            await self.async_login()
            return await self._request(method, url, authenticated=True, **kwargs)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        authenticated: bool,
        json: dict[str, Any] | None = None,
        is_login_request: bool = False,
    ) -> Any:
        data, _cookie_header = await self._request_with_cookies(
            method,
            url,
            authenticated=authenticated,
            json=json,
            is_login_request=is_login_request,
        )
        return data

    async def _request_with_cookies(
        self,
        method: str,
        url: str,
        *,
        authenticated: bool,
        json: dict[str, Any] | None = None,
        is_login_request: bool = False,
    ) -> tuple[Any, str | None]:
        headers = {"Accept": "application/json"}
        if authenticated:
            if self.token.value:
                headers["Authorization"] = f"Bearer {self.token.value}"
            elif self.token.cookie_header:
                headers["Cookie"] = self.token.cookie_header
            else:
                raise NPMplusAuthError("No token or auth cookie available")

        try:
            async with asyncio.timeout(API_TIMEOUT):
                async with self.session.request(
                    method,
                    url,
                    json=json,
                    headers=headers,
                    ssl=self.verify_ssl,
                ) as resp:
                    if resp.status in (401, 403):
                        raise NPMplusAuthError(
                            f"Authentication failed ({resp.status})"
                        )
                    # NPM/NPMplus replies to a failed POST /api/tokens with
                    # HTTP 400 (not 401/403), e.g.:
                    # {"error": {"code": 400, "message": "Invalid email or password", ...}}
                    if is_login_request and resp.status == 400:
                        message = await _safe_error_message(resp)
                        raise NPMplusAuthError(message or "Invalid email or password")
                    if resp.status >= 400:
                        body = await resp.text()
                        raise NPMplusApiError(
                            f"Request to {url} failed: {resp.status} {body}"
                        )

                    cookie_header = _extract_cookie_header(resp)

                    if resp.content_type == "application/json":
                        return await resp.json(), cookie_header
                    return {}, cookie_header
        except (aiohttp.ClientConnectorError, aiohttp.ClientOSError) as err:
            raise NPMplusConnectionError(str(err)) from err
        except aiohttp.InvalidURL as err:
            raise NPMplusConnectionError(
                f"Invalid host/port configuration: {err}"
            ) from err
        except aiohttp.ClientError as err:
            raise NPMplusConnectionError(str(err)) from err
        except TimeoutError as err:
            raise NPMplusConnectionError("Timeout connecting to NPMplus") from err


def _extract_cookie_header(resp: aiohttp.ClientResponse) -> str | None:
    """Build a `Cookie:` header value from a response's Set-Cookie headers.

    aiohttp exposes cookies set on this specific response via `resp.cookies`
    (a http.cookies.SimpleCookie). This is used to forward NPMplus's
    httponly auth cookie manually, since it may be set for a bare IP host
    that a standard cookie jar would refuse to store per RFC 6265.
    """
    if not resp.cookies:
        return None
    return "; ".join(f"{name}={morsel.value}" for name, morsel in resp.cookies.items())


async def _safe_error_message(resp: aiohttp.ClientResponse) -> str | None:
    """Best-effort extraction of the NPM-style {"error": {"message": ...}} body."""
    try:
        data = await resp.json(content_type=None)
        return data.get("error", {}).get("message")
    except Exception:  # noqa: BLE001
        return None


def _parse_datetime(value: Any) -> datetime | None:
    """Parse a datetime coming from the API (ISO-8601 or epoch seconds)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None

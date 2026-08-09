"""Issue short-lived TURN REST credentials for Browser clients."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from pathlib import Path

from app.config.settings import Settings

from app.modules.workspace.browser_connectivity_contract import (
    TURNReachabilityProfile,
    TURNReachabilityProfileError,
)
from app.modules.workspace.browser_credential_models import BrowserIceServer


@dataclass(frozen=True)
class BrowserTurnCredentialIssuer:
    ice_servers: tuple[BrowserIceServer, ...]
    shared_secret: str
    ttl_seconds: int

    @classmethod
    def from_settings(cls, settings: Settings) -> BrowserTurnCredentialIssuer | None:
        profile_path = settings.TURN_REACHABILITY_PROFILE_FILE.strip()
        profile: TURNReachabilityProfile | None = None
        if profile_path:
            try:
                profile = TURNReachabilityProfile.from_file(Path(profile_path))
            except TURNReachabilityProfileError as exc:
                raise RuntimeError("TURN reachability profile is invalid") from exc
            kind = profile.credential_issuer_kind
            raw_servers = json.dumps(
                [{"urls": list(profile.frontend_urls)}],
                separators=(",", ":"),
            )
            raw_ttl = str(profile.credential_ttl_seconds)
        else:
            kind = settings.TURN_BROWSER_CREDENTIAL_ISSUER_KIND
            servers_file = settings.TURN_FRONTEND_ICE_SERVERS_JSON_FILE.strip()
            if servers_file:
                try:
                    raw_servers = Path(servers_file).read_text(encoding="utf-8").strip()
                except OSError as exc:
                    raise RuntimeError(
                        "TURN frontend ICE server file is unreadable"
                    ) from exc
            else:
                raw_servers = ""
            raw_ttl = str(settings.TURN_BROWSER_CREDENTIAL_TTL_SECONDS)
        if kind == "":
            return None
        if kind != "turnRest":
            raise RuntimeError(
                "TURN_BROWSER_CREDENTIAL_ISSUER_KIND must be turnRest"
            )
        secret_path = settings.TURN_REST_SHARED_SECRET_FILE.strip()
        try:
            shared_secret = Path(secret_path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError("TURN REST shared secret file is unreadable") from exc
        if not shared_secret or not raw_servers or not raw_ttl:
            raise RuntimeError("TURN REST Browser credential settings are incomplete")
        try:
            ttl_seconds = int(raw_ttl)
            decoded = json.loads(raw_servers)
            ice_servers = tuple(BrowserIceServer.model_validate(item) for item in decoded)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("TURN REST Browser credential settings are invalid") from exc
        if ttl_seconds < 60 or not ice_servers:
            raise RuntimeError("TURN REST Browser credential settings are invalid")
        return cls(
            ice_servers=ice_servers,
            shared_secret=shared_secret,
            ttl_seconds=ttl_seconds,
        )

    def issue(
        self,
        *,
        workspace_id: str,
        now: int | None = None,
    ) -> list[BrowserIceServer]:
        issued_at = int(time.time()) if now is None else now
        username = f"{issued_at + self.ttl_seconds}:browser:{workspace_id}"
        credential = base64.b64encode(
            hmac.new(
                self.shared_secret.encode(),
                username.encode(),
                hashlib.sha1,
            ).digest()
        ).decode()
        return [
            BrowserIceServer(
                urls=server.urls,
                username=username,
                credential=credential,
            )
            for server in self.ice_servers
        ]


__all__ = ["BrowserTurnCredentialIssuer"]

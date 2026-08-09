"""OIDC discovery, JWKS retrieval, and confidential-client ID-token validation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from jose import jwk, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError

from app.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def _http_client_kwargs(config: Settings) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"timeout": config.OIDC_DISCOVERY_TIMEOUT_SECONDS}
    if config.OIDC_CA_CERT_FILE:
        kwargs["verify"] = config.OIDC_CA_CERT_FILE
    return kwargs


class JWTValidationError(Exception):
    """JWT verification failed exception."""


class JWKSFetchError(Exception):
    """JWKS or OIDC discovery retrieval failed exception."""


@dataclass(frozen=True)
class OIDCDiscoveryDocument:
    """Validated OIDC Discovery endpoints exposed to the application."""

    issuer: str
    jwks_uri: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: Optional[str] = None
    end_session_endpoint: Optional[str] = None

    @classmethod
    def from_payload(
        cls, payload: Dict[str, Any], expected_issuer: str
    ) -> "OIDCDiscoveryDocument":
        if not isinstance(payload, dict):
            raise JWKSFetchError("OIDC discovery response must be a JSON object")

        issuer = payload.get("issuer")
        if issuer != expected_issuer:
            raise JWKSFetchError("OIDC discovery issuer does not match configuration")

        required_fields = (
            "jwks_uri",
            "authorization_endpoint",
            "token_endpoint",
        )
        for field_name in required_fields:
            value = payload.get(field_name)
            if not isinstance(value, str) or not _is_http_url(
                value, expected_issuer=expected_issuer
            ):
                raise JWKSFetchError(
                    f"OIDC discovery field '{field_name}' is missing or invalid"
                )

        optional_fields: dict[str, Optional[str]] = {}
        for field_name in ("userinfo_endpoint", "end_session_endpoint"):
            value = payload.get(field_name)
            if value is not None:
                if not isinstance(value, str) or not _is_http_url(
                    value, expected_issuer=expected_issuer
                ):
                    raise JWKSFetchError(
                        f"OIDC discovery field '{field_name}' is invalid"
                    )
                optional_fields[field_name] = value
            else:
                optional_fields[field_name] = None

        return cls(
            issuer=issuer,
            jwks_uri=payload["jwks_uri"],
            authorization_endpoint=payload["authorization_endpoint"],
            token_endpoint=payload["token_endpoint"],
            **optional_fields,
        )


def _is_http_url(value: str, *, expected_issuer: str) -> bool:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
    ):
        return False
    expected_scheme = urlparse(expected_issuer).scheme
    if expected_scheme == "https" and parsed.scheme != "https":
        return False
    return True


def _is_numeric_claim(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class JWTUtils:
    """Validate OIDC ID tokens using a provider-neutral issuer."""

    def __init__(self, config: Optional[Settings] = None):
        self.config = config or get_settings()
        self.jwks_cache: Optional[Dict[str, Any]] = None
        self.jwks_cache_time: Optional[datetime] = None
        self.discovery_cache: Optional[OIDCDiscoveryDocument] = None
        self.discovery_cache_time: Optional[datetime] = None

    def _cache_is_fresh(self, cache_time: Optional[datetime]) -> bool:
        if cache_time is None:
            return False
        age = (datetime.now(timezone.utc) - cache_time).total_seconds()
        return age < self.config.OIDC_JWKS_CACHE_TTL

    async def fetch_discovery(self, force: bool = False) -> OIDCDiscoveryDocument:
        """Fetch and validate the standard OIDC Discovery document."""

        if self.discovery_cache is not None and not force:
            if self._cache_is_fresh(self.discovery_cache_time):
                return self.discovery_cache

        try:
            async with httpx.AsyncClient(**_http_client_kwargs(self.config)) as client:
                response = await client.get(self.config.oidc_discovery_url)
                response.raise_for_status()
                payload = response.json()
            discovery = OIDCDiscoveryDocument.from_payload(
                payload,
                self.config.OIDC_ISSUER_URL,
            )
            self.discovery_cache = discovery
            self.discovery_cache_time = datetime.now(timezone.utc)
            return discovery
        except JWKSFetchError:
            raise
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch OIDC discovery: %s", exc)
            raise JWKSFetchError("Failed to fetch OIDC discovery document") from exc
        except (TypeError, ValueError, KeyError) as exc:
            logger.error("Invalid OIDC discovery response: %s", exc)
            raise JWKSFetchError("Invalid OIDC discovery response") from exc
        except Exception as exc:
            logger.error("Unexpected OIDC discovery error: %s", exc)
            raise JWKSFetchError("Unexpected OIDC discovery error") from exc

    async def fetch_jwks(self, force: bool = False) -> Dict[str, Any]:
        """Fetch and cache the issuer JWKS obtained from Discovery."""

        if self.jwks_cache is not None and not force:
            if self._cache_is_fresh(self.jwks_cache_time):
                logger.debug("Using cached JWKS")
                return self.jwks_cache

        discovery = await self.fetch_discovery()
        try:
            async with httpx.AsyncClient(**_http_client_kwargs(self.config)) as client:
                response = await client.get(discovery.jwks_uri)
                response.raise_for_status()
                jwks_data = response.json()
            if not isinstance(jwks_data, dict) or not isinstance(
                jwks_data.get("keys"), list
            ):
                raise JWKSFetchError("OIDC JWKS response must contain a keys array")
            self.jwks_cache = jwks_data
            self.jwks_cache_time = datetime.now(timezone.utc)
            logger.info("Successfully fetched OIDC JWKS")
            return jwks_data
        except JWKSFetchError:
            raise
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch OIDC JWKS: %s", exc)
            raise JWKSFetchError("Failed to fetch OIDC JWKS") from exc
        except (TypeError, ValueError, KeyError) as exc:
            logger.error("Invalid OIDC JWKS response: %s", exc)
            raise JWKSFetchError("Invalid OIDC JWKS response") from exc
        except Exception as exc:
            logger.error("Unexpected OIDC JWKS error: %s", exc)
            raise JWKSFetchError("Unexpected OIDC JWKS error") from exc

    @staticmethod
    def _get_token_headers(token: str) -> Dict[str, Any]:
        try:
            headers = jwt.get_unverified_headers(token)
        except JWTError as exc:
            raise JWTValidationError(f"Invalid token header: {exc}") from exc
        if not isinstance(headers, dict):
            raise JWTValidationError("Invalid token header")
        return headers

    def _validate_header_algorithm(self, headers: Dict[str, Any]) -> str:
        algorithm = headers.get("alg")
        if not isinstance(algorithm, str) or not algorithm:
            raise JWTValidationError("Token header missing 'alg' field")
        if algorithm not in self.config.OIDC_ALLOWED_ALGORITHMS:
            raise JWTValidationError(
                f"Token signing algorithm is not allowed: {algorithm}"
            )
        return algorithm

    @staticmethod
    def _find_public_key(
        jwks_data: Optional[Dict[str, Any]], kid: str
    ) -> Optional[Dict[str, Any]]:
        if not jwks_data:
            return None
        for key in jwks_data.get("keys", []):
            if (
                isinstance(key, dict)
                and key.get("kid") == kid
                and key.get("use") in (None, "sig")
            ):
                return key
        return None

    async def get_public_key_async(self, token: str) -> Dict[str, Any]:
        """Return a public JWK, refreshing JWKS once for an unknown key id."""

        headers = self._get_token_headers(token)
        self._validate_header_algorithm(headers)
        kid = headers.get("kid")
        if not isinstance(kid, str) or not kid:
            raise JWTValidationError("Token header missing 'kid' field")

        if self.jwks_cache is None or not self._cache_is_fresh(self.jwks_cache_time):
            try:
                self.jwks_cache = await self.fetch_jwks(force=True)
            except JWKSFetchError as exc:
                raise JWTValidationError(str(exc)) from exc
        key = self._find_public_key(self.jwks_cache, kid)
        if key is not None:
            return key

        try:
            self.jwks_cache = await self.fetch_jwks(force=True)
        except JWKSFetchError as exc:
            raise JWTValidationError(str(exc)) from exc
        key = self._find_public_key(self.jwks_cache, kid)
        if key is None:
            raise JWTValidationError(f"Public key not found for kid: {kid}")
        return key

    def _validate_payload(
        self,
        payload: Dict[str, Any],
        *,
        expected_audience: str,
        expected_nonce: str | None = None,
    ) -> None:
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise JWTValidationError("Token missing non-empty 'sub' claim")

        issuer = payload.get("iss")
        if issuer != self.config.OIDC_ISSUER_URL:
            raise JWTValidationError("Token issuer does not match configured issuer")

        audience = payload.get("aud")
        audiences = [audience] if isinstance(audience, str) else audience
        if (
            not isinstance(audiences, list)
            or not audiences
            or not all(isinstance(item, str) for item in audiences)
            or expected_audience not in audiences
        ):
            raise JWTValidationError("Token audience does not include the client ID")

        if expected_nonce is not None and payload.get("nonce") != expected_nonce:
            raise JWTValidationError("OIDC ID token nonce does not match callback")

        exp = payload.get("exp")
        issued_at = payload.get("iat")
        not_before = payload.get("nbf")
        if not _is_numeric_claim(exp):
            raise JWTValidationError("Token missing valid 'exp' claim")
        if not _is_numeric_claim(issued_at):
            raise JWTValidationError("Token missing valid 'iat' claim")
        if not_before is not None and not _is_numeric_claim(not_before):
            raise JWTValidationError("Token contains invalid 'nbf' claim")

        now = datetime.now(timezone.utc).timestamp()
        if exp <= now:
            raise JWTValidationError("Token has expired")
        if issued_at > now:
            raise JWTValidationError("Token 'iat' claim is in the future")
        if not_before is not None and not_before > now:
            raise JWTValidationError("Token is not yet valid")
        if exp <= issued_at:
            raise JWTValidationError("Token expiration must be after issuance")
        if exp - issued_at > self.config.OIDC_MAX_TOKEN_LIFETIME_SECONDS:
            raise JWTValidationError("Token lifetime exceeds configured maximum")

        if (
            self.config.OIDC_REQUIRED_ACR
            and payload.get("acr") != self.config.OIDC_REQUIRED_ACR
        ):
            raise JWTValidationError(
                "Token authentication assurance does not meet policy"
            )

    async def decode_id_token_async(
        self,
        token: str,
        *,
        nonce: str,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify a callback ID token for the confidential Manager client."""

        try:
            public_key = await self.get_public_key_async(token)
            headers = self._get_token_headers(token)
            algorithm = self._validate_header_algorithm(headers)
            key_algorithm = public_key.get("alg")
            if key_algorithm and key_algorithm != algorithm:
                raise JWTValidationError("Token algorithm does not match the JWKS key")
            signing_key = jwk.construct(public_key, algorithm=algorithm).to_pem()
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=[algorithm],
                issuer=self.config.OIDC_ISSUER_URL,
                audience=self.config.OIDC_CLIENT_ID,
                access_token=access_token,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_iss": True,
                    "verify_aud": True,
                    "require_exp": True,
                    "require_iat": True,
                },
            )
            if not isinstance(payload, dict):
                raise JWTValidationError("OIDC ID token payload must be an object")
            self._validate_payload(
                payload,
                expected_audience=self.config.OIDC_CLIENT_ID,
                expected_nonce=nonce,
            )
            return payload
        except JWTValidationError:
            raise
        except (
            ExpiredSignatureError,
            JWTClaimsError,
            JWTError,
            TypeError,
            ValueError,
        ) as exc:
            raise JWTValidationError(f"Invalid OIDC ID token: {exc}") from exc


_jwt_utils_instance: Optional[JWTUtils] = None


def get_jwt_utils() -> JWTUtils:
    """Return the process-wide JWT utility instance."""

    global _jwt_utils_instance
    if _jwt_utils_instance is None:
        _jwt_utils_instance = JWTUtils()
    return _jwt_utils_instance

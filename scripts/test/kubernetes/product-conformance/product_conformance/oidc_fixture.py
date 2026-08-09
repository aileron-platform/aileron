"""Provider-neutral OIDC fixture used only by Kubernetes product conformance."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import ssl
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _read_required_secret_file(environment_name: str) -> str:
    path = os.environ[environment_name]
    with open(path, encoding="utf-8") as secret_file:
        value = secret_file.read().strip()
    if not value:
        raise ValueError(f"{environment_name} must reference a non-empty file")
    return value


class FixtureState:
    def __init__(self) -> None:
        self.issuer = os.environ["OIDC_FIXTURE_ISSUER"].rstrip("/")
        self.client_id = os.getenv("OIDC_FIXTURE_CLIENT_ID", "aileron-manager")
        self.client_secret = _read_required_secret_file(
            "OIDC_FIXTURE_CLIENT_SECRET_FILE"
        )
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = "product-conformance-oidc-v1"
        self.users: dict[str, dict[str, str]] = {}
        self.next_username = ""
        self.codes: dict[str, dict[str, str]] = {}
        self.tokens: dict[str, dict[str, str]] = {}
        self.logout_count = 0

    def jwt(self, claims: dict[str, object]) -> str:
        header = _b64(
            json.dumps(
                {"alg": "RS256", "kid": self.kid, "typ": "JWT"}, separators=(",", ":")
            ).encode()
        )
        payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
        signature = self.key.sign(
            f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256()
        )
        return f"{header}.{payload}.{_b64(signature)}"

    def jwk(self) -> dict[str, str]:
        numbers = self.key.public_key().public_numbers()
        return {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": self.kid,
            "n": _b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
            "e": _b64(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
        }


STATE = FixtureState()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0"))
        parsed = parse_qs(self.rfile.read(length).decode())
        return {key: values[0] for key, values in parsed.items()}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/.well-known/openid-configuration":
            self._json(
                200,
                {
                    "issuer": STATE.issuer,
                    "authorization_endpoint": f"{STATE.issuer}/authorize",
                    "token_endpoint": f"{STATE.issuer}/token",
                    "userinfo_endpoint": f"{STATE.issuer}/userinfo",
                    "jwks_uri": f"{STATE.issuer}/jwks",
                    "end_session_endpoint": f"{STATE.issuer}/logout",
                    "response_types_supported": ["code"],
                    "subject_types_supported": ["public"],
                    "id_token_signing_alg_values_supported": ["RS256"],
                },
            )
            return
        if parsed.path == "/jwks":
            self._json(200, {"keys": [STATE.jwk()]})
            return
        if parsed.path == "/authorize":
            query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
            username = STATE.next_username
            user = STATE.users.get(username)
            if user is None or query.get("client_id") != STATE.client_id:
                self._json(400, {"error": "invalid_request"})
                return
            code = secrets.token_urlsafe(24)
            STATE.codes[code] = {
                **user,
                "nonce": query.get("nonce", ""),
                "code_challenge": query.get("code_challenge", ""),
            }
            location = f"{query['redirect_uri']}?{urlencode({'code': code, 'state': query['state']})}"
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()
            return
        if parsed.path == "/userinfo":
            token = self.headers.get("Authorization", "").removeprefix("Bearer ")
            user = STATE.tokens.get(token)
            if user is None:
                self._json(401, {"error": "invalid_token"})
            else:
                self._json(200, user)
            return
        if parsed.path == "/logout":
            STATE.logout_count += 1
            self.send_response(204)
            self.end_headers()
            return
        if parsed.path == "/test/logout-count":
            self._json(200, {"count": STATE.logout_count})
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/test/users":
            length = int(self.headers.get("Content-Length", "0"))
            user = json.loads(self.rfile.read(length))
            user_id = secrets.token_hex(16)
            STATE.users[user["username"]] = {
                "sub": user_id,
                "preferred_username": user["username"],
                "email": user["email"],
                "name": "Product Conformance",
                "platform_role": user["realm_role"],
            }
            self._json(201, {"id": user_id})
            return
        if parsed.path == "/test/next-login":
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            STATE.next_username = payload["username"]
            self.send_response(204)
            self.end_headers()
            return
        if parsed.path == "/token":
            form = self._form()
            code = STATE.codes.pop(form.get("code", ""), None)
            verifier = form.get("code_verifier", "")
            challenge = _b64(hashlib.sha256(verifier.encode()).digest())
            if (
                code is None
                or form.get("client_id") != STATE.client_id
                or form.get("client_secret") != STATE.client_secret
                or challenge != code["code_challenge"]
            ):
                self._json(400, {"error": "invalid_grant"})
                return
            now = int(time.time())
            claims = {
                **code,
                "iss": STATE.issuer,
                "aud": STATE.client_id,
                "iat": now,
                "exp": now + 300,
            }
            claims.pop("code_challenge", None)
            access_token = secrets.token_urlsafe(32)
            STATE.tokens[access_token] = {
                key: value
                for key, value in code.items()
                if key != "code_challenge" and key != "nonce"
            }
            self._json(
                200,
                {
                    "token_type": "Bearer",
                    "expires_in": 300,
                    "access_token": access_token,
                    "id_token": STATE.jwt(claims),
                },
            )
            return
        self._json(404, {"error": "not_found"})


def serve() -> int:
    server = ThreadingHTTPServer(("0.0.0.0", 8443), Handler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(
        certfile=os.environ["OIDC_FIXTURE_TLS_CERT_FILE"],
        keyfile=os.environ["OIDC_FIXTURE_TLS_KEY_FILE"],
    )
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
    return 0

#!/bin/sh

set -eu

suffix="$(date +%s)-$$"
network="aileron-keycloak-e2e-${suffix}"
postgres_container="aileron-identity-postgres-${suffix}"
keycloak_container="aileron-keycloak-${suffix}"
postgres_secret="aileron-postgres-secret-${suffix}"
admin_secret="aileron-keycloak-admin-${suffix}"
realm_import="aileron-keycloak-realm-${suffix}"
public_config="aileron-keycloak-config-${suffix}"
postgres_data="aileron-keycloak-postgres-${suffix}"

cleanup() {
  docker rm -f "${keycloak_container}" "${postgres_container}" >/dev/null 2>&1 || true
  docker network rm "${network}" >/dev/null 2>&1 || true
  docker volume rm "${postgres_secret}" "${admin_secret}" "${realm_import}" "${public_config}" "${postgres_data}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

fail() {
  printf '%s\n' "$1" >&2
  docker logs "${keycloak_container}" >&2 2>/dev/null || true
  exit 1
}

wait_for_command() {
  container=$1
  shift
  attempt=0
  while test "${attempt}" -lt 180; do
    if docker exec "${container}" "$@" >/dev/null 2>&1; then
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 1
  done
  fail "container did not become ready: ${container}"
}

docker network create "${network}" >/dev/null
for volume in "${postgres_secret}" "${admin_secret}" "${realm_import}" "${public_config}" "${postgres_data}"; do
  docker volume create "${volume}" >/dev/null
done

docker run --rm \
  -v "${postgres_secret}:/postgres" \
  -v "${admin_secret}:/admin" \
  -v "${realm_import}:/realm" \
  -v "${public_config}:/config" \
  alpine:3.20 sh -ec '
    printf %s keycloak > /postgres/username
    printf %s postgres-test-password > /postgres/password
    printf %s keycloak-admin > /admin/username
    printf %s keycloak-admin-password > /admin/password
    printf %s jdbc:postgresql://identity-postgres:5432/keycloak > /config/db-url
    printf %s http://identity-keycloak:8080 > /config/hostname
    printf %s http://identity-keycloak:8080 > /config/hostname-admin
    cat > /realm/realm.json <<"JSON"
{"realm":"aileron","enabled":true,"registrationAllowed":false,"clients":[{"clientId":"aileron-manager","enabled":true,"protocol":"openid-connect","publicClient":false,"clientAuthenticatorType":"client-secret","secret":"manager-client-secret","standardFlowEnabled":true,"implicitFlowEnabled":false,"directAccessGrantsEnabled":false,"redirectUris":["http://client.example.test/callback"],"webOrigins":["http://client.example.test"],"attributes":{"pkce.code.challenge.method":"S256"},"defaultClientScopes":["web-origins","acr","profile","email"]}],"users":[{"id":"00000000-0000-4000-8000-000000000001","username":"admin","email":"admin@example.test","firstName":"Aileron","lastName":"Administrator","enabled":true,"emailVerified":true,"credentials":[{"type":"password","value":"admin123","temporary":false}]}]}
JSON
    chmod 0444 /postgres/* /admin/* /realm/* /config/*
  '

docker run -d --name "${postgres_container}" --network "${network}" --network-alias identity-postgres \
  -v "${postgres_secret}:/run/secrets/identity-postgres:ro" \
  -v "${postgres_data}:/var/lib/postgresql/data" \
  -e POSTGRES_DB=keycloak \
  -e POSTGRES_USER_FILE=/run/secrets/identity-postgres/username \
  -e POSTGRES_PASSWORD_FILE=/run/secrets/identity-postgres/password \
  postgres:15-alpine >/dev/null
wait_for_command "${postgres_container}" pg_isready -U keycloak -d keycloak

docker run -d --name "${keycloak_container}" --network "${network}" --network-alias identity-keycloak \
  -v "${postgres_secret}:/run/secrets/identity-postgres:ro" \
  -v "${admin_secret}:/run/secrets/keycloak-bootstrap-admin:ro" \
  -v "${realm_import}:/opt/keycloak/data/import:ro" \
  -v "${public_config}:/opt/aileron/public-config:ro" \
  ailerondocker/platform-keycloak:dev \
  start --optimized --import-realm >/dev/null

wait_for_command "${keycloak_container}" bash -c ':> /dev/tcp/127.0.0.1/8080'
docker run --rm --network "${network}" alpine:3.20 sh -ec '
  attempt=0
  until wget -qO- http://identity-keycloak:8080/realms/aileron/.well-known/openid-configuration >/dev/null 2>&1; do
    test "$attempt" -lt 120 || exit 1
    attempt=$((attempt + 1))
    sleep 1
  done
' ||
  fail 'Keycloak discovery failed on a clean database'

docker exec "${keycloak_container}" /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://127.0.0.1:8080 --realm master \
  --user keycloak-admin --password keycloak-admin-password >/dev/null ||
  fail 'Keycloak Admin Console administrator bootstrap failed'

oidc_script=$(cat <<'PY'
import base64, hashlib, html.parser, http.cookiejar, json, urllib.error, urllib.parse, urllib.request

issuer = "http://identity-keycloak:8080/realms/aileron"
verifier = "a" * 64
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
query = urllib.parse.urlencode({"client_id":"aileron-manager","redirect_uri":"http://client.example.test/callback","response_type":"code","scope":"openid profile email","state":"contract-state","code_challenge":challenge,"code_challenge_method":"S256"})
document = opener.open(f"{issuer}/protocol/openid-connect/auth?{query}").read().decode()

class LoginForm(html.parser.HTMLParser):
    action = None
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form" and values.get("id") == "kc-form-login":
            self.action = values.get("action")

form = LoginForm(); form.feed(document)
assert form.action
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
login = urllib.parse.urlencode({"username":"admin","password":"admin123","credentialId":""}).encode()
no_redirect = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect())
try:
    no_redirect.open(urllib.request.Request(form.action, data=login), timeout=10)
    raise AssertionError("login did not redirect")
except urllib.error.HTTPError as error:
    assert error.code == 302
    location = error.headers["Location"]
params = urllib.parse.parse_qs(urllib.parse.urlsplit(location).query)
assert params["state"] == ["contract-state"]
token_data = urllib.parse.urlencode({"grant_type":"authorization_code","client_id":"aileron-manager","client_secret":"manager-client-secret","redirect_uri":"http://client.example.test/callback","code":params["code"][0],"code_verifier":verifier}).encode()
tokens = json.loads(urllib.request.urlopen(urllib.request.Request(f"{issuer}/protocol/openid-connect/token", data=token_data), timeout=10).read())
payload = json.loads(base64.urlsafe_b64decode(tokens["id_token"].split(".")[1] + "=="))
assert payload["sub"] == "00000000-0000-4000-8000-000000000001"
logout_data = urllib.parse.urlencode({"client_id":"aileron-manager","client_secret":"manager-client-secret","refresh_token":tokens["refresh_token"]}).encode()
response = urllib.request.urlopen(urllib.request.Request(f"{issuer}/protocol/openid-connect/logout", data=logout_data), timeout=10)
assert response.status == 204
PY
)
docker run --rm --network "${network}" python:3.12-alpine python -c "${oidc_script}" ||
  fail 'platform administrator Authorization Code + PKCE or logout failed'

if docker inspect "${keycloak_container}" --format '{{range .Config.Env}}{{println .}}{{end}}' |
  grep -Eq '^(KC_BOOTSTRAP_ADMIN_PASSWORD|AILERON_BOOTSTRAP_ADMIN_PASSWORD)='; then
  fail 'Keycloak long-lived process retains a Secret environment contract'
fi

docker restart "${keycloak_container}" >/dev/null
docker run --rm --network "${network}" alpine:3.20 sh -ec '
  attempt=0
  until wget -qO- http://identity-keycloak:8080/realms/aileron/.well-known/openid-configuration >/dev/null 2>&1; do
    test "$attempt" -lt 120 || exit 1
    attempt=$((attempt + 1))
    sleep 1
  done
' || fail 'Keycloak discovery failed after restart'
docker exec "${keycloak_container}" /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://127.0.0.1:8080 --realm master \
  --user keycloak-admin --password keycloak-admin-password >/dev/null ||
  fail 'Keycloak administrator is unavailable after restart'

printf '%s\n' 'Local Keycloak clean-volume OIDC E2E passed'

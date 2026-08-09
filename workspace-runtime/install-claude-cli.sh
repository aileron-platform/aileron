#!/bin/sh
set -eu

target="${1:-stable}"
repository_base_url="https://downloads.claude.ai/claude-code/apt"
key_url="https://downloads.claude.ai/keys/claude-code.asc"
keyring_dir="${CLAUDE_APT_KEYRING_DIR:-/etc/apt/keyrings}"
source_dir="${CLAUDE_APT_SOURCE_DIR:-/etc/apt/sources.list.d}"
expected_fingerprint="31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE"

architecture="$(dpkg --print-architecture)"
case "$architecture" in
    amd64|arm64) ;;
    *)
        echo "Unsupported Claude Code package architecture: $architecture" >&2
        exit 1
        ;;
esac

case "$target" in
    stable|latest)
        channel="$target"
        package_spec="claude-code"
        ;;
    *)
        if ! printf '%s\n' "$target" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$'; then
            echo "Unsupported Claude Code version: $target" >&2
            exit 1
        fi
        channel="latest"
        package_spec="claude-code=${target}-1"
        ;;
esac

mkdir -p "$keyring_dir" "$source_dir"
key_file="$(mktemp)"
gnupg_home="$(mktemp -d)"
verification_home="$(mktemp -d)"
trap 'rm -f "$key_file"; rm -rf "$gnupg_home" "$verification_home"' EXIT HUP INT TERM
chmod 0700 "$gnupg_home"
chmod 0700 "$verification_home"

curl \
    --fail \
    --silent \
    --show-error \
    --location \
    --retry 5 \
    --retry-all-errors \
    --retry-delay 5 \
    --connect-timeout 30 \
    --max-time 300 \
    --output "$key_file" \
    "$key_url"

primary_fingerprints="$(
    GNUPGHOME="$gnupg_home" gpg --show-keys --with-colons "$key_file" 2>/dev/null \
        | awk -F: '
            $1 == "pub" { primary = 1; next }
            primary && $1 == "fpr" { print $10; primary = 0 }
        '
)"
if [ "$primary_fingerprints" != "$expected_fingerprint" ]; then
    echo "Claude Code signing key fingerprint verification failed" >&2
    exit 1
fi

keyring_path="$keyring_dir/claude-code.asc"
source_path="$source_dir/claude-code.list"
install -m 0644 "$key_file" "$keyring_path"
printf '%s\n' \
    "deb [arch=${architecture} signed-by=${keyring_path}] ${repository_base_url}/${channel} ${channel} main" \
    > "$source_path"

set -- \
    -o Acquire::Retries=5 \
    -o Acquire::http::Timeout=300 \
    -o Acquire::https::Timeout=300

apt-get "$@" update
DEBIAN_FRONTEND=noninteractive apt-get "$@" install -y --no-install-recommends "$package_spec"

installed_package_version="$(dpkg-query -W -f='${Version}' claude-code)"
if [ "$target" != "stable" ] && [ "$target" != "latest" ]; then
    expected_package_version="${target}-1"
    if [ "$installed_package_version" != "$expected_package_version" ]; then
        echo "Claude Code package version mismatch: expected $expected_package_version, got $installed_package_version" >&2
        exit 1
    fi
fi

if ! command -v claude >/dev/null 2>&1; then
    echo "Claude Code package did not install the claude executable" >&2
    exit 1
fi

cli_output="$(
    HOME="$verification_home" \
        XDG_CONFIG_HOME="$verification_home/.config" \
        XDG_DATA_HOME="$verification_home/.local/share" \
        XDG_STATE_HOME="$verification_home/.local/state" \
        DISABLE_AUTOUPDATER=1 \
        claude --version 2>&1
)"
cli_version="$(printf '%s\n' "$cli_output" | awk 'NR == 1 { print $1 }')"
package_upstream_version="${installed_package_version%-*}"
if [ "$cli_version" != "$package_upstream_version" ]; then
    echo "Claude Code executable version mismatch: expected $package_upstream_version, got $cli_output" >&2
    exit 1
fi

apt-get clean
printf 'Installed Claude Code %s for %s from the %s channel\n' \
    "$cli_version" "$architecture" "$channel"

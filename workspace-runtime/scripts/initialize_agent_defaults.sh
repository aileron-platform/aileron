#!/bin/sh

set -eu

source_dir="${AILERON_AGENT_DEFAULTS_SOURCE:-/opt/aileron/agent-defaults}"
workspace_root="${AILERON_WORKSPACE_PATH}"
xdg_state_home="${XDG_STATE_HOME:-${HOME}/.local/state}"
marker_dir="${xdg_state_home}/aileron/bootstrap"
marker_path="${marker_dir}/agent-defaults-v1.json"

fail() {
  echo "AGENT_DEFAULTS_INIT_FAILED: $*" >&2
  exit 1
}

[ -d "${source_dir}" ] || fail "defaults source is missing"
mkdir -p "${marker_dir}"
if [ -f "${marker_path}" ]; then
  exit 0
fi

# Once seeded, each Target Client's Client User Scope copy is Workspace-owned;
# this script never reconciles or restores it on later restarts or upgrades.

require_safe_absolute_path() {
  desc="$1"
  path="$2"
  case "${path}" in
    /*) ;;
    *) fail "${desc} must be an absolute path: ${path}" ;;
  esac
  case "/${path#/}/" in
    */../*) fail "${desc} must not contain '..' path segments: ${path}" ;;
  esac
  [ "${path}" != "/" ] || fail "${desc} must not be the filesystem root: ${path}"
}

verify_scope_target() {
  desc="$1"
  path="$2"
  require_safe_absolute_path "${desc}" "${path}"
  if [ -L "${path}" ]; then
    fail "${desc} must not be a symbolic link: ${path}"
  fi
  if [ -e "${path}" ] && [ ! -d "${path}" ]; then
    fail "${desc} must be a directory: ${path}"
  fi
}

seed_client_skills() {
  skills_root="$1"
  mkdir -p "${skills_root}"
  chmod g+rws "${skills_root}"
  [ -d "${source_dir}/skills" ] || return 0
  for source_skill in "${source_dir}"/skills/*; do
    [ -d "${source_skill}" ] || continue
    skill_name="$(basename "${source_skill}")"
    target_skill="${skills_root}/${skill_name}"
    if [ -e "${target_skill}" ] || [ -L "${target_skill}" ]; then
      continue
    fi
    staged_skill="$(mktemp -d "${skills_root}/.${skill_name}.staged.XXXXXX")"
    cp -a "${source_skill}/." "${staged_skill}/"
    find "${staged_skill}" -type d -exec chmod g+rws '{}' +
    find "${staged_skill}" -type f -exec chmod g+rw '{}' +
    mv "${staged_skill}" "${target_skill}"
  done
}

claude_home="${CLAUDE_CONFIG_DIR:-${HOME}/.claude}"
codex_home="${CODEX_HOME:-${HOME}/.codex}"
opencode_home="${HOME}/.config/opencode"

verify_scope_target "Claude Client User Scope root" "${claude_home}"
verify_scope_target "Claude Agent Defaults skills target" "${claude_home}/skills"
verify_scope_target "Codex Client User Scope root" "${codex_home}"
verify_scope_target "Codex Agent Defaults skills target" "${codex_home}/skills"
verify_scope_target "OpenCode Client User Scope root" "${opencode_home}"
verify_scope_target "OpenCode Agent Defaults skills target" "${opencode_home}/skills"

umask 0007
mkdir -p "${claude_home}" "${codex_home}" "${opencode_home}"
chmod g+rws "${claude_home}" "${codex_home}" "${opencode_home}"

seed_client_skills "${claude_home}/skills"
seed_client_skills "${codex_home}/skills"
seed_client_skills "${opencode_home}/skills"

# .mcp.json, CLAUDE.md and AGENTS.md placement are unrelated to the Client
# User Scope skills migration and keep their prior locations and behavior.
opencode_agents_home="${XDG_CONFIG_HOME:-${HOME}/.config}/opencode"
mkdir -p "${opencode_agents_home}"

if [ -f "${source_dir}/mcp.json" ] && [ ! -e "${workspace_root}/.mcp.json" ]; then
  staged_mcp="$(mktemp "${workspace_root}/.mcp.json.staged.XXXXXX")"
  cp "${source_dir}/mcp.json" "${staged_mcp}"
  mv "${staged_mcp}" "${workspace_root}/.mcp.json"
fi
if [ -f "${source_dir}/CLAUDE.md" ] && [ ! -e "${claude_home}/CLAUDE.md" ]; then
  staged_claude="$(mktemp "${claude_home}/.CLAUDE.md.staged.XXXXXX")"
  cp "${source_dir}/CLAUDE.md" "${staged_claude}"
  mv "${staged_claude}" "${claude_home}/CLAUDE.md"
fi
if [ -f "${source_dir}/AGENTS.md" ]; then
  if [ ! -e "${codex_home}/AGENTS.md" ]; then
    staged_codex="$(mktemp "${codex_home}/.AGENTS.md.staged.XXXXXX")"
    cp "${source_dir}/AGENTS.md" "${staged_codex}"
    mv "${staged_codex}" "${codex_home}/AGENTS.md"
  fi
  if [ ! -e "${opencode_agents_home}/AGENTS.md" ]; then
    staged_opencode="$(mktemp "${opencode_agents_home}/.AGENTS.md.staged.XXXXXX")"
    cp "${source_dir}/AGENTS.md" "${staged_opencode}"
    mv "${staged_opencode}" "${opencode_agents_home}/AGENTS.md"
  fi
fi

manifest_sha="$(
  find "${source_dir}" -type f -exec sha256sum '{}' \; |
    sort |
    sha256sum |
    awk '{print $1}'
)"
completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
staged_marker="$(mktemp "${marker_dir}/.agent-defaults-v1.json.staged.XXXXXX")"
printf '{"schemaVersion":1,"manifestSha256":"%s","completedAt":"%s"}\n' \
  "${manifest_sha}" "${completed_at}" > "${staged_marker}"
mv "${staged_marker}" "${marker_path}"

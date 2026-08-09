#!/bin/sh

set -eu

source_dir="${AILERON_AGENT_DEFAULTS_SOURCE:-/opt/aileron/agent-defaults}"
workspace_root="${AILERON_WORKSPACE_PATH}"
xdg_state_home="${XDG_STATE_HOME:-${HOME}/.local/state}"
marker_dir="${xdg_state_home}/aileron/bootstrap"
marker_path="${marker_dir}/agent-defaults-v1.json"
layout_marker_path="${marker_dir}/agent-defaults-v2.json"
workspace_agents_dir="${workspace_root}/.agents"
workspace_skills_dir="${workspace_agents_dir}/skills"
workspace_claude_dir="${workspace_root}/.claude"
workspace_claude_skills="${workspace_claude_dir}/skills"
workspace_codex_dir="${workspace_root}/.codex"
workspace_opencode_dir="${workspace_root}/.opencode"

fail() {
  echo "AGENT_DEFAULTS_INIT_FAILED: $*" >&2
  exit 1
}

[ -d "${source_dir}" ] || fail "defaults source is missing"
mkdir -p "${marker_dir}"
if [ -f "${marker_path}" ] && [ -f "${layout_marker_path}" ]; then
  exit 0
fi

umask 0007
mkdir -p \
  "${workspace_skills_dir}" \
  "${workspace_claude_dir}"

if [ -e "${workspace_claude_skills}" ] || [ -L "${workspace_claude_skills}" ]; then
  if [ ! -L "${workspace_claude_skills}" ] ||
    [ "$(readlink "${workspace_claude_skills}")" != "${workspace_skills_dir}" ]; then
    fail "${workspace_claude_skills} conflicts with the required skills symlink"
  fi
else
  ln -s "${workspace_skills_dir}" "${workspace_claude_skills}"
fi

if [ ! -f "${marker_path}" ] && [ -d "${source_dir}/skills" ]; then
  for source_skill in "${source_dir}"/skills/*; do
    [ -d "${source_skill}" ] || continue
    skill_name="$(basename "${source_skill}")"
    target_skill="${workspace_skills_dir}/${skill_name}"
    if [ -e "${target_skill}" ] || [ -L "${target_skill}" ]; then
      [ -d "${target_skill}" ] && [ ! -L "${target_skill}" ] ||
        fail "${target_skill} conflicts with the default skill directory"
      continue
    fi
    staged_skill="$(mktemp -d "${workspace_skills_dir}/.${skill_name}.staged.XXXXXX")"
    cp -a "${source_skill}/." "${staged_skill}/"
    mv "${staged_skill}" "${target_skill}"
  done
fi

for tool_dir in "${workspace_codex_dir}" "${workspace_opencode_dir}"; do
  if [ -L "${tool_dir}" ] ||
    { [ -e "${tool_dir}" ] && [ ! -d "${tool_dir}" ]; }; then
    continue
  fi
  mkdir -p "${tool_dir}"
  target_skills_dir="${tool_dir}/skills"
  if [ -L "${target_skills_dir}" ] ||
    { [ -e "${target_skills_dir}" ] && [ ! -d "${target_skills_dir}" ]; }; then
    continue
  fi
  mkdir -p "${target_skills_dir}"
  for default_skill in "${source_dir}"/skills/*; do
    [ -d "${default_skill}" ] || continue
    skill_name="$(basename "${default_skill}")"
    source_skill="${workspace_skills_dir}/${skill_name}"
    [ -d "${source_skill}" ] && [ ! -L "${source_skill}" ] || continue
    target_skill="${target_skills_dir}/${skill_name}"
    if [ -e "${target_skill}" ] || [ -L "${target_skill}" ]; then
      continue
    fi
    staged_skill="$(mktemp -d "${target_skills_dir}/.${skill_name}.staged.XXXXXX")"
    cp -a "${source_skill}/." "${staged_skill}/"
    mv "${staged_skill}" "${target_skill}"
  done
done

if [ ! -f "${marker_path}" ] &&
  [ -f "${source_dir}/mcp.json" ] &&
  [ ! -e "${workspace_root}/.mcp.json" ]; then
  staged_mcp="$(mktemp "${workspace_root}/.mcp.json.staged.XXXXXX")"
  cp "${source_dir}/mcp.json" "${staged_mcp}"
  mv "${staged_mcp}" "${workspace_root}/.mcp.json"
fi

umask 0077
claude_home="${HOME}/.claude"
codex_home="${CODEX_HOME:-${HOME}/.codex}"
opencode_home="${XDG_CONFIG_HOME:-${HOME}/.config}/opencode"
mkdir -p "${claude_home}" "${codex_home}" "${opencode_home}"

if [ ! -f "${marker_path}" ] &&
  [ -f "${source_dir}/CLAUDE.md" ] &&
  [ ! -e "${claude_home}/CLAUDE.md" ]; then
  staged_claude="$(mktemp "${claude_home}/.CLAUDE.md.staged.XXXXXX")"
  cp "${source_dir}/CLAUDE.md" "${staged_claude}"
  mv "${staged_claude}" "${claude_home}/CLAUDE.md"
fi
if [ ! -f "${marker_path}" ] && [ -f "${source_dir}/AGENTS.md" ]; then
  if [ ! -e "${codex_home}/AGENTS.md" ]; then
    staged_codex="$(mktemp "${codex_home}/.AGENTS.md.staged.XXXXXX")"
    cp "${source_dir}/AGENTS.md" "${staged_codex}"
    mv "${staged_codex}" "${codex_home}/AGENTS.md"
  fi
  if [ ! -e "${opencode_home}/AGENTS.md" ]; then
    staged_opencode="$(mktemp "${opencode_home}/.AGENTS.md.staged.XXXXXX")"
    cp "${source_dir}/AGENTS.md" "${staged_opencode}"
    mv "${staged_opencode}" "${opencode_home}/AGENTS.md"
  fi
fi

manifest_sha="$(
  find "${source_dir}" -type f -exec sha256sum '{}' \; |
    sort |
    sha256sum |
    awk '{print $1}'
)"
completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [ ! -f "${marker_path}" ]; then
  staged_marker="$(mktemp "${marker_dir}/.agent-defaults-v1.json.staged.XXXXXX")"
  printf '{"schemaVersion":1,"manifestSha256":"%s","completedAt":"%s"}\n' \
    "${manifest_sha}" "${completed_at}" > "${staged_marker}"
  mv "${staged_marker}" "${marker_path}"
fi
staged_layout_marker="$(
  mktemp "${marker_dir}/.agent-defaults-v2.json.staged.XXXXXX"
)"
printf '{"schemaVersion":2,"manifestSha256":"%s","completedAt":"%s"}\n' \
  "${manifest_sha}" "${completed_at}" > "${staged_layout_marker}"
mv "${staged_layout_marker}" "${layout_marker_path}"

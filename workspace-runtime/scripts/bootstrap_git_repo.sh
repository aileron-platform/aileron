#!/bin/sh
set -eu

WORKSPACE_PATH="${WORKSPACE_BOOTSTRAP_WORKSPACE_PATH:-/workspace}"
INIT_GIT="${WORKSPACE_INIT_GIT:-0}"
GIT_INIT_BRANCH="${GIT_INIT_BRANCH:-main}"
GIT_USER_NAME_VALUE="${GIT_USER_NAME:-Developer}"
GIT_USER_EMAIL_VALUE="${GIT_USER_EMAIL:-developer@workspace.local}"

should_init_git() {
  case "${INIT_GIT}" in
    1|true|TRUE|yes|YES|on|ON)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

if [ -n "${GIT_REPO_URL:-}" ]; then
  echo "ℹ️  GIT_REPO_URL is set; skipping workspace git bootstrap"
  exit 0
fi

if ! should_init_git; then
  echo "ℹ️  WORKSPACE_INIT_GIT is disabled; leaving workspace as a plain directory"
  exit 0
fi

mkdir -p "${WORKSPACE_PATH}"

if [ -d "${WORKSPACE_PATH}/.git" ]; then
  echo "ℹ️  Workspace repository already exists; skipping git init"
  exit 0
fi

git -C "${WORKSPACE_PATH}" init --initial-branch "${GIT_INIT_BRANCH}" >/dev/null
git -C "${WORKSPACE_PATH}" config user.name "${GIT_USER_NAME_VALUE}"
git -C "${WORKSPACE_PATH}" config user.email "${GIT_USER_EMAIL_VALUE}"

echo "✅ Initialized Git repository in ${WORKSPACE_PATH}"

#!/usr/bin/env bash
# ==============================================================================
# Vexlyx — One-Line Server Installer (F5.1)
# Usage: curl -fsSL https://vexlyx.atlantiqs.org/install.sh | bash
#
# This is the thin, public entrypoint: it only figures out where the Vexlyx
# checkout lives (cloning/updating it if needed) and hands off to the real
# orchestrator at system/scripts/install/run.sh, which is versioned inside
# the repo itself so every actual install step can be reviewed, tested, and
# changed without touching this file.
#
# Which code gets installed (VEXLYX_REPO_REF):
#   unset / "latest"  the newest stable release tag (vMAJOR.MINOR.PATCH);
#                     prerelease tags such as v1.0.0-rc.1 are never chosen
#   v1.2.3            that exact release
#   main (or any branch)  the tip of that branch, for development
# An existing install that follows a branch keeps following it unless
# VEXLYX_REPO_REF is set, so re-running the installer never silently
# changes channel.
# ==============================================================================
set -euo pipefail

# Only stable releases: vMAJOR.MINOR.PATCH, no prerelease or build suffix.
RELEASE_TAG_PATTERN='^v[0-9]+\.[0-9]+\.[0-9]+$'

log() { echo "[install.sh] $*"; }
warn() { echo "[install.sh] WARNING: $*" >&2; }

# Prints the newest stable release tag on the remote, or nothing if there is
# none (or the remote cannot be reached). `sort -V` compares version numbers
# numerically, so v0.10.0 is newer than v0.9.0.
latest_release_tag() {
  { git ls-remote --tags --refs "${VEXLYX_REPO_URL}" 'v*' 2>/dev/null || true; } \
    | awk '{ sub("^refs/tags/", "", $2); print $2 }' \
    | { grep -E "${RELEASE_TAG_PATTERN}" || true; } \
    | sort -V \
    | tail -n 1
}

remote_has_tag() {
  git ls-remote --exit-code --tags --refs "${VEXLYX_REPO_URL}" "refs/tags/$1" >/dev/null 2>&1
}

# Sets TARGET_KIND ("tag" or "branch") and TARGET_NAME from VEXLYX_REPO_REF.
resolve_target() {
  local requested="${VEXLYX_REPO_REF:-latest}"

  if [[ "${requested}" == "latest" ]]; then
    local tag
    tag="$(latest_release_tag)"
    if [[ -n "${tag}" ]]; then
      TARGET_KIND="tag"
      TARGET_NAME="${tag}"
    else
      warn "No release tag found on ${VEXLYX_REPO_URL}; falling back to the main branch."
      TARGET_KIND="branch"
      TARGET_NAME="main"
    fi
  elif remote_has_tag "${requested}"; then
    TARGET_KIND="tag"
    TARGET_NAME="${requested}"
  else
    TARGET_KIND="branch"
    TARGET_NAME="${requested}"
  fi
}

describe_target() {
  if [[ "${TARGET_KIND}" == "tag" ]]; then
    echo "release ${TARGET_NAME}"
  else
    echo "branch ${TARGET_NAME} (development, not a tagged release)"
  fi
}

is_vexlyx_checkout() {
  [[ -f "$1/CLAUDE.md" && -f "$1/system/scripts/install/run.sh" ]]
}

prepare_mail_upgrade() {
  local migration_script state_dir status_line
  local runtime_files=(
    docker/postfix/config/virtual_domains docker/postfix/config/virtual_mailbox_maps
    docker/postfix/config/virtual_alias_maps docker/dovecot/config/users
    docker/postfix/opendkim/KeyTable docker/postfix/opendkim/SigningTable
    docker/postfix/opendkim/TrustedHosts
  )
  git diff --cached --quiet || { echo "[ERROR] Staged source changes must be preserved before upgrading." >&2; exit 1; }
  while IFS= read -r status_line; do
    case "${status_line:3}" in
      docker/postfix/config/virtual_domains|docker/postfix/config/virtual_mailbox_maps|docker/postfix/config/virtual_alias_maps|docker/dovecot/config/users|docker/postfix/opendkim/KeyTable|docker/postfix/opendkim/SigningTable|docker/postfix/opendkim/TrustedHosts) ;;
      *) echo "[ERROR] Source changes detected; upgrade stopped without discarding them: ${status_line:3}" >&2; exit 1;;
    esac
  done < <(source_changes)
  if ! git cat-file -e FETCH_HEAD:system/python/mail_state_migrate.py 2>/dev/null; then
    [[ -z "$(source_changes)" ]] || { echo "[ERROR] Target revision has no mail-state migration. Preserve generated maps before upgrading." >&2; exit 1; }
    return
  fi
  if [[ -z "$(git ls-files -- "${runtime_files[@]}")" ]]; then return; fi
  state_dir="${VEXLYX_MAIL_STATE_DIR:-}"
  if [[ -z "$state_dir" && -f /etc/vexlyx/vexlyx.env ]]; then
    state_dir="$(sed -n 's/^VEXLYX_MAIL_STATE_DIR=//p' /etc/vexlyx/vexlyx.env | tail -n 1)"
  fi
  state_dir="${state_dir:-/var/lib/vexlyx/mail}"
  command -v python3 >/dev/null || { echo "[ERROR] Python 3 is required to preserve legacy mail state before upgrading." >&2; exit 1; }
  if [[ -f /etc/vexlyx/vexlyx.env ]]; then
    docker compose --env-file /etc/vexlyx/vexlyx.env -f docker-compose.yml -f docker-compose.prod.yml stop api
  fi
  migration_script="$(mktemp)"
  git show FETCH_HEAD:system/python/mail_state_migrate.py > "$migration_script"
  python3 "$migration_script" --source "${VEXLYX_HOME}" --state-root "$state_dir"
  rm -f "$migration_script"
  # Only verified, backed-up generated files are reset; unrelated source changes were rejected above.
  local file
  for file in "${runtime_files[@]}"; do
    if git ls-files --error-unmatch "$file" >/dev/null 2>&1; then git restore --worktree -- "$file"; fi
  done
}


# Edits to tracked files: the only local changes an upgrade has to protect.
# Untracked files (a pnpm store, build output) and mode-only changes never get
# in the way of a checkout. v0.3.x servers have the latter on tracked
# OpenDKIM key files, because the Postfix entrypoint ran chmod -R on them.
# Defined after prepare_mail_upgrade, which calls it, so that
# system/python/test_mail_upgrade.py (it runs that function's text on its own)
# still receives it.
source_changes() {
  git -c core.fileMode=false status --porcelain --untracked-files=no 2>/dev/null
}

ensure_git() {
  if ! command -v git >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y --no-install-recommends git ca-certificates
  fi
}

# Fresh install: clone the chosen tag or branch into VEXLYX_HOME.
fresh_checkout() {
  resolve_target
  log "Cloning Vexlyx $(describe_target) into ${VEXLYX_HOME}..."
  install -d -m 0755 "$(dirname "${VEXLYX_HOME}")"
  git -c advice.detachedHead=false clone --quiet --branch "${TARGET_NAME}" --depth 1 \
    "${VEXLYX_REPO_URL}" "${VEXLYX_HOME}"
}

# Moves an existing checkout to the chosen tag or branch. Never touches a
# checkout with local changes. Runs from inside VEXLYX_HOME.
update_checkout() {
  if [[ ! -d .git ]]; then
    log "${VEXLYX_HOME} is not a git checkout — leaving it untouched, not updating."
    return 0
  fi
  if [[ -n "$(source_changes)" ]] &&
     [[ -z "$(git ls-files -- docker/postfix/config/virtual_domains docker/postfix/config/virtual_mailbox_maps docker/postfix/config/virtual_alias_maps docker/dovecot/config/users docker/postfix/opendkim/KeyTable docker/postfix/opendkim/SigningTable docker/postfix/opendkim/TrustedHosts)" ]]; then
    log "Local changes detected in ${VEXLYX_HOME} — leaving them as-is, not pulling."
    if git status --porcelain -- docker/dovecot/config/users 2>/dev/null | grep -q .; then
      log "docker/dovecot/config/users is a tracked file in this older version. To upgrade, follow"
      log "docs/dev/email/mail-credential-remediation.md (it removes publicly known mailbox credentials)."
    fi
    return 0
  fi

  local current_branch
  current_branch="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"

  if [[ -z "${VEXLYX_REPO_REF:-}" && -n "${current_branch}" ]]; then
    # An install that follows a branch keeps following it; switching to
    # releases is an explicit choice (VEXLYX_REPO_REF=latest).
    log "Following branch ${current_branch}. Set VEXLYX_REPO_REF=latest to switch to tagged releases."
    TARGET_KIND="branch"
    TARGET_NAME="${current_branch}"
  else
    resolve_target
  fi

  if [[ "${TARGET_KIND}" == "tag" ]]; then
    local current_tag
    current_tag="$(git describe --tags --exact-match 2>/dev/null || true)"
    if [[ "${current_tag}" == "${TARGET_NAME}" ]]; then
      if [[ -n "$(source_changes)" ]]; then
        log "Local changes detected in ${VEXLYX_HOME} — leaving them as-is, not pulling."
        log "For exposed legacy mailbox credentials, follow docs/dev/email/mail-credential-remediation.md."
      else
        log "Already on release ${TARGET_NAME}."
      fi
      return 0
    fi
    log "Updating to release ${TARGET_NAME}..."
    git fetch --quiet --depth 1 origin "refs/tags/${TARGET_NAME}:refs/tags/${TARGET_NAME}"
    prepare_mail_upgrade
    git -c core.fileMode=false -c advice.detachedHead=false checkout --quiet "refs/tags/${TARGET_NAME}"
  else
    log "Updating to the latest ${TARGET_NAME} (development branch)..."
    git fetch origin "${TARGET_NAME}"
    prepare_mail_upgrade
    git -c core.fileMode=false checkout "${TARGET_NAME}"
    git -c core.fileMode=false pull --ff-only origin "${TARGET_NAME}"
  fi
}

main() {
  VEXLYX_HOME="${VEXLYX_HOME:-/opt/vexlyx}"
  VEXLYX_REPO_URL="${VEXLYX_REPO_URL:-https://github.com/atlantiqshq/vexlyx.git}"

  if [[ ${EUID} -ne 0 ]]; then
    echo "[ERROR] This installer must be run as root (or with sudo)." >&2
    exit 1
  fi

  if is_vexlyx_checkout "$(pwd)"; then
    # Already running from inside a Vexlyx checkout — use it as-is.
    VEXLYX_HOME="$(pwd)"
  elif is_vexlyx_checkout "${VEXLYX_HOME}"; then
    log "Found existing Vexlyx checkout at ${VEXLYX_HOME}."
    cd "${VEXLYX_HOME}"
    update_checkout
  elif [[ -e "${VEXLYX_HOME}" ]]; then
    echo "[ERROR] ${VEXLYX_HOME} already exists but is not a Vexlyx checkout." >&2
    echo "        Refusing to overwrite it. Set VEXLYX_HOME to a different path and re-run." >&2
    exit 1
  else
    ensure_git
    fresh_checkout
    cd "${VEXLYX_HOME}"
  fi

  export VEXLYX_HOME VEXLYX_REPO_URL
  if [[ -n "${TARGET_NAME:-}" ]]; then
    export VEXLYX_REPO_REF="${TARGET_NAME}"
  fi
  cd "${VEXLYX_HOME}"
  exec bash system/scripts/install/run.sh "$@"
}

# Run main when executed (`bash install.sh`) or piped (`curl ... | bash`, where
# BASH_SOURCE is empty); do nothing when sourced, so the functions above can be
# tested in isolation.
if [[ -z "${BASH_SOURCE[0]:-}" || "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi

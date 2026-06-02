#!/usr/bin/env bash
set -euo pipefail

# BridgeMix launcher / installer — friendly, no docs required.
#
# Just run it (double-click → "Run in Terminal", or `./setup.sh`). You get a menu:
#   • Install & Launch — set things up, add BridgeMix to your apps menu, start it
#   • Launch           — start it without adding a menu entry
#   • Uninstall        — remove the apps-menu entry
#
# Backend is automatic: a conda env if you have conda, otherwise a normal Python
# venv (.venv). Force one with BRIDGEMIX_BACKEND=conda|venv. Non-interactive
# (e.g. launched from the apps menu) it installs & launches without prompting.
# Flags: --install | --launch | --uninstall | --help

APP_ID="io.github.ex0danify.BridgeMix"
LEGACY_IDS=("com.skyfire_networks.BridgeMix")   # cleaned up on uninstall
ENV_NAME="bridgemix"
PY_MIN_MINOR=11
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

PY=() ; PIP=() ; BACKEND=""

# ── Colours (only when writing to a real terminal) ────────────────────────────
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    BOLD=$'\e[1m'; DIM=$'\e[2m'; RESET=$'\e[0m'
    ORANGE=$'\e[38;5;208m'; GREEN=$'\e[32m'; RED=$'\e[31m'; GRAY=$'\e[90m'
else
    BOLD='' ; DIM='' ; RESET='' ; ORANGE='' ; GREEN='' ; RED='' ; GRAY=''
fi
trap 'printf "\e[?25h" 2>/dev/null || true' EXIT   # always restore the cursor

banner() {   # drawn to stderr so it never pollutes captured output
    printf '\n  %sBridge%s%s%sMix%s   %s· Roland Bridge Cast controller%s\n' \
        "$BOLD" "$RESET" "$BOLD" "$ORANGE" "$RESET" "$GRAY" "$RESET" >&2
    printf '  %s────────────────────────────────────────%s\n' "$GRAY" "$RESET" >&2
}

# Run a slow step with a spinner; hide its output unless it fails.
run_step() {
    local msg="$1"; shift
    if [[ ! -t 1 ]]; then echo "[bridgemix] $msg"; "$@"; return; fi
    local log spin='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏' i=0
    log="$(mktemp)"
    printf '  %s%s%s  ' "$DIM" "$msg" "$RESET"
    ( "$@" ) >"$log" 2>&1 &
    local pid=$!
    while kill -0 "$pid" 2>/dev/null; do
        printf '\b%s' "${spin:i++%${#spin}:1}"; sleep 0.1
    done
    if wait "$pid"; then
        printf '\b%s✓%s\n' "$GREEN" "$RESET"; rm -f "$log"
    else
        printf '\b%s✗%s\n' "$RED" "$RESET"
        echo "  ${RED}Something went wrong:${RESET}"; tail -n 25 "$log"; rm -f "$log"
        exit 1
    fi
}

# Like run_step but non-fatal: returns the command's exit code and leaves the
# captured output in $STEP_LOG for the caller to inspect or show.
STEP_LOG=""
run_soft() {
    local msg="$1"; shift
    [[ -n "$STEP_LOG" ]] && rm -f "$STEP_LOG"
    STEP_LOG="$(mktemp)"
    if [[ ! -t 1 ]]; then echo "[bridgemix] $msg"; "$@" >"$STEP_LOG" 2>&1; return $?; fi
    local spin='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏' i=0
    printf '  %s%s%s  ' "$DIM" "$msg" "$RESET"
    ( "$@" ) >"$STEP_LOG" 2>&1 &
    local pid=$!
    while kill -0 "$pid" 2>/dev/null; do
        printf '\b%s' "${spin:i++%${#spin}:1}"; sleep 0.1
    done
    if wait "$pid"; then printf '\b%s✓%s\n' "$GREEN" "$RESET"; return 0
    else printf '\b%s✗%s\n' "$RED" "$RESET"; return 1; fi
}

show_step_error() {
    echo "  ${RED}Something went wrong:${RESET}"; tail -n 25 "$STEP_LOG"
}

# ── Backend discovery ─────────────────────────────────────────────────────────

find_conda() {
    if command -v conda &>/dev/null; then command -v conda; return 0; fi
    local c
    for c in "$HOME/miniconda3/bin/conda" "$HOME/anaconda3/bin/conda" \
             "/opt/miniconda3/bin/conda" "/opt/anaconda3/bin/conda" \
             "/usr/local/miniconda3/bin/conda"; do
        [[ -x "$c" ]] && { echo "$c"; return 0; }
    done
    return 1
}

# First python3 that actually runs and is >= 3.$PY_MIN_MINOR. Prefer versions
# with full prebuilt-wheel coverage (3.11/3.12) over 3.13+ where python-rtmidi
# has no wheel yet. Invoking each candidate skips broken/old ones.
find_python() {
    local cand
    for cand in python3.11 python3.12 python3.13 python3 python; do
        command -v "$cand" &>/dev/null || continue
        if "$cand" -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, ${PY_MIN_MINOR}) else 1)" &>/dev/null; then
            command -v "$cand"; return 0
        fi
    done
    return 1
}

# ── Build-tools handling (for compiling python-rtmidi on newer Pythons) ───────
# python-rtmidi ships wheels for 3.11/3.12; on 3.13+ pip must compile it, which
# needs a C compiler, ALSA dev headers and Python dev headers.

# Best-effort check that the toolchain to build python-rtmidi is present.
# $1 = the (system) python interpreter whose dev headers we'd compile against.
have_build_tools() {
    local py="$1" inc
    command -v cc &>/dev/null || command -v gcc &>/dev/null || command -v clang &>/dev/null || return 1
    [[ -f /usr/include/alsa/asoundlib.h ]] || return 1
    inc="$("$py" -c 'import sysconfig; print(sysconfig.get_path("include"))' 2>/dev/null || true)"
    [[ -n "$inc" && -f "$inc/Python.h" ]] || return 1
    return 0
}

# Echo the distro's package-install command (sans sudo), or empty if unknown.
# Detection is by package manager, so derivatives (Mint, Pop!_OS, Nobara,
# Manjaro, EndeavourOS …) are covered by their base.
build_tools_install_cmd() {
    if   command -v apt-get      &>/dev/null; then echo "apt-get install -y build-essential python3-dev libasound2-dev"
    elif command -v dnf          &>/dev/null; then echo "dnf install -y gcc make python3-devel alsa-lib-devel"
    elif command -v yum          &>/dev/null; then echo "yum install -y gcc make python3-devel alsa-lib-devel"
    elif command -v zypper       &>/dev/null; then echo "zypper install -y gcc make python3-devel alsa-devel"
    elif command -v pacman       &>/dev/null; then echo "pacman -S --needed --noconfirm base-devel python alsa-lib"
    elif command -v apk          &>/dev/null; then echo "apk add build-base python3-dev alsa-lib-dev"
    elif command -v xbps-install &>/dev/null; then echo "xbps-install -Sy gcc make python3-devel alsa-lib-devel"
    elif command -v eopkg        &>/dev/null; then echo "eopkg install -y -c system.devel alsa-lib-devel"
    else echo ""
    fi
}

# Explain the missing build tools and, interactively, offer to install them.
offer_build_tools() {
    local pyver="$1" cmd
    cmd="$(build_tools_install_cmd)"
    echo "" >&2
    echo "  ${BOLD}python-rtmidi needs to be compiled${RESET} ${GRAY}(no prebuilt wheel for Python $pyver)${RESET}" >&2
    echo "  ${GRAY}That needs a C compiler, ALSA dev headers and Python dev headers.${RESET}" >&2
    if [[ -z "$cmd" ]]; then
        echo "  ${GRAY}Couldn't recognise your package manager — install those three" >&2
        echo "  with your distro's tools, then re-run setup.sh.${RESET}" >&2
        return 0
    fi
    echo "  ${BOLD}Suggested:${RESET} ${GRAY}sudo $cmd${RESET}" >&2
    if [[ -t 0 && -t 2 ]]; then
        printf '  Install them now (uses sudo)? %s[Y/n]%s ' "$DIM" "$RESET" >&2
        local ans=""; IFS= read -r ans || true
        if [[ "${ans:-Y}" =~ ^[Nn] ]]; then
            echo "  ${GRAY}Skipped — run the command above, then re-run setup.sh.${RESET}" >&2
        else
            echo "  ${GRAY}You may be prompted for your password…${RESET}" >&2
            sudo sh -c "$cmd" || echo "  ${RED}Package install failed — see the output above.${RESET}" >&2
        fi
    else
        echo "  ${GRAY}(non-interactive — run the command above, then re-run setup.sh)${RESET}" >&2
    fi
}

# Install BridgeMix into the venv; if the build fails for want of tools, offer
# to install them and retry once.
install_into_venv() {
    local py="$1" pyver="$2"
    if run_soft "Installing BridgeMix…" "$VENV_DIR/bin/pip" install -e "$SCRIPT_DIR"; then
        rm -f "$STEP_LOG"; return 0
    fi
    if ! have_build_tools "$py"; then
        offer_build_tools "$pyver"
        if run_soft "Building BridgeMix…" "$VENV_DIR/bin/pip" install -e "$SCRIPT_DIR"; then
            rm -f "$STEP_LOG"; return 0
        fi
    fi
    show_step_error; rm -f "$STEP_LOG"
    exit 1
}

setup_conda() {
    local conda="$1"
    BACKEND="conda"
    if ! "$conda" env list 2>/dev/null | grep -qE "^${ENV_NAME}[[:space:]]"; then
        echo "  ${BOLD}First-time setup${RESET} ${GRAY}(this can take a minute)${RESET}"
        run_step "Creating environment…"     "$conda" create -n "$ENV_NAME" "python=3.${PY_MIN_MINOR}" -y
        run_step "Installing BridgeMix…"      "$conda" run -n "$ENV_NAME" pip install -e "$SCRIPT_DIR"
    fi
    PY=("$conda" run -n "$ENV_NAME" python)
    PIP=("$conda" run -n "$ENV_NAME" pip)
}

setup_venv() {
    local py
    if ! py="$(find_python)"; then
        echo "  ${RED}Python 3.${PY_MIN_MINOR}+ not found and no conda.${RESET}" >&2
        echo "  Install Python 3 (and 'python3-venv' on Debian/Ubuntu), then try again." >&2
        exit 1
    fi
    local pyver
    pyver="$("$py" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo '?')"
    BACKEND="venv"
    if [[ ! -x "$VENV_DIR/bin/python" ]]; then
        echo "  ${BOLD}First-time setup${RESET} ${GRAY}(this can take a minute)${RESET}"
        if ! "$py" -m venv "$VENV_DIR" 2>/dev/null; then
            echo "  ${RED}Could not create the Python environment.${RESET}" >&2
            echo "  On Debian/Ubuntu run:  sudo apt install python3-venv" >&2
            exit 1
        fi
        "$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null 2>&1 || true
        install_into_venv "$py" "$pyver"
    fi
    PY=("$VENV_DIR/bin/python")
    PIP=("$VENV_DIR/bin/pip")
}

setup_backend() {
    local conda_exe
    case "${BRIDGEMIX_BACKEND:-}" in
        conda) conda_exe="$(find_conda)" || { echo "  ${RED}BRIDGEMIX_BACKEND=conda but conda not found.${RESET}" >&2; exit 1; }
               setup_conda "$conda_exe";;
        venv)  setup_venv;;
        *)     if conda_exe="$(find_conda)"; then setup_conda "$conda_exe"; else setup_venv; fi;;
    esac
    # Keep the env pointed at THIS folder (handles a moved/renamed/cloned copy).
    local expected_src current_src
    expected_src="$(realpath "$SCRIPT_DIR/src")"
    current_src="$("${PY[@]}" -c \
        'import os, bridgemix; print(os.path.dirname(os.path.dirname(os.path.realpath(bridgemix.__file__))))' \
        2>/dev/null || true)"
    if [[ "$current_src" != "$expected_src" ]]; then
        run_step "Linking this copy…" "${PIP[@]}" install -e "$SCRIPT_DIR"
    fi
}

# ── Desktop (apps-menu) integration ───────────────────────────────────────────

install_desktop_integration() {
    local data_dir="${XDG_DATA_HOME:-$HOME/.local/share}"
    local apps_dir="$data_dir/applications"
    local icons_dir="$data_dir/icons/hicolor/scalable/apps"
    local desktop_dst="$apps_dir/$APP_ID.desktop"
    local desktop_src="$SCRIPT_DIR/assets/$APP_ID.desktop"
    local icon_src="$SCRIPT_DIR/assets/icon.svg"
    # The menu entry launches directly (--launch): skips the menu + desktop reinstall,
    # just sets up the env and starts. Still routed through setup.sh so it
    # self-heals if the folder moves.
    local launcher="$SCRIPT_DIR/setup.sh --launch"
    [[ -f "$desktop_src" && -f "$icon_src" ]] || return 0
    if [[ -f "$desktop_dst" && "$desktop_dst" -nt "$desktop_src" \
          && "$desktop_dst" -nt "$icon_src" ]] \
       && grep -qF "Exec=$launcher" "$desktop_dst"; then
        return 0
    fi
    mkdir -p "$apps_dir" "$icons_dir"
    cp -f "$icon_src" "$icons_dir/$APP_ID.svg"
    sed "s|@LAUNCHER@|$launcher|g" "$desktop_src" > "$desktop_dst"
    update-desktop-database "$apps_dir" >/dev/null 2>&1 || true
    kbuildsycoca6 >/dev/null 2>&1 || kbuildsycoca5 >/dev/null 2>&1 || true
    echo "  ${GREEN}✓${RESET} Added BridgeMix to your apps menu"
}

remove_desktop_integration() {
    local data_dir="${XDG_DATA_HOME:-$HOME/.local/share}"
    local apps_dir="$data_dir/applications"
    local icons_dir="$data_dir/icons/hicolor/scalable/apps"
    local removed=0 id f
    for id in "$APP_ID" "${LEGACY_IDS[@]}"; do
        for f in "$apps_dir/$id.desktop" "$icons_dir/$id.svg"; do
            [[ -e "$f" ]] && { rm -f "$f"; removed=1; }
        done
    done
    if (( removed )); then
        update-desktop-database "$apps_dir" >/dev/null 2>&1 || true
        kbuildsycoca6 >/dev/null 2>&1 || kbuildsycoca5 >/dev/null 2>&1 || true
        echo "  ${GREEN}✓${RESET} Removed BridgeMix from your apps menu"
        echo "  ${GRAY}(the environment in .venv / conda is left untouched)${RESET}"
    else
        echo "  ${GRAY}BridgeMix wasn't in your apps menu — nothing to remove.${RESET}"
    fi
}

# ── Keyboard menu ─────────────────────────────────────────────────────────────
# ↑/↓ or j/k to move, Enter to choose, q/Esc to quit. UI → stderr; index → stdout.

menu_select() {
    local prompt="$1"; shift
    local options=("$@") n=$# sel=0 key rest i
    printf '\e[?25l' >&2
    trap 'printf "\e[?25h" >&2' RETURN
    printf '%s\n' "$prompt" >&2
    while true; do
        for ((i = 0; i < n; i++)); do
            if (( i == sel )); then
                printf '   %s%s ▸ %s %s\e[K\n' "$ORANGE" "$BOLD" "${options[i]}" "$RESET" >&2
            else
                printf '     %s%s%s\e[K\n' "$DIM" "${options[i]}" "$RESET" >&2
            fi
        done
        IFS= read -rsn1 key || true
        if [[ $key == $'\e' ]]; then
            read -rsn2 -t 0.1 rest || true
            key+="$rest"
        fi
        case "$key" in
            $'\e[A'|k) (( sel = (sel - 1 + n) % n ));;
            $'\e[B'|j) (( sel = (sel + 1) % n ));;
            ''|$'\n'|$'\r') printf '%s' "$sel"; return 0;;
            q|$'\e') return 1;;
        esac
        printf '\e[%dA' "$n" >&2
    done
}

# ── Action resolution: flags → non-interactive default → menu ─────────────────

choose_action() {
    for arg in "$@"; do
        case "$arg" in
            --install|--auto|-y)             echo install;   return 0;;
            --launch|--play|--no-desktop)    echo launch;    return 0;;
            --uninstall|--remove)            echo uninstall; return 0;;
            -h|--help)
                echo "usage: setup.sh [--install | --launch | --uninstall]" >&2
                echo "  no args (in a terminal): shows the menu" >&2
                echo quit; return 0;;
        esac
    done
    # Interactive only if we can read keys (stdin) AND draw the UI (stderr).
    # NOTE: stdout is a pipe here (this runs inside $()), so never test fd 1.
    [[ ! -t 0 || ! -t 2 ]] && { echo install; return 0; }   # no terminal: just go
    banner
    local idx
    idx="$(menu_select "  ${GRAY}↑/↓ to move · Enter to choose · Q to quit${RESET}" \
        "Install & Launch  —  add to apps menu, then start" \
        "Launch            —  start (no menu entry)" \
        "Uninstall         —  remove the apps-menu entry" \
        "Quit")" || { echo quit; return 0; }
    case "$idx" in
        0) echo install;; 1) echo launch;; 2) echo uninstall;; *) echo quit;;
    esac
}

# ── Main ──────────────────────────────────────────────────────────────────────

case "$(choose_action "$@")" in
    quit)
        echo "  ${GRAY}Bye!${RESET}"; exit 0;;
    uninstall)
        remove_desktop_integration; exit 0;;
    install)
        setup_backend
        install_desktop_integration
        echo "  ${GREEN}✓ Ready${RESET} — starting BridgeMix… ${GRAY}(${BACKEND})${RESET}"
        exec "${PY[@]}" -m bridgemix;;
    launch)
        setup_backend
        echo "  ${GREEN}✓ Ready${RESET} — starting BridgeMix… ${GRAY}(${BACKEND})${RESET}"
        exec "${PY[@]}" -m bridgemix;;
esac

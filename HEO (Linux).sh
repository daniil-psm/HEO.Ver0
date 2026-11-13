#!/usr/bin/env bash
set -euo pipefail

heo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Doppelklick startet ohne Terminal; Ausgabe und Fehler bleiben im Projektprotokoll.
if [[ $# == 0 && -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    mkdir -p -- "$heo_root/.heo-runtime/logs"
    heo_log="$heo_root/.heo-runtime/logs/start-$(date +%Y%m%d-%H%M%S)-$$.log"
    HEO_GUI_START=1 nohup bash "$heo_root/HEO (Linux).sh" --open-existing >"$heo_log" 2>&1 < /dev/null &
    exit 0
fi

heo_run() {
    if [[ $# == 0 ]]; then
        set -- --open-existing
    fi
    for heo_python in "$heo_root/.venv-linux/bin/python" python3.12 python3; do
        if "$heo_python" -I -c 'import ensurepip, struct, sys, venv; sys.exit(0 if sys.version_info[:2] == (3, 12) and struct.calcsize("P") == 8 else 1)' 2>/dev/null; then
            exec "$heo_python" -X utf8 -I "$heo_root/heo/application/launcher.py" "$@"
        fi
    done
    exec bash "$heo_root/heo/application/bootstrap_linux.sh" "$@"
}

if [[ "${HEO_GUI_START:-0}" == 1 ]]; then
    set +e
    (heo_run "$@")
    heo_status=$?
    if [[ $heo_status != 0 && $heo_status != 130 ]]; then
        heo_message="HEO konnte nicht geöffnet werden. Bitte erneut versuchen. Details stehen im Projektordner unter .heo-runtime/logs."
        if command -v zenity >/dev/null 2>&1; then
            zenity --error --title="HEO – Start fehlgeschlagen" --text="$heo_message"
        elif command -v kdialog >/dev/null 2>&1; then
            kdialog --error "$heo_message" --title "HEO"
        elif command -v xmessage >/dev/null 2>&1; then
            xmessage -center "$heo_message"
        else
            notify-send "HEO – Start fehlgeschlagen" "$heo_message" 2>/dev/null || true
            xdg-open "$heo_root/.heo-runtime/logs" 2>/dev/null || true
        fi
    fi
    exit "$heo_status"
fi

heo_run "$@"

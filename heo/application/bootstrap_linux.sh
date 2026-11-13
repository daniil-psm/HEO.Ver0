#!/usr/bin/env bash
# Dieser Teil muss auch auf Rechnern ohne Python funktionieren.
set -euo pipefail

heo_application="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
heo_root="$(cd -- "$heo_application/../.." && pwd)"

case "${1:-}" in
    --check)
        echo "HEO: Keine verwendbare Python-Umgebung vorhanden. Normal starten, um Python automatisch einzurichten." >&2
        exit 1
        ;;
    --help|-h)
        echo 'HEO: "HEO (Linux).sh" [--setup-only | --check]'
        echo "Beim ersten normalen Start werden fehlendes Python 3.12 und die App-Pakete automatisch eingerichtet."
        exit 0
        ;;
esac

if [[ "$(uname -m)" != "x86_64" ]]; then
    echo "Der automatische Python-Download unter Linux unterstuetzt derzeit x86_64." >&2
    exit 1
fi

# Version und Prüfsumme kommen aus derselben festen Downloadvorgabe.
heo_version=""
heo_expected_hash=""
while IFS='=' read -r heo_key heo_value; do
    case "$heo_key" in
        UV_VERSION) heo_version="$heo_value" ;;
        UV_LINUX_X86_64_SHA256) heo_expected_hash="$heo_value" ;;
    esac
done < "$heo_application/uv.env"
if [[ ! "$heo_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ || ! "$heo_expected_hash" =~ ^[0-9a-f]{64}$ ]]; then
    echo "Die Download-Konfiguration heo/application/uv.env fehlt oder ist ungueltig." >&2
    exit 1
fi

heo_runtime="$heo_root/.heo-runtime/linux-x86_64"
heo_uv="$heo_runtime/uv-$heo_version/uv"
if [[ -L "$heo_root/.heo-runtime" || -L "$heo_runtime" ]]; then
    echo "HEO: Der Laufzeitordner darf keine Verknuepfung auf eine andere Installation sein." >&2
    exit 1
fi
mkdir -p -- "$heo_runtime"

# Erst nach erfolgreicher Integritätsprüfung darf das heruntergeladene Werkzeug verwendet werden.
if [[ ! -x "$heo_uv" ]]; then
    for heo_tool in sha256sum tar mktemp; do
        if ! command -v "$heo_tool" >/dev/null 2>&1; then
            echo "HEO: Fuer den ersten Python-Download fehlt das Systemwerkzeug $heo_tool." >&2
            exit 1
        fi
    done
    heo_temporary="$(mktemp -d "$heo_runtime/download.XXXXXXXX")"
    trap 'rm -rf -- "$heo_temporary"' EXIT
    heo_archive="$heo_temporary/uv.tar.gz"
    heo_url="https://github.com/astral-sh/uv/releases/download/$heo_version/uv-x86_64-unknown-linux-gnu.tar.gz"
    echo "HEO: Lade das Werkzeug fuer die lokale Python-Einrichtung ..."
    if command -v curl >/dev/null 2>&1; then
        curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 --connect-timeout 20 --max-time 300 --output "$heo_archive" "$heo_url"
    elif command -v wget >/dev/null 2>&1; then
        wget --https-only --timeout=30 --tries=2 --quiet --output-document="$heo_archive" "$heo_url"
    else
        echo "HEO: Fuer den ersten Download wird curl oder wget benoetigt." >&2
        exit 1
    fi
    heo_actual_hash="$(sha256sum < "$heo_archive")"
    if [[ "${heo_actual_hash%% *}" != "$heo_expected_hash" ]]; then
        echo "HEO: Die Pruefsumme des Downloads stimmt nicht. Es wird nichts ausgefuehrt. Bitte erneut starten." >&2
        exit 1
    fi
    tar -xzf "$heo_archive" -C "$heo_temporary"
    mkdir -p -- "$(dirname -- "$heo_uv")"
    mv -- "$heo_temporary/uv-x86_64-unknown-linux-gnu/uv" "$heo_uv"
    chmod +x -- "$heo_uv"
    rm -rf -- "$heo_temporary"
    trap - EXIT
fi

# Diese Einstellungen gelten nur fuer diesen Startprozess und seine Kinder.
export UV_PYTHON_INSTALL_DIR="$heo_runtime/python"
export UV_CACHE_DIR="$heo_runtime/cache"
export UV_PYTHON_INSTALL_BIN=0
export UV_PYTHON_INSTALL_REGISTRY=0
export UV_PYTHON_NO_REGISTRY=1

# Der Python-Launcher übernimmt die App-Einrichtung mit dem geprüften lokalen Interpreter.
echo "HEO: Richte Python 3.12 im HEO-Ordner ein ..."
"$heo_uv" --no-config python install 3.12 --no-bin --no-registry --no-cache
heo_python="$("$heo_uv" --no-config python find --managed-python --no-python-downloads 3.12)"
"$heo_python" -I -c 'import ensurepip, struct, sys, venv; sys.exit(0 if sys.version_info[:2] == (3, 12) and struct.calcsize("P") == 8 else 1)'
exec "$heo_python" -X utf8 -I "$heo_application/launcher.py" "$@"

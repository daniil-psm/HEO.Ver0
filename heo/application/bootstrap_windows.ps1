# Dieser Teil laeuft mit Windows PowerShell auch ohne vorhandenes Python.
$ErrorActionPreference = 'Stop'
$heoArguments = @($args)
$heoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$heoTemporary = $null

try {
    if ($heoArguments -contains '--check') {
        throw 'Keine verwendbare Python-Umgebung vorhanden. Normal starten, um Python automatisch einzurichten.'
    }
    if (($heoArguments -contains '--help') -or ($heoArguments -contains '-h')) {
        Write-Host 'HEO: "HEO (Windows).bat" [--setup-only | --check]'
        Write-Host 'Beim ersten normalen Start werden fehlendes Python 3.12 und die App-Pakete automatisch eingerichtet.'
        exit 0
    }
    if (($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') -and ($env:PROCESSOR_ARCHITEW6432 -ne 'AMD64')) {
        throw 'Der automatische Python-Download unter Windows unterstuetzt derzeit x64.'
    }
    # Version und Pruefsumme kommen aus derselben festen Downloadvorgabe.
    $heoSettings = ConvertFrom-StringData -StringData (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'uv.env') -Raw)
    $heoVersion = $heoSettings.UV_VERSION
    $heoExpectedHash = $heoSettings.UV_WINDOWS_X86_64_SHA256
    if (($heoVersion -notmatch '^\d+\.\d+\.\d+$') -or ($heoExpectedHash -notmatch '^[0-9a-f]{64}$')) {
        throw 'Die Download-Konfiguration heo/application/uv.env fehlt oder ist ungueltig.'
    }
    $heoRuntimeRoot = Join-Path $heoRoot '.heo-runtime'
    $heoRuntime = Join-Path $heoRuntimeRoot 'windows-x86_64'
    foreach ($heoDirectory in @($heoRuntimeRoot, $heoRuntime)) {
        if ((Test-Path -LiteralPath $heoDirectory) -and ((Get-Item -LiteralPath $heoDirectory).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Der Laufzeitordner darf keine Verknuepfung auf eine andere Installation sein.'
        }
    }
    $heoUvDirectory = Join-Path $heoRuntime "uv-$heoVersion"
    $heoUv = Join-Path $heoUvDirectory 'uv.exe'
    New-Item -ItemType Directory -Path $heoRuntime -Force | Out-Null

    # Das heruntergeladene Werkzeug erst nach erfolgreicher Integritaetspruefung verwenden.
    if (-not (Test-Path -LiteralPath $heoUv -PathType Leaf)) {
        $heoTemporary = Join-Path $heoRuntime ('download.' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $heoTemporary | Out-Null
        $heoArchive = Join-Path $heoTemporary 'uv.zip'
        $heoUrl = "https://github.com/astral-sh/uv/releases/download/$heoVersion/uv-x86_64-pc-windows-msvc.zip"
        Write-Host 'HEO: Lade das Werkzeug fuer die lokale Python-Einrichtung ...'
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri $heoUrl -OutFile $heoArchive -TimeoutSec 300
        if ((Get-FileHash -LiteralPath $heoArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $heoExpectedHash) {
            throw 'Die Pruefsumme des Downloads stimmt nicht. Es wird nichts ausgefuehrt. Bitte erneut starten.'
        }
        $heoExpanded = Join-Path $heoTemporary 'expanded'
        Expand-Archive -LiteralPath $heoArchive -DestinationPath $heoExpanded
        $heoDownloadedUv = Get-ChildItem -LiteralPath $heoExpanded -Filter 'uv.exe' -Recurse | Select-Object -First 1
        if ($null -eq $heoDownloadedUv) {
            throw 'Der Download enthaelt kein uv.exe.'
        }
        New-Item -ItemType Directory -Path $heoUvDirectory -Force | Out-Null
        Move-Item -LiteralPath $heoDownloadedUv.FullName -Destination $heoUv
    }

    # Nur Prozessvariablen: weder System-PATH noch Registry werden veraendert.
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $heoRuntime 'python'
    $env:UV_CACHE_DIR = Join-Path $heoRuntime 'cache'
    $env:UV_PYTHON_INSTALL_BIN = '0'
    $env:UV_PYTHON_INSTALL_REGISTRY = '0'
    $env:UV_PYTHON_NO_REGISTRY = '1'
    # Der Launcher uebernimmt die App-Einrichtung mit dem geprueften lokalen Interpreter.
    Write-Host 'HEO: Richte Python 3.12 im HEO-Ordner ein ...'
    & $heoUv --no-config python install 3.12 --no-bin --no-registry --no-cache
    if ($LASTEXITCODE -ne 0) { throw 'Python konnte nicht heruntergeladen oder eingerichtet werden. Bitte erneut starten.' }
    $heoPython = & $heoUv --no-config python find --managed-python --no-python-downloads 3.12
    if (($LASTEXITCODE -ne 0) -or (-not $heoPython)) { throw 'Die lokale Python-Laufzeit wurde nicht gefunden.' }
    $heoPython = ([string] $heoPython).Trim()
    & $heoPython -I -c "import ensurepip, struct, sys, venv; sys.exit(0 if sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8 else 1)"
    if ($LASTEXITCODE -ne 0) { throw 'Die heruntergeladene Python-Laufzeit konnte nicht gestartet werden.' }
    & $heoPython -X utf8 -I (Join-Path $PSScriptRoot 'launcher.py') @heoArguments
    exit $LASTEXITCODE
}
catch {
    Write-Host ('HEO konnte nicht gestartet werden: ' + $_.Exception.Message)
    exit 1
}
finally {
    if ($heoTemporary -and (Test-Path -LiteralPath $heoTemporary)) {
        Remove-Item -LiteralPath $heoTemporary -Recurse -Force
    }
}

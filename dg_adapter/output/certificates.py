# Findet DG-Energieausweise und rendert einzelne PDF-Seiten für HEO.

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..input.config_service import DG_SCENARIOS_DIR
from ..shared.scenario_names import validate_scenario_name
from ..shared.dg_paths import objective_dir
from . import DGResultError, DGResultMissingError

PDF_RENDER_SCRIPT = Path(__file__).with_name("render_pdf_page.ps1")
PDF_PAGE_CACHE = Path(tempfile.gettempdir()) / "heo-certificate-pages"


# Findet den Energieausweis einer geprüften Variante.
def certificate_result_path(
    scenario_name: Any,
    objective: Any | None = None,
    *,
    _variant_path=None,
    _scenarios_root=None,
) -> Path:
    root = _scenarios_root if _scenarios_root is not None else DG_SCENARIOS_DIR
    if _variant_path is None:
        from .results_reader import comparison_variant_results_path
        variant_path = comparison_variant_results_path
    else:
        variant_path = _variant_path
    name = validate_scenario_name(scenario_name)
    selected = objective if objective is not None and str(objective).strip() else (
        "economic" if (objective_dir(root / name, "economic") / "manifest.json").is_file()
        else "ecological"
    )
    result_root = variant_path(name, selected)
    expected_path = result_root / f"Quartiersenergieausweis_{name}.pdf"
    if expected_path.is_file():
        return expected_path

    candidates = [
        path
        for path in result_root.glob("Quartiersenergieausweis_*.pdf")
        if path.is_file()
    ]
    if not candidates:
        raise DGResultMissingError(
            f"Für das Szenario {name!r} wurde noch kein Quartiersenergieausweis erzeugt."
        )
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


# Liest oder rendert PDF-Seiten unter Windows und Linux.
def _run_pdf_renderer(
    mode: str,
    pdf_path: Path,
    *,
    page: int = 1,
    output_path: Path | None = None,
) -> str:
    if os.name == "nt":
        arguments = ["-Mode", mode, "-PdfPath", str(pdf_path)]
        if mode == "render":
            arguments.extend(["-Page", str(page), "-OutputPath", str(output_path)])
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(PDF_RENDER_SCRIPT),
                *arguments,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return completed.stdout.strip()

    if mode == "count":
        completed = subprocess.run(
            ["pdfinfo", str(pdf_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        match = re.search(r"^Pages:\s*(\d+)\s*$", completed.stdout, re.MULTILINE)
        if match is None:
            raise ValueError("pdfinfo hat keine Seitenzahl geliefert.")
        return match.group(1)

    if mode == "render" and output_path is not None:
        with output_path.open("wb") as output_file:
            subprocess.run(
                [
                    "pdftoppm", "-f", str(page), "-l", str(page),
                    "-singlefile", "-png", "-r", "150", str(pdf_path),
                ],
                check=True,
                stdout=output_file,
                stderr=subprocess.PIPE,
                timeout=30,
            )
        return str(output_path)

    raise ValueError(f"Ungültiger PDF-Render-Modus: {mode!r}")


# Ermittelt die Seitenzahl des Energieausweises.
def certificate_page_count(
    scenario_name: Any,
    objective: Any | None = None,
    *,
    _certificate_path=None,
) -> int:
    """Liefert die Seitenzahl des Quartiersenergieausweises."""

    certificate = (_certificate_path or certificate_result_path)(scenario_name, objective).resolve()
    try:
        return int(_run_pdf_renderer("count", certificate))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise DGResultError(
            "Der Quartiersenergieausweis konnte nicht gelesen werden."
        ) from exc


# Erzeugt und puffert eine PNG-Seite des Energieausweises.
def render_certificate_page(
    scenario_name: Any,
    page: Any,
    objective: Any | None = None,
    *,
    _certificate_path=None,
    _page_counter=None,
    _page_cache=None,
) -> Path:
    certificate = (_certificate_path or certificate_result_path)(scenario_name, objective).resolve()
    try:
        page_number = int(page)
    except (TypeError, ValueError) as exc:
        raise DGResultError("Ungültige Seitennummer.") from exc

    page_count = (_page_counter or certificate_page_count)(scenario_name, objective)
    if not 1 <= page_number <= page_count:
        raise DGResultError(
            f"Seite {page_number} liegt außerhalb des Dokuments mit {page_count} Seiten."
        )

    cache = _page_cache if _page_cache is not None else PDF_PAGE_CACHE
    cache.mkdir(parents=True, exist_ok=True)
    cache_name = (
        f"{certificate.stem}-{certificate.stat().st_mtime_ns}-p{page_number}.png"
    )
    cached_page = cache / cache_name
    if cached_page.is_file():
        return cached_page

    temporary_page = cache / f".{cache_name}.{os.getpid()}.tmp"
    try:
        _run_pdf_renderer(
            "render", certificate, page=page_number, output_path=temporary_page
        )
        os.replace(temporary_page, cached_page)
    except (OSError, subprocess.SubprocessError) as exc:
        temporary_page.unlink(missing_ok=True)
        raise DGResultError(
            f"Seite {page_number} des Quartiersenergieausweises konnte nicht dargestellt werden."
        ) from exc
    return cached_page


# Erstellt den Energieausweis ohne den gespeicherten Zahlenstand zu verwerfen.
def create_certificate_best_effort(data: Any, objective: str, *, _progress_marker=None) -> dict[str, str] | None:
    """Erstellt das PDF, ohne ein bereits gespeichertes Optimierungsergebnis zu verwerfen."""

    try:
        data.KPIs.create_certificate(data=data, result_path=data.resultPath)
    except Exception as exc:
        warning = {
            "artifact": "certificate",
            "type": type(exc).__name__,
            "message": str(exc),
        }
        if _progress_marker is not None:
            _progress_marker(
                "ARTIFACT",
                objective,
                "CERTIFICATE",
                "FAILED",
                description="PDF-Zertifikat konnte nicht erstellt werden",
            )
        return warning
    return None

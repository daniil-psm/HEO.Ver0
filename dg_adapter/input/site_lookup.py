# Liest DG-Referenzstandorte und stellt alte Standortimporte bereit.

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

from heo.model.site import (
    GERMANY_TRY_TIMEZONE, LOCATION_MODE_GERMANY, LOCATION_MODE_OTHER,
    LOCATION_MODE_PIDULA, LOCATION_MODES, PIDULA_TIMEZONE,
    automatic_location_timezone, german_location_label, location_mode_from_state,
    normalise_postal_code,
)

APP_ROOT = Path(__file__).resolve().parents[2]
DG_DATA_DIR = APP_ROOT / "dg_backend" / "districtgenerator" / "data"
DG_SITE_DATA_PATH = DG_DATA_DIR / "site_data.txt"
DG_SITE_DATA_KLZ_PATH = DG_DATA_DIR / "site_data_with_KLZ.txt"

# Normalisiert eine Postleitzahl aus den DG-Tabellendaten auf fünf Stellen.
def _normalised_row_zip(value: Any) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(5)


# Liest und puffert die DG-Standorttabelle nach Postleitzahl.
@lru_cache(maxsize=2)
def _read_site_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"DG-Standortdatei nicht gefunden: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            _normalised_row_zip(row.get("Zip")): row
            for row in csv.DictReader(handle, delimiter="\t")
            if row.get("Zip")
        }


# Liefert Standortwerte und TRY-Referenzstadt zu einer deutschen Postleitzahl.
def lookup_german_site(postal_code: Any) -> dict[str, Any]:
    """Liest DG-Standortdaten und die zugehörige TRY-Referenzstadt."""

    canonical_zip = normalise_postal_code(postal_code)
    site_rows = _read_site_rows(DG_SITE_DATA_PATH)
    row = site_rows.get(canonical_zip)
    if row is None:
        raise ValueError(
            f"Die PLZ {canonical_zip} ist nicht in den DG-Standortdaten enthalten."
        )

    reference_row = _read_site_rows(DG_SITE_DATA_KLZ_PATH).get(canonical_zip, {})
    reference_city = str(reference_row.get("Ref_City") or "").strip() or None
    return {
        "zip": canonical_zip,
        "reference_city": reference_city,
        "latitude": float(row["Latitude"]),
        "longitude": float(row["Longitude"]),
        "altitude_m": float(row["Altitude"]),
        "temperature_mean_c": float(row["T_me"]),
        "temperature_design_c": float(row["T_ne"]),
    }

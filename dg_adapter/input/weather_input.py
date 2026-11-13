# Dash-freies Einlesen und Normalisieren von TRY- und EPW-Wetterdateien.

from __future__ import annotations

import base64
import binascii
import re
from typing import Any
import csv
import io
import sys
from pathlib import Path

import pandas as pd

MAX_UPLOADED_WEATHER_BYTES = 25 * 1024 * 1024

TRY_COLUMNS = [
    "RW", "HW", "MM", "DD", "HH", "t", "p", "WR", "WG", "N", "x",
    "RF", "B", "D", "A", "E", "IL",
]
DEFAULT_WEATHER_FILENAME = (
    "Laydbug Tools EST_SA_Vilsandi.Lighthouse.262140_TMYx/"
    "EST_SA_Vilsandi.Lighthouse.262140_TMYx.epw"
)


# Bestimmt den Projektpfad auch für eine als ausführbare Datei verpackte Anwendung.
def app_base_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


DEFAULT_WEATHER_PATH = app_base_path() / "data" / DEFAULT_WEATHER_FILENAME


# Vereinheitlicht Wetterspalten und berechnet Stundenwerte, Tageswerte und Metadaten.
def _normalise_weather_frame(
    frame: pd.DataFrame, *, filename: str, source_format: str,
    metadata: dict | None = None,
) -> dict:
    required = [
        "month", "day", "hour", "temperature_C", "global_horizontal_W_m2",
        "direct_horizontal_W_m2", "diffuse_horizontal_W_m2", "wind_speed_m_s",
        "relative_humidity_pct", "pressure_hPa", "cloud_cover_pct",
    ]
    for column in required:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=required).copy()
    if frame.empty:
        raise ValueError("Die Wetterdatei enthält keine auswertbaren Stundenwerte.")
    frame["hour_index"] = range(len(frame))
    frame["day_index"] = frame["hour_index"] // 24 + 1
    for column in ("global_horizontal_W_m2", "direct_horizontal_W_m2", "diffuse_horizontal_W_m2", "wind_speed_m_s"):
        frame[column] = frame[column].clip(lower=0)
    frame["relative_humidity_pct"] = frame["relative_humidity_pct"].clip(0, 100)
    frame["cloud_cover_pct"] = frame["cloud_cover_pct"].clip(0, 100)
    daily = frame.groupby("day_index", as_index=False).agg(
        month=("month", "first"), day=("day", "first"),
        temperature_mean_C=("temperature_C", "mean"),
        solar_Wh_m2_day=("global_horizontal_W_m2", "sum"),
        direct_solar_Wh_m2_day=("direct_horizontal_W_m2", "sum"),
        diffuse_solar_Wh_m2_day=("diffuse_horizontal_W_m2", "sum"),
        wind_speed_mean_m_s=("wind_speed_m_s", "mean"),
        relative_humidity_mean_pct=("relative_humidity_pct", "mean"),
        pressure_mean_hPa=("pressure_hPa", "mean"),
        cloud_cover_mean_pct=("cloud_cover_pct", "mean"),
    )
    result = {"filename": filename, "source_format": source_format, "n": int(len(frame))}
    hourly = {
        "hour_index": ("hour_index", int), "day_index_hourly": ("day_index", int),
        "month": ("month", int), "day": ("day", int), "hour": ("hour", int),
        "temperature_C": ("temperature_C", float),
        "irradiance_W_m2": ("global_horizontal_W_m2", float),
        "direct_irradiance_W_m2": ("direct_horizontal_W_m2", float),
        "diffuse_irradiance_W_m2": ("diffuse_horizontal_W_m2", float),
        "wind_speed_m_s": ("wind_speed_m_s", float),
        "relative_humidity_pct": ("relative_humidity_pct", float),
        "pressure_hPa": ("pressure_hPa", float), "cloud_cover_pct": ("cloud_cover_pct", float),
    }
    for target, (source, kind) in hourly.items():
        series = frame[source].astype(kind)
        result[target] = series.tolist() if kind is int else series.round(3).tolist()
    daily_fields = {
        "daily_day_index": ("day_index", int), "daily_month": ("month", int),
        "daily_day": ("day", int), "daily_temperature_mean_C": ("temperature_mean_C", float),
        "daily_solar_Wh_m2_day": ("solar_Wh_m2_day", float),
        "daily_direct_solar_Wh_m2_day": ("direct_solar_Wh_m2_day", float),
        "daily_diffuse_solar_Wh_m2_day": ("diffuse_solar_Wh_m2_day", float),
        "daily_wind_speed_mean_m_s": ("wind_speed_mean_m_s", float),
        "daily_relative_humidity_mean_pct": ("relative_humidity_mean_pct", float),
        "daily_pressure_mean_hPa": ("pressure_mean_hPa", float),
        "daily_cloud_cover_mean_pct": ("cloud_cover_mean_pct", float),
    }
    for target, (source, kind) in daily_fields.items():
        series = daily[source].astype(kind)
        result[target] = series.tolist() if kind is int else series.round(3).tolist()
    result.update(
        t_min=float(frame["temperature_C"].min()), t_max=float(frame["temperature_C"].max()),
        t_mean=float(frame["temperature_C"].mean()),
        solar_sum_kWh_m2_a=float(daily["solar_Wh_m2_day"].sum() / 1000),
        solar_max_Wh_m2_day=float(daily["solar_Wh_m2_day"].max()),
    )
    result.update(metadata or {})
    return result


# Liest TRY-Wettertext und übersetzt dessen Spalten in das gemeinsame Wettermodell.
def parse_try_text(text: str, filename: str) -> dict:
    if not text:
        raise ValueError("Keine Datei übergeben.")
    frame = pd.read_csv(io.StringIO(text), sep=r"\s+", engine="python")
    if any(column not in frame.columns for column in ("MM", "DD", "HH", "t", "B", "D")):
        frame = pd.read_csv(io.StringIO(text), sep=r"\s+", engine="python", names=TRY_COLUMNS, header=0)
    for column in ("MM", "DD", "HH", "t", "p", "WG", "N", "RF", "B", "D"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return _normalise_weather_frame(pd.DataFrame({
        "month": frame["MM"], "day": frame["DD"], "hour": frame["HH"],
        "temperature_C": frame["t"], "global_horizontal_W_m2": frame["B"].clip(lower=0) + frame["D"].clip(lower=0),
        "direct_horizontal_W_m2": frame["B"], "diffuse_horizontal_W_m2": frame["D"],
        "wind_speed_m_s": frame["WG"], "relative_humidity_pct": frame["RF"],
        "pressure_hPa": frame["p"], "cloud_cover_pct": frame["N"] / 8 * 100,
    }), filename=filename, source_format="TRY")


# Liest EPW-Metadaten und Wetterzeilen und berechnet die effektive Albedo.
def parse_epw_text(text: str, filename: str) -> dict:
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) <= 8 or not rows[0] or rows[0][0].strip().upper() != "LOCATION":
        raise ValueError("Keine gültige EPW-Datei erkannt.")
    location = rows[0]
    epw = pd.DataFrame([row for row in rows[8:] if len(row) >= 35])
    if epw.empty:
        raise ValueError("Die EPW-Datei enthält keine vollständigen Wetterzeilen.")
    ghi = pd.to_numeric(epw[13], errors="coerce")
    diffuse = pd.to_numeric(epw[15], errors="coerce")
    albedo = pd.to_numeric(epw[32], errors="coerce")
    valid = albedo.between(0, 1, inclusive="both")
    weighted = valid & ghi.notna() & ghi.gt(0)
    metadata = {
        "location_name": location[1].strip(), "country_code": location[3].strip(),
        "latitude_deg": float(location[6]), "longitude_deg": float(location[7]),
        "time_zone": float(location[8]), "altitude_m": float(location[9]),
    }
    if valid.any():
        samples = albedo[valid]
        effective = float((albedo[weighted] * ghi[weighted]).sum() / ghi[weighted].sum()) if weighted.any() else float(samples.mean())
        metadata.update(
            albedo=round(effective, 6), albedo_mean=round(float(samples.mean()), 6),
            albedo_min=round(float(samples.min()), 6), albedo_max=round(float(samples.max()), 6),
            albedo_sample_count=int(valid.sum()),
            albedo_method="globalstrahlungsgewichtet" if weighted.any() else "arithmetisches Mittel",
        )
    frame = pd.DataFrame({
        "month": epw[1], "day": epw[2], "hour": epw[3], "temperature_C": epw[6],
        "global_horizontal_W_m2": ghi, "direct_horizontal_W_m2": (ghi - diffuse).clip(lower=0),
        "diffuse_horizontal_W_m2": diffuse, "wind_speed_m_s": epw[21],
        "relative_humidity_pct": epw[8], "pressure_hPa": pd.to_numeric(epw[9], errors="coerce") / 100,
        "cloud_cover_pct": pd.to_numeric(epw[22], errors="coerce") * 10,
    })
    return _normalise_weather_frame(frame, filename=filename, source_format="EPW", metadata=metadata)


# Wählt anhand des Dateiformats den passenden Wetterparser aus.
def parse_weather_text(text: str, filename: str) -> dict:
    suffix = Path(filename or "").suffix.lower()
    first = text.lstrip("\ufeff\r\n ").splitlines()[0] if text.strip() else ""
    return parse_epw_text(text, filename or "Wetterdatei.epw") if suffix == ".epw" or first.upper().startswith("LOCATION,") else parse_try_text(text, filename or "Wetterdatei")


# Dekodiert einen Browser-Upload und übergibt den Text an den Wetterparser.
def parse_weather_upload(contents: str, filename: str) -> dict:
    if not contents:
        raise ValueError("Keine Datei übergeben.")
    _, encoded = contents.split(",", 1)
    return parse_weather_text(base64.b64decode(encoded).decode("utf-8", errors="replace"), filename or "Wetterdatei")


parse_try_upload = parse_weather_upload


# Lädt die voreingestellte Wetterdatei und liefert bei fehlender Datei einen leeren Wetterzustand.
def load_default_weather_file() -> dict | None:
    if not DEFAULT_WEATHER_PATH.exists():
        return None
    return parse_weather_text(DEFAULT_WEATHER_PATH.read_text(encoding="utf-8", errors="replace"), DEFAULT_WEATHER_PATH.name)


DEFAULT_WEATHER_DATA = load_default_weather_file()

# Validiert einen Browser-Upload und bestimmt seinen Szenariopfad.
def _decode_weather_upload(
    weather_upload: dict[str, Any] | None,
    scenario_dir: Path,
) -> tuple[bytes, Path, str] | None:

    if not weather_upload:
        return None

    filename = Path(str(weather_upload.get("filename") or "weather.epw")).name
    if Path(filename).suffix.lower() != ".epw":
        raise ValueError("Für den District Generator kann nur eine EPW-Datei gespeichert werden.")
    filename = re.sub(r"[^A-Za-z0-9._ -]", "_", filename).strip(" .") or "weather.epw"

    contents = str(weather_upload.get("contents") or "")
    if "," not in contents:
        raise ValueError("Die hochgeladene EPW-Datei ist unvollständig.")
    try:
        payload = base64.b64decode(contents.split(",", 1)[1], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Die hochgeladene EPW-Datei konnte nicht dekodiert werden.") from exc

    if len(payload) > MAX_UPLOADED_WEATHER_BYTES:
        raise ValueError("Die EPW-Datei darf höchstens 25 MB groß sein.")
    if not payload.lstrip(b"\xef\xbb\xbf\r\n ").upper().startswith(b"LOCATION,"):
        raise ValueError("Die hochgeladene Datei ist keine gültige EPW-Datei.")

    relative_path = Path("weather") / filename
    return payload, scenario_dir / relative_path, relative_path.as_posix()


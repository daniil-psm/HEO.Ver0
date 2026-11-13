# Verwaltet Profiloptionen, Seeds und Nachfrageprofile für DG-Läufe.
# Ein fester Seed ist unabhängig vom Cache-Schlüssel des vorbereiteten Modells.
# Mehrere Profil-Worker teilen DG-Zufallszustände und sind daher nicht reproduzierbar.
from contextlib import contextmanager
from dataclasses import dataclass, asdict
import hashlib
import os
from pathlib import Path
import random
import re
import secrets
import shutil
import tempfile
import warnings
from threading import RLock

_RNG_LOCK = RLock()

import numpy as np
from dotenv import dotenv_values

from ..shared.dg_paths import seed_control_dir


# Bündelt die szenariospezifischen Optionen der Profilgenerierung.
@dataclass(frozen=True)
class ProfileOptions:
    seed: int = 20261013
    workers: int = 1
    mode: str = 'generate'
    source: Path | None = None

    # Prüft Seed, Workerzahl und die Quelle gespeicherter Profile.
    def __post_init__(self):
        if not 0 <= self.seed < 2**32:
            raise ValueError('PROFILE_SEED muss zwischen 0 und 4294967295 liegen.')
        if self.workers < 1:
            raise ValueError('PROFILE_WORKERS muss mindestens 1 sein.')
        if self.mode not in {'generate', 'saved'}:
            raise ValueError('PROFILE_MODE muss generate oder saved sein.')
        if self.mode == 'saved' and (self.source is None or not self.source.is_dir()):
            raise ValueError('Für saved ist ein vorhandener DG-demands-Ordner erforderlich.')

    # Erstellt einen Fingerprint-tauglichen Schnappschuss inklusive Quelldatei-Hashes.
    def snapshot(self):
        result = asdict(self)
        result['source'] = str(self.source) if self.source else None
        result['files'] = {}
        if self.mode == 'saved':
            result['files'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(self.source.glob('*.csv'))}
            if not result['files']:
                raise ValueError('Der DG-Profilordner enthält keine CSV-Dateien.')
        return result


# Liest die Adaptervorlage und überschreibt sie mit den Szenariooptionen.
def load_profile_options(scenario_dir):
    """Adapter-only env file; never injected into the DG model config."""
    values = dict(dotenv_values(Path(__file__).resolve().parents[1] / '.env.PROFILES'))
    local = seed_control_dir(scenario_dir) / '.env.PROFILES'
    if local.is_file():
        values.update(dotenv_values(local))
    source = values.get('PROFILE_SOURCE')
    if source:
        source = Path(source).expanduser()
        if not source.is_absolute():
            source = Path(scenario_dir) / source
        source = source.resolve()
    return ProfileOptions(int(values['PROFILE_SEED']), int(values['PROFILE_WORKERS']),
                          values['PROFILE_MODE'], source or None)


# Kopiert die Profilvorlage in ein neues Szenario, falls dort noch keine Optionen liegen.
def ensure_profile_options_file(scenario_dir: Path) -> Path:
    """Freeze adapter defaults for a newly prepared scenario."""
    target = seed_control_dir(scenario_dir) / '.env.PROFILES'
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        source = Path(__file__).resolve().parents[1] / '.env.PROFILES'
        target.write_bytes(source.read_bytes())
    return target


# Liest den im Konfigurator gewählten Seedmodus und Seed.
def profile_seed_choice(scenario_dir: Path) -> dict[str, int | str]:
    """Read the editor choice; legacy profile files use the fixed seed."""

    values = dict(dotenv_values(Path(__file__).resolve().parents[1] / '.env.PROFILES'))
    local = seed_control_dir(scenario_dir) / '.env.PROFILES'
    if local.is_file():
        values.update(dotenv_values(local))
    mode = values.get('PROFILE_SEED_MODE') or 'fixed'
    seed = int(values['PROFILE_SEED'])
    validate_profile_seed_choice(mode, seed)
    return {'mode': mode, 'seed': seed}


# Prüft Seedmodus und Zahlenbereich und liefert den ganzzahligen Seed.
def validate_profile_seed_choice(mode: str, seed: int | float | str) -> int:
    if mode not in {'fixed', 'random'}:
        raise ValueError('Seed-Auswahl muss zufällig oder vorgegeben sein.')
    if isinstance(seed, bool):
        raise ValueError('Der Seed muss eine ganze Zahl zwischen 0 und 4294967295 sein.')
    if isinstance(seed, int):
        parsed = seed
    elif isinstance(seed, float) and seed.is_integer():
        parsed = int(seed)
    elif isinstance(seed, str) and re.fullmatch(r'\d+', seed.strip()):
        parsed = int(seed.strip())
    else:
        raise ValueError('Der Seed muss eine ganze Zahl zwischen 0 und 4294967295 sein.')
    if not 0 <= parsed < 2**32:
        raise ValueError('Der Seed muss eine ganze Zahl zwischen 0 und 4294967295 sein.')
    return parsed


# Speichert die Seedwahl atomar und erhält alle anderen Profiloptionen.
def save_profile_seed_choice(scenario_dir: Path, mode: str, seed: int | float | str) -> bool:
    """Preserve other profile options while atomically saving the seed choice."""

    seed = validate_profile_seed_choice(mode, seed)
    target = ensure_profile_options_file(scenario_dir)
    original = target.read_text(encoding='utf-8')
    replacements = {'PROFILE_SEED': str(seed), 'PROFILE_SEED_MODE': mode}
    seen: set[str] = set()
    lines = []
    for line in original.splitlines():
        match = re.match(r'^\s*(?:export\s+)?(PROFILE_SEED|PROFILE_SEED_MODE)\s*=', line)
        if match:
            key = match.group(1)
            if key not in seen:
                lines.append(f'{key}={replacements[key]}')
                seen.add(key)
        else:
            lines.append(line)
    for key, value in replacements.items():
        if key not in seen:
            lines.append(f'{key}={value}')
    content = '\n'.join(lines) + '\n'
    if content == original:
        return False
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', newline='\n', dir=target.parent,
            prefix='.env.PROFILES-', delete=False,
        ) as handle:
            handle.write(content)
            temporary_path = Path(handle.name)
        os.replace(temporary_path, target)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return True


# Wählt für einen neuen Lauf einen vom letzten verschiedenen Seed und speichert ihn.
def renew_random_profile_seed(scenario_dir: Path) -> int:
    """Choose one seed for the next profile generation and persist it first."""

    choice = profile_seed_choice(scenario_dir)
    if choice['mode'] != 'random':
        return int(choice['seed'])
    previous = int(choice['seed'])
    seed = secrets.randbelow(2**32)
    while seed == previous:
        seed = secrets.randbelow(2**32)
    save_profile_seed_choice(scenario_dir, 'random', seed)
    return seed


# Setzt Python- und NumPy-Zufallszustände während der Profilgenerierung temporär.
@contextmanager
def seeded_profiles(seed):
    """Scope both RNGs, including stochastic building initialization."""
    with _RNG_LOCK:
        python_state, numpy_state = random.getstate(), np.random.get_state()
        try:
            random.seed(seed)
            np.random.seed(seed)
            yield
        finally:
            random.setstate(python_state)
            np.random.set_state(numpy_state)


# Prüft und übernimmt gespeicherte Profile oder erzeugt DG-Nachfrageprofile.
# Bei mehreren Workern werden gemeinsame Tabellen vor dem Threadstart geladen.
def generate_demands(data, options, *, gen_cars=True):
    if options.mode == 'saved':
        target = Path(data.resultPath) / 'demands'
        # Validate with DG's own loaders before any demand worker is started.
        expected = int(data.time['dataLength'] / data.time['timeResolution'])
        for building in data.district:
            name = building['unique_name']
            profiles = data.loadProfiles(name, str(options.source), gen_cars=gen_cars)
            heat, cooling = data.loadHeatingProfiles(name, str(options.source))
            for values in (*profiles[:2], *profiles[3:8], heat, cooling):
                array = np.asarray(values)
                if len(array) != expected or not np.isfinite(array).all():
                    raise ValueError(f'Ungültige Profilzeitreihe für {name}: Länge oder Werte passen nicht.')
            minute_values = np.asarray(profiles[2])
            if len(minute_values) != int(data.time["dataLength"] / 60) or not np.isfinite(minute_values).all():
                raise ValueError(f"Ungültiges Minutenprofil für {name}.")
        target.mkdir(parents=True, exist_ok=True)
        for building in data.district:
            for suffix in ('timeseries', 'static', 'timeseries_minutely'):
                name = f"{building['unique_name']}_{suffix}.csv"
                if (options.source / name).resolve() != (target / name).resolve():
                    shutil.copy2(options.source / name, target / name)
    elif options.workers > 1:
        warnings.warn('Mehrere Profil-Worker teilen Zufallszustände; der Seed allein garantiert keine Reproduzierbarkeit.', RuntimeWarning)
        # Loading shared RichardsonPy tables must not consume the model RNG.
        with seeded_profiles(options.seed):
            prime_profile_data()
    data.generateDemands(options.mode == 'generate', options.mode == 'generate',
                         max_threads=options.workers, gen_cars=gen_cars)


# Lädt RichardsonPy-Klassencaches vor dem Start paralleler Profil-Worker.
def prime_profile_data():
    """Initialisiert die RichardsonPy-Klassencaches vor dem Threadstart."""

    from richardsonpy.classes.occupancy import Occupancy
    from richardsonpy.classes.stochastic_el_load_wrapper import ElectricityProfile

    required_week_types = {"wd", "we"}

    if not required_week_types.issubset(Occupancy.occ_start_states):
        # Auch einen eventuell abgebrochenen Teilzustand zuverlässig
        # zurücksetzen, bevor der einzige schreibende Thread lädt.
        Occupancy.occ_start_states = {}
        Occupancy.occ_start_states_loaded = False
        probe = Occupancy(
            number_occupants=1,
            initial_day=1,
            nb_days=1,
            do_profile=True,
        )
        del probe

    if not required_week_types.issubset(ElectricityProfile.activity_statistics):
        ElectricityProfile.activity_statistics = {}
        ElectricityProfile.activity_statistics_loaded = False
        probe = ElectricityProfile.__new__(ElectricityProfile)
        probe._load_activity_statistics()

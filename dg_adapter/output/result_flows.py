# Ordnet die DG-Ergebniscluster für die HEO-Ausgabe in stabiler Reihenfolge.

from __future__ import annotations

from typing import Any

# Stellt die Ergebniscluster über alle Jahre und Cluster bereit.
def _result_clusters(optimization_data: dict | None) -> list[dict]:
    """Liefert alle Ergebniscluster in stabiler Jahr-/Clusterreihenfolge."""

    years = (optimization_data or {}).get("results") or {}
    if not isinstance(years, dict) or not years:
        return []
    sort_key = lambda key: (
        0, int(key)
    ) if str(key).isdigit() else (
        1, str(key)
    )
    return [
        cluster
        for year_key in sorted(years, key=sort_key)
        for year in [years.get(year_key) or {}]
        if isinstance(year, dict)
        for _, cluster in sorted(year.items(), key=lambda item: sort_key(item[0]))
        if isinstance(cluster, dict)
    ]


# Ordnet die Cluster des ersten Jahres und ihre Gewichte den DG-Lösungsdateien zu.
def _sort_key(value: object) -> tuple[int, int | str]:
    text = str(value)
    return (0, int(text)) if text.isdigit() else (1, text)

# Liefert Clustergewichte für Lösungsdateien des ersten Jahres.
def _cluster_schedule(bundle: dict[str, Any]) -> tuple[tuple[str, str, int], ...]:
    results = bundle.get("results") or {}
    if not isinstance(results, dict) or not results:
        return ()
    year = sorted(results, key=_sort_key)[0]
    clusters = results[year]
    if not isinstance(clusters, dict) or not clusters:
        return ()
    representatives = bundle.get("clusters") or []
    weights = bundle.get("cluster_weights") or {}
    schedule = []
    for index, cluster in enumerate(sorted(clusters, key=_sort_key)):
        representative = (
            str(representatives[index])
            if isinstance(representatives, list) and index < len(representatives)
            else str(cluster)
        )
        raw_weight = (
            weights.get(representative, weights.get(str(cluster), 1))
            if isinstance(weights, dict)
            else weights[index] if isinstance(weights, list) and index < len(weights)
            else 1
        )
        try:
            weight = max(1, int(float(raw_weight)))
        except (TypeError, ValueError):
            weight = 1
        schedule.append((str(year), str(cluster), weight))
    return tuple(schedule)

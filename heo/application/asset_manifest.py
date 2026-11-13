"""Browser-Assets in der bisherigen, bewusst festgelegten Lade-Reihenfolge."""

from __future__ import annotations

from pathlib import Path


STYLESHEETS = (
    "shared/annual_series.css",
    "devtools/dev_tools.css",
    "shared/field_system.css",
    "shared/units.css",
    "shared/grid_system.css",
    "shared/main_panel_info.css",
    "configurator/optimization_process.css",
    "configurator/parameter_overview.css",
    "base/scrollbars.css",
    "base/styles.css",
    "base/theme.css",
    "results/topology_overlay.css",
    "topology/topology_scene_nodes.css",
    "configurator/topology_supply.css",
)

SCRIPTS = (
    "shared/browser_lifecycle.js",
    "shared/dashboard_info_flip.js",
    "devtools/dev_tools.js",
    "results/energy_certificate_viewer.js",
    "shared/grid_system.js",
    "shared/form_measure.js",
    "shared/form_layout.js",
    "shared/form_state.js",
    "shared/form_viewports.js",
    "shared/units.js",
    "configurator/konfigurator_angle_control.js",
    "configurator/konfigurator_building_drag.js",
    "configurator/konfigurator_create_transition.js",
    "configurator/konfigurator_details_state.js",
    "configurator/konfigurator_dialog_position.js",
    "configurator/konfigurator_editable_values.js",
    "configurator/konfigurator_scenario_delete_overlay.js",
    "configurator/optimization_process.js",
    "configurator/parameter_help_tooltip.js",
    "base/plotly_theme.js",
    "topology/topology_edge_renderer.js",
    "topology/topology_node_labels.js",
    "topology/topology_overlay_position.js",
    "results/topology_result_interactions.js",
)


def asset_urls(asset_root: Path, paths: tuple[str, ...]) -> list[str]:
    """Erzeugt lokale URLs mit Versionswert, damit geänderte Dateien neu laden."""

    return [
        f"/assets/{path}?m={(asset_root / path).stat().st_mtime_ns}"
        for path in paths
    ]

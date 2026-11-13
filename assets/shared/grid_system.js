(function () {
    "use strict";

    // Aufgelöste CSS-Tracks verwenden, nicht Kachelrechtecke: Auch leere
    // Unterzeilen/-spalten und ungleich breite Gruppen bleiben sichtbar.
    function gridAxis(template, gap) {
        var tracks = Array.from(template.matchAll(/(?:^|\s)([\d.]+)px(?=\s|$)/g), function (match) {
            return Number(match[1]);
        });
        var boundaries = [0];
        var extent = 0;
        tracks.forEach(function (track, index) {
            if (index) {
                extent += gap;
                if (gap) boundaries.push(extent);
            }
            extent += track;
            boundaries.push(extent);
        });
        return {boundaries: boundaries, extent: extent};
    }

    function lineGradient(axis, direction, color) {
        if (!axis.extent) return "none";
        var stops = [];
        axis.boundaries.forEach(function (position, index) {
            // Äußere Linien nach innen zeichnen, ohne Rahmenbreite hinzuzufügen.
            var start = Math.max(0, Math.min(position, axis.extent - 1));
            if (index) stops.push("transparent " + start + "px");
            stops.push(color + " " + start + "px", color + " " + (start + 1) + "px");
            if (index < axis.boundaries.length - 1) stops.push("transparent " + (start + 1) + "px");
        });
        return "linear-gradient(to " + direction + ", " + stops.join(", ") + ")";
    }

    if (typeof module !== "undefined" && module.exports) {
        module.exports = {gridAxis: gridAxis};
    }
    if (typeof document === "undefined") return;

    function refresh(grid) {
        if (!grid.isConnected || !grid.getClientRects().length || grid.closest("[hidden]")) return;
        var style = getComputedStyle(grid);
        var columns = gridAxis(style.gridTemplateColumns, parseFloat(style.columnGap) || 0);
        var rows = gridAxis(style.gridTemplateRows, parseFloat(style.rowGap) || 0);
        var properties = {
            "--heo-dev-grid-left": style.paddingLeft,
            "--heo-dev-grid-top": style.paddingTop,
            "--heo-dev-grid-width": columns.extent + "px",
            "--heo-dev-grid-height": rows.extent + "px",
            "--heo-dev-grid-columns": lineGradient(columns, "right", "var(--heo-grid-main-soft)"),
            "--heo-dev-grid-rows": lineGradient(rows, "bottom", "var(--heo-grid-accent-soft)")
        };
        Object.keys(properties).forEach(function (key) {
            if (grid.style.getPropertyValue(key) !== properties[key]) {
                grid.style.setProperty(key, properties[key]);
            }
        });
    }

    var scheduled = 0;
    var observed = new Set();
    var observer = typeof ResizeObserver === "function" ? new ResizeObserver(function (entries) {
        entries.forEach(function (entry) { refresh(entry.target); });
    }) : null;
    function refreshAll() {
        scheduled = 0;
        observed.forEach(function (grid) {
            if (!grid.isConnected) {
                if (observer) observer.unobserve(grid);
                observed.delete(grid);
            }
        });
        document.querySelectorAll(".heo-field-grid").forEach(function (grid) {
            if (!observed.has(grid)) {
                if (observer) observer.observe(grid);
                observed.add(grid);
            }
            refresh(grid);
        });
    }
    function schedule() {
        if (!scheduled) scheduled = requestAnimationFrame(refreshAll);
    }
    window.HEOFormGrid = {refresh: refresh};
    new MutationObserver(schedule).observe(document.documentElement, {
        subtree: true, childList: true, attributes: true, attributeFilter: ["hidden", "open"]
    });
    window.addEventListener("resize", schedule);
    if (document.fonts) document.fonts.ready.then(schedule);
    schedule();
}());

/* Themewechsel und neue Figuren ohne Server-Callback oder periodisches Polling. */
(function () {
    "use strict";
    var registered = new WeakSet();
    var pending = new WeakSet();
    var applying = new WeakSet();

    function valueAt(object, path) {
        return path.replace(/\[(\d+)\]/g, ".$1").split(".").reduce(function (value, key) {
            return value == null ? undefined : value[key];
        }, object);
    }

    function themePatch(layout, dark) {
        var text = dark ? "#e2eee6" : "#173b26";
        var grid = dark ? "rgba(226,238,230,0.16)" : "rgba(23,59,38,0.18)";
        var background = dark ? "#12221c" : "#fffcf6";
        var update = {};
        function set(path, value) {
            if (valueAt(layout, path) !== value) update[path] = value;
        }
        set("font.color", text);
        set("title.font.color", text);
        set("legend.font.color", text);
        set("legend.title.font.color", text);
        set("hoverlabel.font.color", text);
        set("hoverlabel.bgcolor", background);
        set("hoverlabel.bordercolor", text);
        Object.keys(layout).filter(function (key) {
            return /^[xy]axis\d*$/.test(key);
        }).forEach(function (axis) {
            set(axis + ".color", text);
            set(axis + ".tickfont.color", text);
            set(axis + ".title.font.color", text);
            set(axis + ".gridcolor", grid);
            set(axis + ".zerolinecolor", grid);
            set(axis + ".linecolor", grid);
        });
        (layout.annotations || []).forEach(function (_annotation, index) {
            set("annotations[" + index + "].font.color", text);
        });
        return update;
    }

    function schedule(graph) {
        if (pending.has(graph) || applying.has(graph)) return;
        pending.add(graph);
        window.requestAnimationFrame(function () {
            pending.delete(graph);
            if (!graph.isConnected || !graph.layout || !window.Plotly) return;
            var patch = themePatch(graph.layout, document.documentElement.dataset.theme === "dark");
            if (!Object.keys(patch).length) return;
            applying.add(graph);
            var succeeded = false;
            Promise.resolve().then(function () {
                return window.Plotly.relayout(graph, patch);
            }).then(function () {
                succeeded = true;
            }).catch(function (error) {
                console.warn("Diagramm-Theme konnte nicht aktualisiert werden", error);
            }).finally(function () {
                applying.delete(graph);
                // Ein Themewechsel während relayout darf nicht verloren gehen.
                if (succeeded) schedule(graph);
            });
        });
    }

    function register(graph) {
        if (typeof graph.on !== "function") return;
        if (!registered.has(graph)) {
            registered.add(graph);
            graph.on("plotly_afterplot", function () { schedule(graph); });
        }
        schedule(graph);
    }

    function scan(root) {
        if (root.matches && root.matches(".js-plotly-plot")) register(root);
        if (root.querySelectorAll) root.querySelectorAll(".js-plotly-plot").forEach(register);
    }

    function start() {
        scan(document);
        new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                // Plotly ergänzt seine Klasse erst während des ersten Renderns.
                var parent = mutation.target.closest && mutation.target.closest(".js-plotly-plot");
                if (parent && !registered.has(parent)) register(parent);
                mutation.addedNodes.forEach(scan);
            });
        }).observe(document.body, {childList: true, subtree: true});
        new MutationObserver(function () { scan(document); }).observe(
            document.documentElement, {attributes: true, attributeFilter: ["data-theme"]}
        );
    }
    // Die reine Patch-Funktion ist auch ohne DOM für Regressionstests nutzbar.
    if (typeof module !== "undefined" && module.exports) {
        module.exports = {themePatch: themePatch};
    } else if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
}());

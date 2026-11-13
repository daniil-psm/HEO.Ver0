/* ####################################################################
   ##  ACHTUNG: REKONSTRUIERTE DATEI (22.10.2026)                     ##
   ####################################################################
   Original durch Dateisystemschaden mit Pyomo-Daten ueberschrieben,
   archiviert unter _archiv_beschaedigt_20261022/assets/.
   Wiederhergestellt mit KI-Unterstuetzung (Claude) aus den
   Codex-Protokollen:
   Datei vollstaendig angelegt am 20.10.2026 22:03 (UTC) plus drei
   Aenderungen bis 22:05, Rollout 10/15/rollout-2026-10-15T12-01-04-...
   Pruefung: Ergebnis 4.876 Bytes, exakt gleich gross wie das Original.
   JS-Syntaxpruefung (node --check) bestanden.
   #################################################################### */

/* Hält die Startansicht offen, bis die neue Topologie im Browser fertig ist. */
(function () {
    "use strict";

    let lastButton = null;
    let lastClick = 0;
    let active = false;
    let generation = 0;
    let observer = null;
    let preparing = false;
    let expectedToken = "";

    function dashboard() {
        return document.querySelector(".konfig-dashboard");
    }

    function stopWatching() {
        if (observer) observer.disconnect();
        observer = null;
    }

    function finish() {
        generation += 1;
        active = false;
        preparing = false;
        expectedToken = "";
        stopWatching();
        const root = dashboard();
        if (root) root.classList.remove("is-creating-microgrid");
        if (lastButton && lastButton.isConnected) {
            lastButton.disabled = false;
            lastButton.removeAttribute("aria-busy");
        }
    }

    function begin(button) {
        generation += 1;
        active = true;
        preparing = false;
        expectedToken = "";
        stopWatching();
        const root = dashboard();
        if (root) root.classList.add("is-creating-microgrid");
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
    }

    function svgReady() {
        const canvas = document.querySelector(
            "#konfig-topology-content .konfig-topology-canvas"
        );
        if (!canvas || !expectedToken || canvas.dataset.createToken !== expectedToken) {
            return false;
        }
        const hosts = canvas.querySelectorAll(
            ".topology-edge-host[data-topology-edge-plan]"
        );
        return hosts.length > 0 && Array.from(hosts).every((host) =>
            host.dataset.topologyRenderedPlan === host.dataset.topologyEdgePlan
            && Boolean(host.querySelector("svg.topology-edge-svg"))
        );
    }

    function iconUrls() {
        const workbench = document.getElementById("konfig-workbench");
        if (!workbench) return [];
        const urls = new Set();
        workbench.querySelectorAll(".konfig-action-icon").forEach((icon) => {
            const style = getComputedStyle(icon);
            const mask = style.maskImage || style.webkitMaskImage || "";
            const match = mask.match(/url\(["']?([^"')]+)["']?\)/);
            if (match) urls.add(match[1]);
        });
        return Array.from(urls);
    }

    function preloadIcon(url) {
        return new Promise((resolve) => {
            const image = new Image();
            image.onload = resolve;
            image.onerror = resolve;
            image.src = url;
            if (image.complete) resolve();
        });
    }

    function checkReady() {
        if (!active || preparing || !svgReady()) return;
        preparing = true;
        stopWatching();
        const currentGeneration = generation;
        const resources = iconUrls().map(preloadIcon);
        if (document.fonts) resources.push(document.fonts.ready);
        Promise.all(resources).then(() => {
            requestAnimationFrame(() => requestAnimationFrame(() => {
                if (active && generation === currentGeneration && svgReady()) {
                    finish();
                } else if (active && generation === currentGeneration) {
                    preparing = false;
                    watch();
                }
            }));
        });
    }

    function watch() {
        if (!active) return;
        if (window.HEOTopologyEdges) {
            window.HEOTopologyEdges.renderAll(
                document.getElementById("konfig-topology-content")
            );
        }
        checkReady();
        if (preparing || observer) return;
        observer = new MutationObserver(checkReady);
        observer.observe(document.documentElement, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["data-topology-rendered-plan", "data-create-token"],
        });
    }

    window.HEOCreateTransition = {
        update: function (clicks, result) {
            const button = document.getElementById("konfig-project-next");
            if (!button) {
                if (active) finish();
                return;
            }
            if (button !== lastButton) {
                if (active) finish();
                lastButton = button;
                lastClick = 0;
            }
            const count = Number(clicks) || 0;
            if (count > lastClick) {
                lastClick = count;
                begin(button);
            }
            if (!active || !result || Number(result.clicks) !== count) return;
            if (result.status === "error") finish();
            if (result.status === "success") {
                expectedToken = String(result.token || "");
                watch();
            }
        },
    };
}());

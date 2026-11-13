/* Gemeinsame Label-Logik für die HTML-Nodes aller Topologie-Tabs.
 * Die drei Varianten kommen aus dem zentralen Gerätekatalog. Der Browser
 * wählt erst bei bekannter responsiver Nodegröße: Vollname in Maximalgröße
 * -> definierter Umbruch -> Kürzel; nur das Kürzel darf weiter schrumpfen. */
(function () {
    "use strict";

    const selector = [
        ".topology-scene-node[data-topology-label-full]"
            + ":not([data-topology-label-external='true'])",
        ".konfig-candidate[data-topology-label-full]",
        ".topology-power-pill-label[data-topology-label-full]",
    ].join(", ");
    let framePending = false;

    function candidates(node) {
        const values = [
            node.dataset.topologyLabelFull,
            node.dataset.topologyLabelWrapped,
            node.dataset.topologyLabelShort,
        ].filter(Boolean);
        return values.filter((value, index) => values.indexOf(value) === index);
    }

    function availableSize(node, text) {
        const style = window.getComputedStyle(text);
        const nodeStyle = window.getComputedStyle(node);
        const externalPowerLabel = node.matches(".topology-power-pill-label");
        const widthPercent = parseFloat(style.maxWidth) || 100;
        const heightPercent = parseFloat(style.maxHeight) || 100;
        const contentWidth = Math.max(
            1,
            node.clientWidth
                - (parseFloat(nodeStyle.paddingLeft) || 0)
                - (parseFloat(nodeStyle.paddingRight) || 0),
        );
        const contentHeight = Math.max(
            1,
            node.clientHeight
                - (parseFloat(nodeStyle.paddingTop) || 0)
                - (parseFloat(nodeStyle.paddingBottom) || 0),
        );
        return {
            width: contentWidth * widthPercent / 100,
            // Das separat positionierte AC-/DC-Label ist eine einzeilige
            // Textbox mit automatischer Höhe. clientHeight kann dabei durch
            // Subpixelrundung einen Pixel kleiner als scrollHeight sein und
            // fälschlich sofort das Kürzel wählen. Für diese Labels entscheidet
            // deshalb ausschließlich die reale Pillenbreite.
            height: externalPowerLabel
                ? Number.POSITIVE_INFINITY
                : contentHeight * heightPercent / 100,
        };
    }

    function prepare(text, label, nowrap) {
        text.style.fontSize = "";
        text.style.overflowWrap = "normal";
        text.style.wordBreak = "normal";
        text.style.whiteSpace = nowrap ? "nowrap" : "pre-line";
        text.textContent = label;
    }

    function fits(node, label) {
        const text = node.matches(".topology-power-pill-label")
            ? node
            : node.querySelector(".topology-node-label");
        if (!text) return true;
        prepare(text, label, false);
        // Ein unsichtbarer oder noch nicht vermessener Container wird beim
        // nächsten Resize/Animationsframe erneut geprüft.
        if (node.clientWidth === 0 || node.clientHeight === 0) return true;
        // Die Auswahl darf nicht durch browserseitige Zeichenumbrüche
        // verfälscht werden. Sonst passt der Vollname künstlich immer und die
        // zentral definierte Stufe „Umbruch“ wird nie erreicht.
        const result = text.scrollWidth <= text.clientWidth + 1
            && text.scrollHeight <= text.clientHeight + 1;
        return result;
    }

    function fullLabelAtMaximumSize(node, label) {
        const text = node.matches(".topology-power-pill-label")
            ? node
            : node.querySelector(".topology-node-label");
        if (!text || node.clientWidth === 0 || node.clientHeight === 0) return null;
        // Die Volltext-Stufe ist bewusst einzeilig. Zeilenumbrüche gehören
        // ausschließlich zur nachfolgenden zentral definierten Umbruchstufe.
        prepare(text, label.replace(/\s*\n\s*/g, " "), true);
        const baseSize = parseFloat(window.getComputedStyle(text).fontSize) || 12.5;
        const available = availableSize(node, text);
        const naturalWidth = Math.max(1, text.scrollWidth);
        const naturalHeight = Math.max(1, text.scrollHeight);
        // Die Basisgröße ist die zentrale Maximalgröße. Ein Vollname wird
        // niemals kleinskaliert, denn dann würde er die fest definierte
        // Umbruchstufe überspringen.
        const scale = Math.min(
            1,
            available.width / naturalWidth,
            available.height / naturalHeight,
        );
        if (scale < 1) return null;
        text.style.fontSize = baseSize.toFixed(2) + "px";
        return { label: text.textContent, scale: 1 };
    }

    function scaleShortLabelToFit(node, label) {
        const text = node.matches(".topology-power-pill-label")
            ? node
            : node.querySelector(".topology-node-label");
        if (!text) return 1;
        prepare(text, label, true);
        const baseSize = parseFloat(window.getComputedStyle(text).fontSize) || 12.5;
        const available = availableSize(node, text);
        const scale = Math.min(
            1,
            available.width / Math.max(1, text.scrollWidth),
            available.height / Math.max(1, text.scrollHeight),
        );
        text.style.fontSize = (baseSize * scale).toFixed(2) + "px";
        return scale;
    }

    function updateNode(node) {
        const values = candidates(node);
        if (!values.length) return;
        const text = node.matches(".topology-power-pill-label")
            ? node
            : node.querySelector(".topology-node-label");
        if (!text) return;
        const full = fullLabelAtMaximumSize(node, values[0]);
        if (full) {
            node.dataset.topologyLabelActive = full.label;
            node.dataset.topologyLabelScale = full.scale.toFixed(3);
            return;
        }
        const wrapped = values.slice(1, -1).find((value) => fits(node, value));
        if (wrapped) {
            prepare(text, wrapped, false);
            node.dataset.topologyLabelActive = wrapped;
            node.dataset.topologyLabelScale = "1";
            return;
        }
        const selected = values[values.length - 1];
        const scale = scaleShortLabelToFit(node, selected);
        node.dataset.topologyLabelActive = selected;
        node.dataset.topologyLabelScale = scale.toFixed(3);
    }

    function updateAll(root) {
        (root || document).querySelectorAll(selector).forEach(updateNode);
    }

    function scheduleUpdate() {
        if (framePending) return;
        framePending = true;
        requestAnimationFrame(() => {
            framePending = false;
            updateAll();
        });
    }

    function observe() {
        updateAll();
        if ("ResizeObserver" in window) {
            new ResizeObserver(scheduleUpdate).observe(document.documentElement);
        }
        window.addEventListener("resize", scheduleUpdate, { passive: true });
        new MutationObserver((mutations) => {
            const labelsChanged = mutations.some((mutation) => {
                if (mutation.type === "attributes") return true;
                // updateAll() ersetzt selbst Textknoten. Diese Mutationen
                // dürfen keine weitere vollständige Messrunde auslösen.
                return Array.from(mutation.addedNodes).some((node) =>
                    node instanceof Element
                    && (node.matches(selector) || node.querySelector(selector))
                );
            });
            if (labelsChanged) scheduleUpdate();
        }).observe(document.documentElement, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: [
                "data-topology-label-full",
                "data-topology-label-wrapped",
                "data-topology-label-short",
            ],
        });
        scheduleUpdate();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", observe, { once: true });
    } else {
        observe();
    }

    // Die native Tab-Aufnahme übernimmt die Live-Pixel des Browsers. Das
    // Dev-Tool kann die responsiven Labels unmittelbar vor dem Frame dennoch
    // synchron aktualisieren, damit keine noch ausstehende Messung sichtbar ist.
    window.HEOTopologyLabels = {
        updateAll: updateAll,
    };
}());

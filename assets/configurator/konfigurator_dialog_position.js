(function () {
    "use strict";

    if (typeof document === "undefined") return;

    var scheduled = 0;
    var observedCard = null;
    var observedSettings = null;
    var settingsWidth = 0;
    // Gleicher Anker und gleiche Geometrie: Layoutänderungen behalten ihren
    // Ausgangspunkt; positionCard begrenzt ihn auf den sichtbaren Bereich.
    var initialDialogPlacement = null;
    var missingAnchorTimer = 0;
    var missingAnchorSince = 0;
    var observedSizes = new WeakMap();
    var observedFields = new Set();
    var formMeasure = window.HEOFormMeasure;
    if (!formMeasure || !window.HEOFormViewports) return;
    var dialogScroll = {anchor: null, card: null, top: 0};
    var settingsScroll = {top: 0, restoring: false};
    var resizeObserver = typeof ResizeObserver === "function"
        ? new ResizeObserver(function (entries) {
            var changed = false;
            entries.forEach(function (entry) {
                var size = entry.contentRect.width + ":" + entry.contentRect.height;
                var previous = observedSizes.get(entry.target);
                observedSizes.set(entry.target, size);
                if (previous !== size) changed = true;
            });
            if (changed) schedulePosition();
        }) : null;
    var settingsResizeObserver = typeof ResizeObserver === "function"
        ? new ResizeObserver(function (entries) {
            var width = entries[0] && entries[0].contentRect.width || 0;
            if (Math.abs(width - settingsWidth) > 0.5) {
                settingsWidth = width;
                schedulePosition();
            }
        }) : null;
    var directFormCells = formMeasure.directCells;

    function layoutSettings() {
        var choice = document.getElementById("konfig-simulation-choice");
        var settings = document.querySelector(
            "#konfig-simulation-settings-content > .konfig-simulation-settings"
        );
        if (settings !== observedSettings) {
            if (settingsResizeObserver) settingsResizeObserver.disconnect();
            observedSettings = settings;
            settingsWidth = 0;
            if (settingsResizeObserver && settings) settingsResizeObserver.observe(settings);
        }
        if (!settings || !formMeasure.visible(settings)) {
            if (!choice || choice.hidden || !settings) {
                settingsScroll.top = 0;
                settingsScroll.restoring = false;
            }
            return;
        }
        settingsScroll.restoring = true;
        var scrollTop = Math.max(choice ? choice.scrollTop : 0, settingsScroll.top);
        window.HEOFormViewports.preserve(choice || settings, function () {
            window.HEOFormViewports.layout(settings);
            if (choice) choice.scrollTop = scrollTop;
        });
        if (choice) settingsScroll.top = choice.scrollTop;
        requestAnimationFrame(function () { settingsScroll.restoring = false; });
    }

    function sizeCard(card, availableWidth, availableHeight) {
        var margin = 14;
        var viewportWidth = Math.max(1, availableWidth - 2 * margin);
        var viewportHeight = Math.max(1, availableHeight - 2 * margin);
        // Erst die maximal verfügbare Breite anlegen, damit keine alte
        // Schmalansicht die Messung von Gruppen und Controls beeinflusst.
        card.style.width = viewportWidth + "px";
        var required = 0;
        card.querySelectorAll('[data-form-planner="automatic"]').forEach(function (grid) {
            if (grid.parentElement.closest('[data-form-planner="automatic"]') || !formMeasure.visible(grid)) return;
            directFormCells(grid).forEach(function (cell) {
                required = Math.max(required, formMeasure.cell(cell).preferredWidth + formMeasure.boxBetween(grid, card));
            });
        });
        var declaredMaxWidth = Number(card.dataset.konfigMaxWidth);
        var maxWidth = declaredMaxWidth > 0
            ? Math.min(viewportWidth, declaredMaxWidth) : viewportWidth;
        var width = Math.min(maxWidth, Math.max(766, required + formMeasure.box(card) + 16));
        var heldWidth = window.HEOFormViewports.preferredWidth(card);
        if (heldWidth) {
            width = Math.min(maxWidth, heldWidth);
            // Während einer Bedienung wächst das Fenster ab seiner bisherigen
            // Oberkante in den verfügbaren Raum; weiterer Inhalt scrollt innen.
            if (initialDialogPlacement) viewportHeight = Math.max(1,
                Math.min(viewportHeight, availableHeight - margin - initialDialogPlacement.top));
        }
        card.style.width = Math.floor(width) + "px";
        card.style.height = "auto";
        card.style.maxHeight = Math.floor(viewportHeight) + "px";
        card.style.aspectRatio = "auto";
        card.style.overflowX = "auto";
        card.style.overflowY = "auto";
        window.HEOFormViewports.layout(card);
        // Eine neu hinzugekommene vertikale Scrollbar reduziert die Nutzbreite.
        window.HEOFormViewports.layout(card);
        return {width: card.offsetWidth, height: card.offsetHeight, margin: margin};
    }

    function positionDialog() {
        scheduled = 0;
        layoutSettings();
        var shell = document.querySelector(".konfig-inspector-shell");
        var card = shell && shell.querySelector(".konfig-inspector-card");
        var viewportElement = document.getElementById("konfig-topology-content");
        if (!shell || !card || !viewportElement) {
            return;
        }

        // Die Tangentenplatzierung ist für Konfigurator und Ergebnisansicht
        // identisch. Dieser Aufrufer bestimmt den Fensterrahmen; die innere
        // Rasterbelegung übernimmt der gemeinsame Formularplaner.
        if (!window.TopologyOverlay) return;
        return window.HEOFormViewports.preserve(card, function () {
            var anchorKey = shell.dataset.konfigAnchor;
            // Die Breitenmessung in sizeCard kann den Inhalt kurz so weit verkürzen,
            // dass der Browser den Scrollstand begrenzt. Dash ersetzt außerdem beim
            // Speichern eines geöffneten Bereichs die gesamte Dialogkarte.
            var scrollTop = dialogScroll.anchor === anchorKey
                ? (dialogScroll.card === card ? card.scrollTop : dialogScroll.top)
                : 0;
            var anchor = window.TopologyOverlay.findAnchor(
                viewportElement, "data-konfig-anchor", anchorKey
            );
            var anchorRect = anchor && anchor.getBoundingClientRect();
            var shellRect = shell.getBoundingClientRect();
            var anchorGeometry = anchorRect && {
                x: (anchorRect.left + anchorRect.right) / 2 - shellRect.left,
                y: (anchorRect.top + anchorRect.bottom) / 2 - shellRect.top,
                width: anchorRect.width,
                height: anchorRect.height
            };
            var sameAnchor = initialDialogPlacement && anchorGeometry
                && initialDialogPlacement.key === anchorKey
                && Math.abs(initialDialogPlacement.x - anchorGeometry.x) < 1
                && Math.abs(initialDialogPlacement.y - anchorGeometry.y) < 1
                && Math.abs(initialDialogPlacement.width - anchorGeometry.width) < 1
                && Math.abs(initialDialogPlacement.height - anchorGeometry.height) < 1;
            var sharedPlacement = window.TopologyOverlay.positionCard({
                viewport: viewportElement,
                shell: shell,
                card: card,
                anchorKey: anchorKey,
                anchorAttribute: "data-konfig-anchor",
                color: shell.dataset.konfigColor || "#43564d",
                preferredPosition: sameAnchor || window.HEOFormViewports.preferredWidth(card) ? initialDialogPlacement : null,
                sizeCard: sizeCard
            });
            if (!sharedPlacement) {
                // Dash kann den Anker und den Dialog in getrennten Renderphasen
                // aktualisieren. Die zuletzt gültige Lage bleibt kurz sichtbar.
                if (initialDialogPlacement && initialDialogPlacement.key === anchorKey
                    && initialDialogPlacement.cardWidth && viewportElement.getClientRects().length) {
                    if (!missingAnchorSince) missingAnchorSince = Date.now();
                    var remaining = 100 - (Date.now() - missingAnchorSince);
                    if (remaining <= 0) {
                        initialDialogPlacement = null;
                        missingAnchorSince = 0;
                        shell.classList.remove("is-positioned");
                        return;
                    }
                    card.style.left = initialDialogPlacement.left + "px";
                    card.style.top = initialDialogPlacement.top + "px";
                    card.style.width = initialDialogPlacement.cardWidth + "px";
                    card.style.maxHeight = initialDialogPlacement.cardMaxHeight;
                    card.style.overflowX = "auto";
                    card.style.overflowY = "auto";
                    card.style.setProperty("--konfig-dialog-radius", initialDialogPlacement.radius);
                    card.style.setProperty("--konfig-dialog-color", shell.dataset.konfigColor || "#43564d");
                    shell.classList.add("is-positioned");
                    clearTimeout(missingAnchorTimer);
                    missingAnchorTimer = window.setTimeout(function () {
                        missingAnchorTimer = 0;
                        schedulePosition();
                    }, remaining);
                    return;
                }
                initialDialogPlacement = null;
                missingAnchorSince = 0;
                shell.classList.remove("is-positioned");
                return;
            }
            card.scrollTop = scrollTop;
            dialogScroll = {anchor: anchorKey, card: card, top: card.scrollTop};
            clearTimeout(missingAnchorTimer);
            missingAnchorTimer = 0;
            missingAnchorSince = 0;
            if (!sameAnchor) {
                initialDialogPlacement = Object.assign({key: anchorKey}, anchorGeometry, {
                    left: sharedPlacement.left,
                    top: sharedPlacement.top
                });
            }
            card.style.setProperty(
                "--konfig-dialog-radius",
                Math.round(sharedPlacement.radius) + "px"
            );
            card.style.setProperty(
                "--konfig-dialog-color",
                shell.dataset.konfigColor || "#43564d"
            );
            initialDialogPlacement.left = sharedPlacement.left;
            initialDialogPlacement.top = sharedPlacement.top;
            initialDialogPlacement.cardWidth = card.offsetWidth;
            initialDialogPlacement.cardMaxHeight = card.style.maxHeight;
            initialDialogPlacement.radius = card.style.getPropertyValue("--konfig-dialog-radius");
            if (resizeObserver) {
                if (observedCard !== card) {
                    resizeObserver.disconnect();
                    observedFields.clear();
                    resizeObserver.observe(card);
                    observedCard = card;
                }
                observedFields.forEach(function (field) {
                    if (!card.contains(field)) {
                        resizeObserver.unobserve(field);
                        observedFields.delete(field);
                    }
                });
                card.querySelectorAll(".konfig-field").forEach(function (field) {
                    if (!observedFields.has(field)) {
                        resizeObserver.observe(field);
                        observedFields.add(field);
                    }
                });
            }
        });
    }

    function schedulePosition() {
        if (scheduled) {
            cancelAnimationFrame(scheduled);
        }
        scheduled = requestAnimationFrame(positionDialog);
    }

    document.addEventListener("heo:form-layout-needed", function (event) {
        if (event.target.closest(".konfig-inspector-card, .konfig-simulation-settings")) {
            // Die Meldung kommt bereits im gemeinsamen Renderframe. Ein
            // weiterer RAF würde den ungeplanten Dash-Zwischenstand anzeigen.
            if (scheduled) cancelAnimationFrame(scheduled);
            positionDialog();
        }
    });
    document.addEventListener("scroll", function (event) {
        if (event.target === dialogScroll.card) {
            dialogScroll.top = event.target.scrollTop;
            return;
        }
        if (event.target.id === "konfig-simulation-choice") {
            // Beim Austausch bedingter Felder kann der Browser den Scrollstand
            // kurz begrenzen. Nur echte Scrollbewegungen übernehmen.
            if (!settingsScroll.restoring
                && event.target.scrollHeight - event.target.clientHeight
                    >= settingsScroll.top - 1) {
                settingsScroll.top = event.target.scrollTop;
            }
            return;
        }
        if (event.target.closest && event.target.closest(".konfig-inspector-card")) return;
        schedulePosition();
    }, true);
    window.addEventListener("resize", schedulePosition);
    new MutationObserver(function (mutations) {
        if (mutations.some(function (mutation) {
            var target = mutation.target;
            return target instanceof Element
                && Boolean(target.closest("#konfig-simulation-choice"));
        })) {
            settingsScroll.restoring = true;
        }
        if (document.querySelector(".konfig-inspector-shell, .konfig-simulation-settings")) {
            if (mutations.some(function (mutation) {
                return Array.from(mutation.addedNodes || []).some(function (node) {
                    return node.matches && (node.matches(".konfig-inspector-shell, .konfig-simulation-settings")
                        || node.querySelector(".konfig-inspector-shell, .konfig-simulation-settings"));
                });
            })) schedulePosition();
        } else {
            dialogScroll = {anchor: null, card: null, top: 0};
            if (!initialDialogPlacement) return;
            clearTimeout(missingAnchorTimer);
            missingAnchorTimer = window.setTimeout(function () {
                if (!document.querySelector(".konfig-inspector-shell")) {
                    initialDialogPlacement = null;
                    missingAnchorSince = 0;
                }
                missingAnchorTimer = 0;
            }, 100);
        }
    }).observe(document.documentElement, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["hidden", "open"]
    });
}());

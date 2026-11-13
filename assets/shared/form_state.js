(function (root) {
    "use strict";

    // Bedienzustand gehört zum Formular, nicht zur Fensterpositionierung.
    // Stabile Dash-IDs ermöglichen die Zuordnung auch nach einem DOM-Austausch.
    function createState(environment, measure) {
        var document = environment.document;
        var selector = '[data-form-planner="automatic"]';
        var plans = new WeakMap();
        var interaction = null;
        var editing = null;
        var focused = null;
        var restoring = false;
        var depth = 0;

        function locator(element) {
            var scope = element.closest(".konfig-inspector-shell, .energy-result-overlay");
            var path = [], host = element;
            while (host && !host.id) {
                if (!host.parentElement) return {node: element, tag: element.tagName,
                    scope: scope && (scope.dataset.konfigAnchor || scope.dataset.topologyAnchor)};
                path.unshift(Array.from(host.parentElement.children).indexOf(host));
                host = host.parentElement;
            }
            return host ? {id: host.id, path: path,
                tag: element.tagName,
                scope: scope && (scope.dataset.konfigAnchor || scope.dataset.topologyAnchor)} : null;
        }

        function resolve(reference) {
            var element = reference && (reference.node ? (reference.node.isConnected ? reference.node : null)
                : document.getElementById(reference.id));
            element = reference && !reference.node ? reference.path.reduce(function (node, index) {
                return node && node.children[index];
            }, element) : element;
            var scope = element && element.closest(".konfig-inspector-shell, .energy-result-overlay");
            return element && (element.tagName !== reference.tag
                || reference.scope !== (scope && (scope.dataset.konfigAnchor || scope.dataset.topologyAnchor)))
                ? null : element || null;
        }

        function grids(element) {
            var result = [], grid = element && element.closest(selector);
            while (grid) {
                result.push(grid);
                grid = grid.parentElement && grid.parentElement.closest(selector);
            }
            return result;
        }

        function scrolls(element) {
            var result = [];
            for (var node = element; node; node = node.parentElement) {
                if (node.scrollHeight > node.clientHeight || node.scrollWidth > node.clientWidth) {
                    result.push({node: node, reference: locator(node), top: node.scrollTop, left: node.scrollLeft});
                }
            }
            return result;
        }

        function restoreScroll(entries) {
            entries.forEach(function (entry) {
                var node = entry.node.isConnected ? entry.node : resolve(entry.reference);
                if (node) { node.scrollTop = entry.top; node.scrollLeft = entry.left; }
            });
        }

        function remember(tree) {
            plans.set(tree.grid, tree);
            tree.plan.placements.forEach(function (placement) { placement.children.forEach(remember); });
        }

        function capture(target) {
            if (!target || !target.closest) return;
            if (target.closest(".heo-unit-picker, #dev-tools-dock, [data-dev-tools-toggle]")) return;
            var control = target.closest("input, textarea, select, button, summary");
            var label = target.closest("label");
            if (!control && label) control = label.control || label.querySelector("input");
            if (!control || !control.closest('.heo-field-grid, [data-form-layout-owner="external"]')) {
                interaction = null;
                if (focused && !focused.node.isConnected) focused = null;
                if (editing && !editing.node.isConnected) { measure.releaseInput(editing.node); editing = null; }
                return;
            }
            var reference = locator(control);
            if (!reference) { interaction = null; return; }
            var owner = control.closest('[data-form-layout-owner="external"]');
            interaction = {reference: reference, rect: control.getBoundingClientRect(), scrolls: scrolls(control),
                ownerReference: owner && locator(owner), ownerWidth: owner && owner.getBoundingClientRect().width,
                bindings: grids(control).map(function (grid) {
                    var tree = plans.get(grid);
                    var index = tree ? tree.cells.findIndex(function (cell) { return cell.contains(control); }) : -1;
                    return index < 0 ? null : {previousPlan: tree.plan, anchorKey: tree.plan.placements[index].key};
                })};
        }

        function constraints(grid) {
            var control = interaction && resolve(interaction.reference);
            var index = grids(control).indexOf(grid);
            return interaction && interaction.bindings[index] || {previousPlan: null, anchorKey: null};
        }

        function editable(target) {
            return target.matches && target.matches("input, textarea")
                && (target.matches("textarea") || ["text", "number", "search", "tel", "email", "url",
                    "password", "date", "datetime-local", "month", "time", "week"].includes(target.type))
                && target.closest(".heo-field-grid");
        }

        function saveEdit(target, dirty) {
            if (!editable(target)) return;
            if (!editing || editing.node !== target) {
                if (editing) measure.releaseInput(editing.node);
                editing = {node: target, reference: locator(target), dirty: false};
                editing.width = measure.holdInput(target);
            }
            editing.value = target.value;
            editing.start = target.selectionStart;
            editing.end = target.selectionEnd;
            editing.direction = target.selectionDirection;
            editing.dirty = editing.dirty || dirty;
        }

        function focusable(control) {
            return measure.visible(control) && (!environment.getComputedStyle
                || environment.getComputedStyle(control).visibility !== "hidden");
        }

        function restoreEdit() {
            if (!editing) return;
            var input = resolve(editing.reference);
            if (!input || !focusable(input)) return;
            var active = document.activeElement;
            if (active && active !== document.body && active !== editing.node && active !== input) return;
            // Nur ein tatsächlich ersetztes Control erhält den lokalen Entwurf.
            // Radio-/Checkbox-Werte und bestätigte Serverwerte bleiben außen.
            if (input !== editing.node) {
                measure.releaseInput(editing.node);
                editing.node = input;
                measure.holdInput(input, editing.width);
                // Die Einheitensteuerung merkt beim Fokus zunächst den
                // bestätigten Ausgangswert; erst danach folgt der Entwurf.
                input.focus({preventScroll: true});
                if (editing.dirty && input.value !== editing.value) {
                    var prototype = input.tagName === "TEXTAREA" ? environment.HTMLTextAreaElement.prototype
                        : environment.HTMLInputElement.prototype;
                    Object.getOwnPropertyDescriptor(prototype, "value").set.call(input, editing.value);
                    input.dispatchEvent(new environment.Event("input", {bubbles: true}));
                }
                if (editing.start != null) {
                    try { input.setSelectionRange(editing.start, editing.end, editing.direction); }
                    catch (_) { /* Numerische native Controls unterstützen keine Textauswahl. */ }
                }
            }
        }

        function restoreFocus() {
            restoreEdit();
            var control = focused && resolve(focused.reference);
            if (control && control !== focused.node && focusable(control)) {
                if (!document.activeElement || document.activeElement === document.body) control.focus({preventScroll: true});
                if (document.activeElement === control) focused.node = control;
            }
        }

        // Auch die äußere Größenmessung kann Scrollstände vorübergehend
        // begrenzen. Verschachtelte Aufrufe stellen erst am Ende wieder her.
        function preserve(container, callback) {
            if (depth) return callback();
            var saved = scrolls(container);
            depth++;
            restoring = true;
            try { restoreFocus(); return callback(); }
            finally {
                try {
                    restoreFocus();
                    restoreScroll(saved);
                    if (interaction && container.contains(resolve(interaction.reference))) {
                        restoreScroll(interaction.scrolls);
                        var control = resolve(interaction.reference);
                        if (control && measure.visible(control)) {
                            var rect = control.getBoundingClientRect();
                            // Rasterbindung hält die Feldposition. Ein darüber
                            // gewachsener Abschnitt wird im Scrollraum ausgeglichen.
                            var dy = rect.top - interaction.rect.top, dx = rect.left - interaction.rect.left;
                            scrolls(control.parentElement).some(function (entry) {
                                var oldTop = entry.node.scrollTop, oldLeft = entry.node.scrollLeft;
                                entry.node.scrollTop += dy; entry.node.scrollLeft += dx;
                                dy -= entry.node.scrollTop - oldTop; dx -= entry.node.scrollLeft - oldLeft;
                                return Math.abs(dy) < 0.5 && Math.abs(dx) < 0.5;
                            });
                            interaction.scrolls = scrolls(control);
                        }
                    }
                } finally { restoring = false; depth--; }
            }
        }

        function release() { interaction = null; }

        function preferredWidth(container) {
            var control = interaction && resolve(interaction.reference);
            return control && container.contains(control) && resolve(interaction.ownerReference) === container
                ? interaction.ownerWidth : null;
        }

        function start() {
            document.addEventListener("pointerdown", function (event) {
                capture(event.target);
            }, true);
            document.addEventListener("keydown", function (event) {
                if (["Enter", " ", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) capture(event.target);
                if (["Tab", "Escape", "PageUp", "PageDown", "Home", "End"].includes(event.key)) release();
            }, true);
            document.addEventListener("focusin", function (event) {
                if (restoring) return;
                capture(event.target);
                focused = event.target.closest('.heo-field-grid, [data-form-layout-owner="external"]')
                    ? {node: event.target, reference: locator(event.target)} : null;
                if (editing && editing.node !== event.target) {
                    measure.releaseInput(editing.node); editing = null;
                }
                saveEdit(event.target, false);
            }, true);
            document.addEventListener("input", function (event) {
                if (!restoring) saveEdit(event.target, true);
            }, true);
            document.addEventListener("focusout", function (event) {
                // Beim Entfernen durch Dash ist relatedTarget leer. Ein echter
                // Fokuswechsel/Blur beendet dagegen die Entwurfsbindung.
                if (restoring) return;
                if (focused && event.target === focused.node && (event.relatedTarget || event.target.isConnected)) focused = null;
                if (!editing || event.target !== editing.node) return;
                if (event.relatedTarget || event.target.isConnected) {
                    measure.releaseInput(editing.node); editing = null;
                }
            }, true);
            document.addEventListener("selectionchange", function () {
                if (!restoring && editing && document.activeElement === editing.node) saveEdit(editing.node, false);
            });
            // Bewusstes Scrollen oder ein neuer Viewport hebt die Pixelbindung auf.
            document.addEventListener("wheel", release, {capture: true, passive: true});
            document.addEventListener("touchmove", release, {capture: true, passive: true});
            environment.addEventListener("resize", release);
        }

        return {remember: remember, constraints: constraints, preserve: preserve, start: start,
            release: release, preferredWidth: preferredWidth};
    }

    if (typeof module !== "undefined" && module.exports) module.exports = {createState: createState};
    if (root) root.HEOFormState = {createState: createState};
}(typeof window !== "undefined" ? window : null));

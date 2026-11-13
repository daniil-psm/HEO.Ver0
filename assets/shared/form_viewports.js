(function (root) {
    "use strict";

    // Ein Aufrufer stellt den Viewport bereit. Diese Steuerung plant nur dessen
    // Inhalt; Fensterkoordinaten und die verfügbare Außenbreite bleiben außen.
    function createController(environment, planner, measure, state) {
        var selector = '[data-form-planner="automatic"]';
        var ownerSelector = '[data-form-layout-owner="external"]';
        var observed = new Map();
        var scheduled = 0;
        var observer = null;
        var dirty = new Set();
        var all = false;

        function roots(container) {
            var grids = Array.from(container.querySelectorAll(selector));
            if (container.matches && container.matches(selector)) grids.unshift(container);
            return grids.filter(function (grid) {
                var parent = grid.parentElement && grid.parentElement.closest(selector);
                return !parent || !(parent === container || container.contains(parent));
            });
        }

        function layout(container) {
            return preserve(container, function () {
                var trees = [];
                roots(container).forEach(function (grid) {
                    var tree = planner.plan(grid, {forGrid: state && state.constraints});
                    if (tree) {
                        planner.apply(tree);
                        if (state) state.remember(tree);
                        // Ein neu gerendertes Dialograster wird erst durch
                        // seinen Eigentümer auf die endgültige Breite gesetzt.
                        // Diese Eigenmessung ist kein Benutzer-Resize.
                        if (observed.has(grid)) observed.set(grid, contentWidth(grid));
                        trees.push(tree);
                    }
                });
                if (environment.HEOFormGrid) {
                    container.querySelectorAll(".heo-field-grid").forEach(environment.HEOFormGrid.refresh);
                    if (container.matches && container.matches(".heo-field-grid")) environment.HEOFormGrid.refresh(container);
                }
                return trees;
            });
        }

        function preserve(container, callback) {
            return state ? state.preserve(container, callback) : callback();
        }

        function outerGrid(element) {
            var grid = element.closest && element.closest(selector), parent;
            while (grid && (parent = grid.parentElement && grid.parentElement.closest(selector))) grid = parent;
            return grid;
        }

        function contentWidth(grid) {
            var style = environment.getComputedStyle ? environment.getComputedStyle(grid) : {};
            return grid.clientWidth - (parseFloat(style.paddingLeft) || 0) - (parseFloat(style.paddingRight) || 0);
        }

        function refresh() {
            scheduled = 0;
            var grids = roots(environment.document);
            var pending = dirty;
            dirty = new Set();
            var refreshAll = all;
            all = false;
            observed.forEach(function (_, grid) {
                if (!grids.includes(grid)) {
                    if (observer) observer.unobserve(grid);
                    observed.delete(grid);
                }
            });
            grids.forEach(function (grid) {
                var fresh = !observed.has(grid);
                if (fresh) {
                    observed.set(grid, contentWidth(grid));
                    if (observer) observer.observe(grid);
                }
                if (!(fresh || refreshAll || pending.has(grid)) || !measure.visible(grid)) return;
                var owner = grid.closest(ownerSelector);
                if (owner) {
                    // Der Fenstereigentümer setzt zuerst die nutzbare Breite.
                    // Auch Portale erhalten Inhalts-/Schriftänderungen direkt.
                    pending.add(owner);
                } else layout(grid);
            });
            pending.forEach(function (owner) {
                if (owner.matches && owner.matches(ownerSelector) && owner.isConnected) {
                    owner.dispatchEvent(new environment.CustomEvent("heo:form-layout-needed", {bubbles: true}));
                }
            });
        }

        function schedule(target) {
            if (!target) all = true;
            else {
                var element = target.target || target;
                if (element.nodeType === 3) element = element.parentElement;
                var grid = element && outerGrid(element);
                var owner = element && element.closest && element.closest(ownerSelector);
                if (owner) dirty.add(owner);
                else if (grid) dirty.add(grid);
                else if (element && element.querySelectorAll) roots(element).forEach(function (child) { dirty.add(child); });
            }
            if (!scheduled) scheduled = environment.requestAnimationFrame(refresh);
        }

        function start() {
            if (environment.ResizeObserver) {
                observer = new environment.ResizeObserver(function (entries) {
                    entries.forEach(function (entry) {
                        var previous = observed.get(entry.target);
                        observed.set(entry.target, entry.contentRect.width);
                        if (previous != null && Math.abs(previous - entry.contentRect.width) > 0.5) {
                            if (state && state.constraints(entry.target).anchorKey != null) state.release();
                            schedule(entry.target);
                        }
                    });
                });
            }
            new environment.MutationObserver(function (mutations) {
                mutations.forEach(function (mutation) {
                    var target = mutation.target.nodeType === 3 ? mutation.target.parentElement : mutation.target;
                    // Eigene Mess- und Belegungsstile erzeugen keine erneute
                    // Planung. Geänderte Inhalte/Sichtbarkeit bleiben relevant.
                    if (!target || !target.closest) return;
                    if (mutation.attributeName === "style" && (target.closest(selector)
                        || target.closest(ownerSelector))) return;
                    if (mutation.type === "attributes" && mutation.oldValue === target.getAttribute(mutation.attributeName)) return;
                    if (outerGrid(target) || target.closest(ownerSelector)
                        || mutation.attributeName && target.querySelector(selector)) schedule(target);
                    else {
                        Array.from(mutation.addedNodes || []).forEach(function (node) {
                            if (node.matches && (node.matches(selector) || node.querySelector(selector))) schedule(node);
                        });
                        if (Array.from(mutation.removedNodes || []).some(function (node) {
                            return node.matches && (node.matches(selector) || node.querySelector(selector));
                        })) schedule({}); // Nur entfernte Raster abmelden, keine unbeteiligten Inhalte neu planen.
                    }
                });
            }).observe(environment.document.documentElement, {
                subtree: true, childList: true, characterData: true, attributes: true,
                attributeOldValue: true, attributeFilter: ["hidden", "open", "class", "style"]
            });
            environment.document.addEventListener("toggle", schedule, true);
            environment.document.addEventListener("change", schedule, true);
            environment.addEventListener("resize", function () { schedule(); });
            if (state) state.start();
            if (environment.document.fonts) {
                environment.document.fonts.ready.then(function () { schedule(); });
                environment.document.fonts.addEventListener("loadingdone", function () { schedule(); });
            }
            schedule();
        }

        return {layout: layout, schedule: schedule, start: start, preserve: preserve,
            preferredWidth: function (container) { return state && state.preferredWidth(container); }};
    }

    if (typeof module !== "undefined" && module.exports) module.exports = {createController: createController};
    if (root && root.HEOFormLayout && root.HEOFormMeasure) {
        root.HEOFormViewports = createController(root,
            root.HEOFormLayout.createDOMPlanner(root, root.HEOFormMeasure), root.HEOFormMeasure,
            root.HEOFormState.createState(root, root.HEOFormMeasure));
        root.HEOFormViewports.start();
    }
}(typeof window !== "undefined" ? window : null));

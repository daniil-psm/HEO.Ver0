(function (root) {
    "use strict";

    // Pure Belegungslogik: keine Überlappungen, keine Verkleinerung von
    // Mindestspannweiten und dieselbe Lese-/Tab-Reihenfolge wie im DOM.
    function packTiles(items, columns) {
        columns = Math.max(1, Math.floor(columns));
        var occupied = [];
        var cursor = 0;
        return items.map(function (item) {
            if (item.breakBefore && occupied.length) cursor = occupied.length * columns;
            var width = Math.min(columns, Math.max(1, Math.ceil(item.columns)));
            var height = Math.max(1, Math.ceil(item.rows));
            for (;; cursor += 1) {
                var row = Math.floor(cursor / columns);
                var column = cursor % columns;
                if (column + width > columns) continue;
                var free = true;
                for (var y = row; y < row + height && free; y += 1) {
                    for (var x = column; x < column + width; x += 1) {
                        if (occupied[y] && occupied[y][x]) { free = false; break; }
                    }
                }
                if (!free) continue;
                for (var py = row; py < row + height; py += 1) {
                    if (!occupied[py]) occupied[py] = [];
                    for (var px = column; px < column + width; px += 1) {
                        occupied[py][px] = true;
                    }
                }
                cursor += width;
                return {row: row + 1, column: column + 1, rows: height, columns: width};
            }
        });
    }

    // Formularzeilen behalten eine gemeinsame Oberkante. Anders als die
    // Kachelbelegung füllen spätere Felder keine Lücken unter hohen Feldern.
    function packRows(items, columns, centered) {
        columns = Math.max(1, Math.floor(columns));
        var placements = [];
        var groups = [];
        var group = [];
        var usedColumns = 0;
        items.forEach(function (item) {
            var width = Math.min(columns, Math.max(1, Math.ceil(item.columns)));
            var height = Math.max(1, Math.ceil(item.rows));
            if (group.length && (item.breakBefore || usedColumns + width > columns)) {
                groups.push(group);
                group = [];
                usedColumns = 0;
            }
            group.push({columns: width, rows: height});
            usedColumns += width;
        });
        if (group.length) groups.push(group);
        var row = 1;
        groups.forEach(function (itemsInRow) {
            var occupiedColumns = itemsInRow.reduce(function (sum, item) {
                return sum + item.columns;
            }, 0);
            var column = centered === false ? 1 : 1 + Math.floor((columns - occupiedColumns) / 2);
            var rowHeight = 0;
            itemsInRow.forEach(function (item) {
                placements.push({
                    row: row, column: column,
                    rows: item.rows, columns: item.columns
                });
                column += item.columns;
                rowHeight = Math.max(rowHeight, item.rows);
            });
            row += rowHeight;
        });
        return placements;
    }


    function positive(value, fallback, name) {
        value = value == null ? fallback : Number(value);
        if (!Number.isFinite(value) || value <= 0) throw new RangeError(name + " muss positiv und endlich sein");
        return value;
    }

    // Bereits bediente Felder bilden einen festen Präfix. Neue Höhen werden
    // reserviert, bevor die übrigen Felder freie Plätze erhalten. Dadurch
    // verschiebt ein größerer abhängiger Inhalt seinen Schalter nicht selbst.
    function packAnchored(items, columns, fixed, mode) {
        var occupied = [];
        function fits(row, column, item) {
            if (column < 0 || column + item.columns > columns || row < 0) return false;
            for (var y = row; y < row + item.rows; y++) {
                for (var x = column; x < column + item.columns; x++) {
                    if (occupied[y] && occupied[y][x]) return false;
                }
            }
            return true;
        }
        function occupy(row, column, item) {
            for (var y = row; y < row + item.rows; y++) {
                if (!occupied[y]) occupied[y] = [];
                for (var x = column; x < column + item.columns; x++) occupied[y][x] = true;
            }
        }
        for (var i = 0; i < items.length; i++) {
            if (!fixed.has(items[i].key)) continue;
            var pin = fixed.get(items[i].key);
            if (!fits(pin.row - 1, pin.column - 1, items[i])) return null;
            occupy(pin.row - 1, pin.column - 1, items[i]);
        }
        var cursor = 0, previous = -1, bottom = 0;
        var placements = [];
        for (var index = 0; index < items.length; index++) {
            var item = items[index], anchor = fixed.get(item.key);
            if (item.breakBefore) cursor = Math.max(cursor, bottom * columns);
            var position;
            if (anchor) {
                position = (anchor.row - 1) * columns + anchor.column - 1;
                if (position <= previous || item.breakBefore && position < cursor) return null;
            } else {
                var next = items.slice(index + 1).find(function (later) { return fixed.has(later.key); });
                var limit = next ? (fixed.get(next.key).row - 1) * columns + fixed.get(next.key).column - 1 : Infinity;
                for (; cursor < limit; cursor++) {
                    if (mode !== "tiles" && Math.floor(cursor / columns) > Math.floor(previous / columns)) {
                        cursor = Math.max(cursor, bottom * columns);
                        if (cursor >= limit) return null;
                    }
                    if (fits(Math.floor(cursor / columns), cursor % columns, item)) break;
                }
                if (cursor >= limit) return null;
                position = cursor;
                occupy(Math.floor(position / columns), position % columns, item);
            }
            var row = Math.floor(position / columns), column = position % columns;
            placements.push({row: row + 1, column: column + 1, rows: item.rows, columns: item.columns});
            previous = position;
            cursor = position + item.columns;
            bottom = Math.max(bottom, row + item.rows);
        }
        return placements;
    }

    // Der reine Planer erhält Messwerte und optional measure(width). Dessen
    // Ergebnis darf bereits gelöste innere Pläne in children enthalten.
    // Weder Messung, DOM-Reihenfolge noch Eingabefelder werden hier verändert.
    function planGrid(items, options) {
        var width = positive(options.width, null, "width");
        var rowUnit = positive(options.rowUnit, 8, "rowUnit");
        var columnUnit = positive(options.columnUnit, 24, "columnUnit");
        var beamWidth = Math.max(1, Math.floor(positive(options.beamWidth, 6, "beamWidth")));
        var gapX = Number(options.columnGap || 0);
        var gapY = Number(options.rowGap || 0);
        if (![gapX, gapY].every(function (gap) { return Number.isFinite(gap) && gap >= 0; })) {
            throw new RangeError("Rasterabstände müssen endlich und nicht negativ sein");
        }
        var mode = options.mode || "tiles";
        if (!["tiles", "rows", "group"].includes(mode)) throw new RangeError("Unbekannter Rastermodus: " + mode);
        var columns = Math.max(1, Math.floor((width + gapX) / (columnUnit + gapX)));
        var trackWidth = (width - (columns - 1) * gapX) / columns;
        var models = items.map(function (item, index) {
            var minimum = positive(item.minWidth, 1, "minWidth");
            var preferred = Math.max(minimum, positive(item.preferredWidth, minimum, "preferredWidth"));
            return {item: item, key: item.key == null ? String(index) : item.key,
                minimum: minimum, preferred: preferred, cache: new Map()};
        });
        var keys = models.map(function (model) { return model.key; });
        if (new Set(keys).size !== keys.length) throw new Error("Doppelte Feldschlüssel im Belegungsplan");
        var previous = options.previousPlan;
        var anchorIndex = previous ? previous.placements.findIndex(function (item) { return item.key === options.anchorKey; }) : -1;
        var anchored = anchorIndex >= 0 && keys.includes(options.anchorKey) && Math.abs(previous.width - width) < 0.5;
        var fixed = new Map();
        if (anchored && !previous.trackWidths && previous.columns === columns) {
            previous.placements.slice(0, anchorIndex + 1).forEach(function (item) { fixed.set(item.key, item); });
        }

        function measured(model, assignedWidth, span) {
            if (!model.cache.has(assignedWidth)) {
                var result = model.item.measure ? model.item.measure(assignedWidth) : {height: model.item.height};
                if (typeof result === "number") result = {height: result};
                var height = positive(result.height, 1, "height");
                model.cache.set(assignedWidth, {height: height, children: result.children || []});
            }
            var size = model.cache.get(assignedWidth);
            return {
                key: model.key, columns: span,
                rows: Math.max(Math.ceil(positive(model.item.minRows, 1, "minRows")), Math.ceil((size.height + gapY) / (rowUnit + gapY))),
                width: assignedWidth, naturalHeight: size.height, children: size.children,
                breakBefore: Boolean(model.item.breakBefore),
                compressed: assignedWidth + 0.01 < model.minimum,
                compression: Math.max(0, model.preferred - assignedWidth),
                excess: Math.max(0, assignedWidth - model.preferred)
            };
        }

        function result(sizes, placements, count, tracks) {
            var rows = Math.max(0, ...placements.map(function (placement) { return placement.row + placement.rows - 1; }));
            var height = rows ? rows * rowUnit + (rows - 1) * gapY : 0;
            var occupied = 0;
            var compression = 0;
            var internalWaste = 0;
            var planned = placements.map(function (placement, index) {
                var size = sizes[index];
                var cellHeight = placement.rows * rowUnit + (placement.rows - 1) * gapY;
                occupied += size.width * cellHeight;
                compression += size.compression * size.naturalHeight;
                internalWaste += size.excess * size.naturalHeight + (cellHeight - size.naturalHeight) * size.width;
                return Object.assign({}, placement, {
                    key: size.key, width: size.width, height: cellHeight,
                    naturalHeight: size.naturalHeight, compressed: size.compressed, children: size.children
                });
            });
            return {width: width, height: height, columns: count, rows: rows,
                rowUnit: rowUnit, columnGap: gapX, rowGap: gapY, trackWidths: tracks || null,
                placements: planned, emptyArea: Math.max(0, width * height - occupied),
                score: [height, compression, internalWaste]};
        }

        // Passt die Gruppe nebeneinander, bleiben ihre Oberkanten gemeinsam.
        // Die Kinder behalten trotzdem ihre eigene Höhe, statt zu strecken.
        var total = models.reduce(function (sum, model) { return sum + model.preferred; }, 0);
        if (anchored && previous.trackWidths && previous.placements.length === models.length
            && previous.placements.every(function (item, index) { return item.key === models[index].key; })) {
            var held = models.map(function (model, index) { return measured(model, previous.trackWidths[index], 1); });
            return result(held, packRows(held, models.length, false), models.length, previous.trackWidths.slice());
        }
        if (!fixed.size && mode === "group" && models.length && !models.some(function (model) { return model.item.breakBefore || model.item.fullWidth; })
            && total + (models.length - 1) * gapX <= width) {
            var usable = width - (models.length - 1) * gapX;
            var tracks = models.map(function (model) { return usable * model.preferred / total; });
            var sizes = models.map(function (model, index) { return measured(model, tracks[index], 1); });
            return result(sizes, packRows(sizes, models.length, false), models.length, tracks);
        }

        function compare(left, right) {
            for (var i = 0; i < left.plan.score.length; i += 1) {
                var difference = left.plan.score[i] - right.plan.score[i];
                if (Math.abs(difference) > 0.01) return difference;
            }
            return left.sequence - right.sequence;
        }

        // Eine kleine Beam-Suche bewertet Breitenkombinationen, statt alle
        // Felder pauschal auf ihre bevorzugte Breite festzulegen. Pro Feld und
        // Breite wird nur einmal gemessen; die Zahl der Varianten ist begrenzt.
        var sequence = 0;
        var beam = [{sizes: [], plan: result([], [], columns), sequence: sequence++}];
        var referenceSizes = [[], []];
        models.forEach(function (model) {
            function spanFor(pixels) { return Math.ceil((pixels + gapX) / (trackWidth + gapX) - 1e-9); }
            var minimum = Math.min(columns, Math.max(1, spanFor(model.minimum),
                Math.ceil(positive(model.item.minColumns, 1, "minColumns"))));
            if (model.item.fullWidth) minimum = columns;
            var preferred = Math.min(columns, Math.max(minimum, spanFor(model.preferred)));
            var variants = Array.from(new Set([preferred, minimum,
                Math.ceil((minimum + preferred) / 2), Math.max(minimum, Math.ceil(columns / 2)), columns]));
            if (fixed.has(model.key)) variants = [fixed.get(model.key).columns];
            var candidates = [];
            beam.forEach(function (state) {
                variants.forEach(function (span) {
                    var assigned = span * trackWidth + (span - 1) * gapX;
                    var sizes = state.sizes.concat([measured(model, assigned, span)]);
                    var placements = fixed.size ? packAnchored(sizes, columns, fixed, mode) : mode === "tiles" ? packTiles(sizes, columns)
                        : packRows(sizes, columns, mode === "rows");
                    if (!placements) return;
                    candidates.push({sizes: sizes, plan: result(sizes, placements, columns), sequence: sequence++});
                });
            });
            var seen = new Set();
            function unique(state) {
                var key = state.sizes.map(function (size) { return size.columns + ":" + size.rows; }).join("|");
                if (seen.has(key)) return false;
                seen.add(key);
                return true;
            }
            beam = candidates.sort(compare).filter(unique).slice(0, beamWidth);
            // Zwei Referenzpfade bleiben bis zum Ende erhalten. Eine zunächst
            // höhere, schmale Variante kann Platz für ein späteres Feld sparen.
            // Sie darf nicht allein wegen der Höhe eines Zwischenstands fehlen.
            seen.clear();
            beam.forEach(unique);
            (fixed.has(model.key) ? [variants[0], variants[0]] : [preferred, minimum]).forEach(function (span, index) {
                var assigned = span * trackWidth + (span - 1) * gapX;
                var sizes = referenceSizes[index].concat([measured(model, assigned, span)]);
                referenceSizes[index] = sizes;
                var placements = fixed.size ? packAnchored(sizes, columns, fixed, mode) : mode === "tiles" ? packTiles(sizes, columns) : packRows(sizes, columns, mode === "rows");
                if (!placements) return;
                var reference = {sizes: sizes, plan: result(sizes, placements, columns), sequence: sequence++};
                if (unique(reference)) beam.push(reference);
            });
        });
        // Bei geänderter Sichtbarkeit können frühere Positionen geometrisch
        // unmöglich werden. Dann gelten wieder Mindestgrößen und Leseordnung.
        if (!beam.length) return planGrid(items, Object.assign({}, options, {previousPlan: null, anchorKey: null}));
        return beam.sort(compare)[0].plan;
    }

    // Der DOM-Adapter stellt für jede Breitenvariante vorübergehend nur Größen
    // ein. Alle Änderungen werden zurückgenommen; erst apply schreibt den
    // ausgewählten Plan. Fensterposition, Scrollstand und Fokus bleiben außen.
    function createDOMPlanner(environment, measure) {
        var styleOf = environment.getComputedStyle.bind(environment);
        var gridSelector = '[data-form-planner="automatic"]';
        var planning = null;

        function number(style, key) { return parseFloat(style[key]) || 0; }

        function transaction(callback) {
            var changes = [];
            function write(element, key, value, priority) {
                changes.push([element, key, element.style.getPropertyValue(key), element.style.getPropertyPriority(key)]);
                element.style.setProperty(key, value, priority || "");
            }
            try { return callback(write); }
            finally {
                changes.reverse().forEach(function (change) {
                    if (change[2]) change[0].style.setProperty(change[1], change[2], change[3]);
                    else change[0].style.removeProperty(change[1]);
                });
            }
        }

        function prepare(cell, write) {
            var field = cell.firstElementChild;
            if (!field || !field.matches(".heo-field, .konfig-field")) return;
            measure.own(field, ".konfig-input").forEach(function (input) {
                var editor = input.closest(".konfig-editable-value");
                if (editor) write(editor, "--konfig-input-slot-width", measure.inputWidth(input) + "px");
            });
        }

        function apply(tree, writer) {
            var write = writer || function (element, key, value) { element.style.setProperty(key, value); };
            var plan = tree.plan;
            write(tree.grid, "grid-template-columns", plan.trackWidths ? plan.trackWidths.map(function (width) {
                return "minmax(0, " + width + "px)";
            }).join(" ") : "repeat(" + plan.columns + ", minmax(0, 1fr))");
            write(tree.grid, "grid-auto-rows", plan.rowUnit + "px");
            plan.placements.forEach(function (placement, index) {
                var cell = tree.cells[index];
                prepare(cell, write);
                write(cell, "grid-column", placement.column + " / span " + placement.columns);
                write(cell, "grid-row", placement.row + " / span " + placement.rows);
                placement.children.forEach(function (child) { apply(child, write); });
            });
        }

        function plan(grid, options) {
            var outer = !planning;
            if (outer) planning = {sizes: new WeakMap(), trees: new WeakMap()};
            try {
                return outer ? measure.during(function () { return solve(grid, options || {}); }) : solve(grid, options || {});
            }
            finally { if (outer) planning = null; }
        }

        // Größenbedarfe und bereits gelöste innere Breiten werden nur innerhalb
        // dieses Durchlaufs geteilt. Neue Inhalte/Schriften starten frisch.
        function solve(grid, options) {
            options = options || {};
            // Benannte feste Profile behalten ihre deklarierte Anordnung.
            if (grid.dataset.formLayoutProfile && grid.dataset.formLayoutProfile !== "automatic") return null;
            var gridStyle = styleOf(grid);
            var width = grid.clientWidth - number(gridStyle, "paddingLeft") - number(gridStyle, "paddingRight");
            if (!measure.visible(grid) || width <= 0) return null;
            if (!planning.trees.has(grid)) planning.trees.set(grid, new Map());
            var cached = planning.trees.get(grid);
            if (cached.has(width)) return cached.get(width);
            var cells = measure.directCells(grid);
            var items = cells.map(function (cell, index) {
                if (!planning.sizes.has(cell)) planning.sizes.set(cell, measure.cell(cell));
                var size = planning.sizes.get(cell);
                var field = cell.matches("[data-form-item], [data-form-section]") ? cell : cell.firstElementChild;
                return {
                    key: field && field.dataset.formKey || String(index),
                    minWidth: Math.max(1, size.minWidth), preferredWidth: Math.max(1, size.preferredWidth),
                    minColumns: Number(cell.dataset.formColumnSpan) || 1,
                    minRows: Number(cell.dataset.formRowSpan) || 1,
                    breakBefore: cell.dataset.formBreakBefore === "true",
                    fullWidth: cell.dataset.formFullWidth === "true",
                    measure: function (assignedWidth) {
                        return transaction(function (write) {
                            write(cell, "width", assignedWidth + "px", "important");
                            write(cell, "max-width", "none", "important");
                            write(cell, "box-sizing", "border-box", "important");
                            prepare(cell, write);
                            var children = [];
                            cell.querySelectorAll(gridSelector).forEach(function (inner) {
                                if (inner.parentElement.closest(gridSelector) !== grid) return;
                                var child = plan(inner, options);
                                if (child) { apply(child, write); children.push(child); }
                            });
                            return {height: Math.max(1, measure.height(cell)), children: children};
                        });
                    }
                };
            });
            var tree = {grid: grid, cells: cells, plan: planGrid(items, Object.assign({}, options,
                options.forGrid ? options.forGrid(grid) : {}, {
                width: width, mode: grid.dataset.formLayout || "tiles",
                columnGap: number(gridStyle, "columnGap"), rowGap: number(gridStyle, "rowGap")
            }))};
            cached.set(width, tree);
            return tree;
        }

        return {plan: plan, apply: apply};
    }

    var api = {packTiles: packTiles, packRows: packRows, planGrid: planGrid, createDOMPlanner: createDOMPlanner};
    if (typeof module !== "undefined" && module.exports) module.exports = api;
    if (root) root.HEOFormLayout = api;
}(typeof window !== "undefined" ? window : null));

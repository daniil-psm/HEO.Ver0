(function (root) {
    "use strict";

    // Die Messung kennt Feldinhalt und CSS, aber weder Fensterpositionen noch
    // Rasterbelegung. field/cell/grid liefern minWidth, preferredWidth und die
    // Inhaltshöhe bei der aktuell zugewiesenen Breite; parts erklärt den Bedarf.
    function createMeasurer(environment) {
        var doc = environment.document;
        var styleOf = environment.getComputedStyle.bind(environment);
        var canvas = null;
        var canvasReady = false;
        var editingWidths = new WeakMap();
        var measuredFields = null;
        var fieldSelector = ".heo-field, .konfig-field, [data-form-item], [data-form-section]";

        function number(style, property) {
            return parseFloat(style[property]) || 0;
        }

        function box(element, axis) {
            if (!element) return 0;
            var style = styleOf(element);
            var sides = axis === "height" ? ["Top", "Bottom"] : ["Left", "Right"];
            return sides.reduce(function (sum, side) {
                return sum + number(style, "padding" + side) + number(style, "border" + side + "Width");
            }, 0);
        }

        function visible(element) {
            return Boolean(element && !element.closest("[hidden]") && element.getClientRects().length);
        }

        function own(field, selector, includeHidden) {
            return Array.from(field.querySelectorAll(selector)).filter(function (element) {
                return element.closest(fieldSelector) === field && (includeHidden || visible(element));
            });
        }

        function directCells(grid) {
            return Array.from(grid.children).filter(function (child) {
                return child.matches(".heo-field-cell, .konfig-form-cell") && visible(child);
            });
        }

        function boxBetween(element, ancestor) {
            var result = 0;
            while (element && element !== ancestor) {
                if (styleOf(element).display !== "contents") result += box(element);
                element = element.parentElement;
            }
            return result;
        }

        function textWidth(element, text) {
            if (!element) return 0;
            var style = styleOf(element);
            text = String(text == null ? element.textContent || "" : text).trim();
            if (!canvasReady) {
                canvas = doc.createElement("canvas").getContext("2d");
                canvasReady = true;
            }
            if (canvas) canvas.font = [style.fontStyle, style.fontWeight, style.fontSize, style.fontFamily].join(" ");
            return Math.ceil(Math.max(0, ...text.split(/\r?\n/).map(function (line) {
                return (canvas ? canvas.measureText(line).width : line.length * (number(style, "fontSize") || 14) * 0.6)
                    + Math.max(0, line.length - 1) * number(style, "letterSpacing");
            })));
        }

        function wordWidth(element) {
            return String(element.textContent || "").trim().split(/\s+/).reduce(function (width, word) {
                return Math.max(width, textWidth(element, word));
            }, 0);
        }

        function inputMinimum(input) {
            var wrapper = input.closest(".konfig-input, .heo-field__input");
            return Math.max(input.closest(".konfig-period-dates") ? 150 : 112,
                number(styleOf(input), "minWidth"), wrapper ? number(styleOf(wrapper), "minWidth") : 0);
        }

        function inputWidth(element) {
            var input = element.matches("input, textarea") ? element : element.querySelector("input, textarea");
            if (!input) return 112;
            if (editingWidths.has(input)) return editingWidths.get(input);
            var wrapper = input.closest(".konfig-input, .heo-field__input");
            var padding = box(input) + (wrapper && wrapper !== input ? box(wrapper) : 0);
            return Math.ceil(Math.max(inputMinimum(input),
                textWidth(input, input.value || input.placeholder || "0") + padding + 16));
        }

        function unitWidth(unit) {
            var pieces = Array.from(unit.querySelectorAll(".konfig-unit-numerator, .konfig-unit-denominator"));
            var text = pieces.length ? Math.max.apply(null, pieces.map(function (piece) {
                return textWidth(piece) + box(piece);
            })) : textWidth(unit);
            return Math.max(42, text + box(unit));
        }

        // Gestreckte Übersichtskarten dürfen ihre aktuelle Zeilenhöhe nicht als
        // eigenen Bedarf zurückmelden. Breite, Inhalt und Mindesthöhe bleiben.
        function naturalHeight(element) {
            var properties = ["height", "max-height", "align-self"];
            var previous = properties.map(function (key) {
                return [key, element.style.getPropertyValue(key), element.style.getPropertyPriority(key)];
            });
            try {
                element.style.setProperty("height", "auto", "important");
                element.style.setProperty("max-height", "none", "important");
                element.style.setProperty("align-self", "start", "important");
                return Math.ceil(element.getBoundingClientRect().height);
            } finally {
                previous.forEach(function (entry) {
                    if (entry[1]) element.style.setProperty(entry[0], entry[1], entry[2]);
                    else element.style.removeProperty(entry[0]);
                });
            }
        }

        function measureField(field, includeHidden) {
            if (!includeHidden && !visible(field)) return {minWidth: 0, preferredWidth: 0, height: 0, parts: []};
            if (measuredFields && measuredFields.has(field)) return measuredFields.get(field);
            var parts = [];
            function read(selector) { return own(field, selector, includeHidden); }
            function add(kind, minimum, preferred) {
                parts.push({kind: kind, minWidth: Math.ceil(minimum), preferredWidth: Math.ceil(preferred)});
            }

            // Beschriftung und Wert-/Einheitenzeile bilden getrennte Bedarfe.
            read(".heo-field__label, [data-form-label]").forEach(function (label) {
                add("label", wordWidth(label), textWidth(label));
            });
            read(".heo-field__control, .konfig-field-control, [data-form-control]").forEach(function (control) {
                var inputs = read("input, textarea").filter(function (input) {
                    return control.contains(input) && !["radio", "checkbox", "hidden"].includes(input.type);
                });
                var values = read(".heo-field__value, .heo-unit-value, [data-form-value]").filter(function (value) {
                    return control.contains(value);
                });
                var valueWidth = Math.max(0, ...inputs.map(inputWidth), ...values.map(function (value) {
                    return textWidth(value);
                }));
                var valueMinimum = Math.max(0, ...inputs.map(inputMinimum), ...values.map(wordWidth));
                var units = read(".konfig-unit, .heo-field__unit").filter(function (unit) {
                    return control.contains(unit);
                });
                var unit = units.length ? Math.max.apply(null, units.map(unitWidth)) : 0;
                var unitParent = units.length && units[0].parentElement;
                var gap = unit && valueWidth ? Math.max(number(styleOf(control), "columnGap"),
                    unitParent ? number(styleOf(unitParent), "columnGap") : 0) : 0;
                add("control", valueMinimum + unit + gap, valueWidth + unit + gap);
            });
            read(".konfig-radio label, .konfig-check label, .konfig-readonly-choice-option").forEach(function (label) {
                var text = label.querySelector(".dash-options-list-option-text") || label;
                var indicator = label.querySelector("input, .konfig-readonly-radio");
                var extra = indicator ? Math.max(18, number(styleOf(indicator), "width"))
                    + number(styleOf(label), "columnGap") : 0;
                extra += boxBetween(label, field);
                add("choice", wordWidth(text) + extra, textWidth(text) + extra);
            });
            read(".konfig-angle-editor").forEach(function (editor) {
                var dial = editor.querySelector(".konfig-angle-dial");
                var numberControl = editor.querySelector(".konfig-angle-number");
                if (!dial || !numberControl) return;
                var dialStyle = styleOf(dial);
                var basis = /px$/.test(dialStyle.flexBasis || "") ? number(dialStyle, "flexBasis") : 0;
                var dialWidth = basis || number(dialStyle, "width") || dial.getBoundingClientRect().width;
                if (styleOf(dial).boxSizing !== "border-box") dialWidth += box(dial);
                var input = numberControl.querySelector("input:not([type=hidden]), textarea");
                var value = numberControl.querySelector(".heo-field__value");
                var unit = numberControl.querySelector(".konfig-unit, .heo-field__unit");
                var numericWidth = input ? inputWidth(input) : textWidth(value);
                numericWidth += unit ? unitWidth(unit) + number(styleOf(numberControl), "columnGap") : 0;
                add("angle", Math.max(dialWidth, numericWidth),
                    dialWidth + number(styleOf(editor), "columnGap") + numericWidth);
            });
            read(".konfig-period-dates").forEach(function (dates) {
                var widths = Array.from(dates.children).filter(function (child) { return includeHidden || visible(child); }).map(function (child) {
                    var input = child.matches("input") ? child : child.querySelector("input");
                    return input ? inputWidth(input) : textWidth(child) + box(child);
                });
                var gap = number(styleOf(dates), "columnGap");
                var padding = boxBetween(dates, field);
                add("period", Math.max(0, ...widths) + padding,
                    widths.reduce(function (a, b) { return a + b; }, 0) + Math.max(0, widths.length - 1) * gap + padding);
            });

            // Innere Gruppen liefern einen eigenen Bedarf. Kinder werden weder
            // beim Label noch bei der Einheit der äußeren Box erneut gezählt.
            read(".heo-field-grid, .konfig-form-grid").forEach(function (grid) {
                var size = measureGrid(grid);
                var padding = boxBetween(grid, field) - box(grid);
                var preferred = size.preferredWidth;
                // Abschnittskarten erhalten als Ausgangsbreite zwei ihrer
                // breitesten Felder; die Variantenplanung prüft schmaler/breiter.
                if (field.hasAttribute("data-form-section") && size.cells.length > 2) {
                    var widths = size.cells.map(function (cell) { return cell.preferredWidth; }).sort(function (a, b) { return b - a; });
                    preferred = widths[0] + widths[1] + number(styleOf(grid), "columnGap") + box(grid);
                }
                add("group", size.minWidth + padding, preferred + padding);
            });
            read("[data-form-header], [data-form-entry]").forEach(function (row) {
                var children = Array.from(row.children).filter(visible);
                if (!children.length) children = [row];
                var widths = children.map(function (child) { return textWidth(child) + box(child); });
                var minimum = Math.max(0, ...children.map(wordWidth));
                add("section", minimum, widths.reduce(function (a, b) { return a + b; }, 0)
                    + Math.max(0, children.length - 1) * number(styleOf(row), "columnGap"));
            });
            read(".heo-field__help, .heo-field__error, [data-field-error], [role=alert]").forEach(function (notice) {
                // Meldungen dürfen umbrechen; ihre volle Satzlänge soll keine
                // zusätzliche Formularspalte erzwingen. Die Höhe misst das DOM.
                add(notice.matches(".heo-field__help") ? "help" : "error", wordWidth(notice), wordWidth(notice));
            });
            // Verborgene abhängige Controls liefern nur die strukturelle
            // Mindestbreite der gemeinsamen Box. Ihre Höhe/Position bleibt
            // unbesetzt, bis sie sichtbar sind. So bleibt eine gebundene Box
            // auch nach dem Aktivieren breit genug für ihre inneren Controls.
            field.querySelectorAll('[data-conditional-panel="true"]').forEach(function (panel) {
                if (!panel.hidden || panel.parentElement.closest(fieldSelector) !== field) return;
                panel.querySelectorAll(".heo-field").forEach(function (child) {
                    var size = measureField(child, true);
                    var padding = boxBetween(child, field) - box(child);
                    add("conditional", size.minWidth + padding, 0);
                });
            });
            var minimum = Math.max(0, ...parts.map(function (part) { return part.minWidth; }));
            var preferred = Math.max(minimum, ...parts.map(function (part) { return part.preferredWidth; }));
            var padding = box(field) + 2;
            var result = {
                minWidth: Math.ceil(minimum + padding), preferredWidth: Math.ceil(preferred + padding),
                height: visible(field) ? naturalHeight(field) : 0, parts: parts
            };
            if (measuredFields) measuredFields.set(field, result);
            return result;
        }

        // Innerhalb einer synchronen Planung sind Text, Schrift und Gruppen
        // unverändert. Auch rekursiv abgefragte Bedarfe werden deshalb geteilt;
        // die variablen Höhen liest height() weiterhin aus dem aktuellen DOM.
        function during(callback) {
            var previous = measuredFields;
            if (!previous) measuredFields = new WeakMap();
            try { return callback(); }
            finally { measuredFields = previous; }
        }

        function measureCell(cell) {
            if (!visible(cell)) return {minWidth: 0, preferredWidth: 0, height: 0, parts: []};
            if (cell.matches(fieldSelector)) return measureField(cell);
            var child = cell.firstElementChild;
            var size = child && child.matches(fieldSelector) ? measureField(child) : {
                minWidth: 0, preferredWidth: 0, height: child ? naturalHeight(child) : 0, parts: []
            };
            return {
                minWidth: size.minWidth + box(cell), preferredWidth: size.preferredWidth + box(cell),
                height: size.height + box(cell, "height"), parts: size.parts
            };
        }

        // Breitenvarianten ändern Umbrüche und damit die Höhe. Der bereits
        // bekannte Größenbedarf aller inneren Felder muss dafür nicht erneut
        // rekursiv gelesen werden.
        function cellHeight(cell) {
            if (!visible(cell)) return 0;
            if (cell.matches(fieldSelector)) return naturalHeight(cell);
            return (cell.firstElementChild ? naturalHeight(cell.firstElementChild) : 0) + box(cell, "height");
        }

        function measureGrid(grid) {
            if (!visible(grid)) return {minWidth: 0, preferredWidth: 0, height: 0, cells: []};
            var cells = directCells(grid).map(measureCell);
            var gap = number(styleOf(grid), "columnGap");
            return {
                minWidth: Math.max(0, ...cells.map(function (cell) { return cell.minWidth; })) + box(grid),
                preferredWidth: cells.reduce(function (sum, cell) { return sum + cell.preferredWidth; },
                    Math.max(0, cells.length - 1) * gap) + box(grid),
                height: visible(grid) ? naturalHeight(grid) : 0, cells: cells
            };
        }

        return {
            field: measureField, cell: measureCell, grid: measureGrid, height: cellHeight, during: during,
            inputWidth: inputWidth, textWidth: textWidth, box: box, boxBetween: boxBetween,
            visible: visible, own: own, directCells: directCells,
            holdInput: function (input, width) {
                width = Number.isFinite(width) && width > 0 ? width : inputWidth(input);
                editingWidths.set(input, width);
                return width;
            },
            releaseInput: function (input) { editingWidths.delete(input); }
        };
    }

    if (typeof module !== "undefined" && module.exports) module.exports = {createMeasurer: createMeasurer};
    if (root && root.document) root.HEOFormMeasure = createMeasurer(root);
}(typeof window !== "undefined" ? window : null));

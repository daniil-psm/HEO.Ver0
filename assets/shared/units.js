/* Gemeinsame Einheitenanzeige. Modell-Inputs bleiben in ihrer Ausgangseinheit. */
(function (root) {
    "use strict";

    function parseNumber(text) {
        if (typeof text === "number") return Number.isFinite(text) ? text : null;
        var normalized = String(text).trim().replace(/[.\s\u00a0]/g, "").replace(",", ".");
        if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(normalized)) return null;
        var value = Number(normalized);
        return Number.isFinite(value) ? value : null;
    }

    function germanNumber(value, significant, grouping) {
        if (!Number.isFinite(value)) return "—";
        // Intl gibt auch sehr kleine/große Zahlen ohne Exponentialnotation aus.
        var options = significant
            ? {maximumSignificantDigits: 5}
            : {maximumSignificantDigits: 17};
        options.useGrouping = grouping !== false;
        return new Intl.NumberFormat("de-DE", options).format(value === 0 ? 0 : value);
    }

    function choose(value, profile, preferred) {
        var choices = profile.choices;
        var manual = choices.find(function (item) { return item.unit === preferred; });
        if (manual) return manual;
        var source = choices.find(function (item) { return item.unit === profile.unit; });
        var magnitude = Math.abs(value);
        if (source && (!Number.isFinite(magnitude) || magnitude === 0 || magnitude >= 1 && magnitude < 10000)) return source;
        // Die fachliche Preisleiter €/kW → €/MW hat inverse Faktoren.
        var suitable = choices.filter(function (item) {
            return magnitude / item.factor >= 1 && magnitude / item.factor < 10000;
        });
        var nearest = function (a, b) { return Math.abs(Math.log10(a.factor)) - Math.abs(Math.log10(b.factor)); };
        if (suitable.length) return suitable.slice().sort(nearest)[0];
        if (!Number.isFinite(magnitude) || magnitude === 0) return choices.slice().sort(nearest)[0];
        return choices.slice().sort(function (a, b) { return magnitude < 1 ? a.factor - b.factor : b.factor - a.factor; })[0];
    }

    // Eine unveränderte gerundete Anzeige darf nie den ungerundeten Rohwert ersetzen.
    function decodeEdit(text, initialText, baseValue, factor) {
        if (text === initialText) return baseValue;
        var value = parseNumber(text);
        return value === null ? null : value * factor;
    }

    var api = {choose: choose, format: germanNumber, parse: parseNumber, decodeEdit: decodeEdit};
    if (typeof module !== "undefined") module.exports = api;
    if (!root.document) return;

    var document = root.document;
    var preferences = {};
    var editors = new WeakMap();
    var pending = false;
    var menu = null;
    var activeButton = null;
    var mutedDialog = null;

    function profileFor(field) {
        try { return JSON.parse(field.dataset.unitField); }
        catch (_) { return null; }
    }

    function setProps(id, props) {
        if (root.dash_clientside && root.dash_clientside.set_props) {
            root.dash_clientside.set_props(id, props);
            return true;
        }
        return false;
    }

    function baseNumber(number) {
        var text = number.dataset.unitBaseValue;
        var value = text == null || text === "" ? NaN : Number(text);
        return Number.isFinite(value) ? value : null;
    }

    function paintUnit(button, unit) {
        var slash = unit.indexOf("/");
        var numerator = button.querySelector(".konfig-unit-numerator");
        var denominator = button.querySelector(".konfig-unit-denominator");
        var denominatorText = unit.slice(slash + 1).replace(/^\((.*)\)$/, "$1");
        var current = slash < 0 ? button.textContent === unit : numerator && denominator
            && numerator.textContent === unit.slice(0, slash) && denominator.textContent === denominatorText;
        // Dash kann denselben DOM-Knoten mit neuen Server-Props wiederverwenden.
        if (button.dataset.unitLabel === unit && current) return;
        button.dataset.unitLabel = unit;
        button.replaceChildren();
        button.classList.toggle("konfig-unit-fraction", slash >= 0);
        if (slash < 0) {
            button.textContent = unit;
        } else {
            [unit.slice(0, slash), "", denominatorText].forEach(function (text, i) {
                var span = document.createElement("span");
                span.className = ["konfig-unit-numerator", "konfig-unit-fraction-line", "konfig-unit-denominator"][i];
                span.textContent = text;
                button.appendChild(span);
            });
        }
        button.setAttribute("aria-label", "Einheit ändern: " + unit);
    }

    function applyField(field) {
        var profile = profileFor(field);
        if (!profile) return;
        var numbers = Array.from(field.querySelectorAll(".heo-unit-number")).filter(function (item) {
            return item.closest("[data-unit-field]") === field;
        });
        if (numbers.some(function (number) { return number.contains(document.activeElement); })
            && editors.has(document.activeElement)) return;
        var baseValue = numbers.length ? baseNumber(numbers[0]) : profile.value;
        if (!Number.isFinite(baseValue)) {
            var reading = field.querySelector("[data-unit-base-value]");
            if (reading) baseValue = Number(reading.dataset.unitBaseValue);
        }
        var preferred = profile.choices.some(function (item) { return item.unit === preferences[profile.key]; })
            ? preferences[profile.key] : null;
        var selected = choose(baseValue, profile, preferred);
        // Jahresreihen besitzen eine gemeinsame Einheit für alle Stützjahre.
        numbers.forEach(function (number) {
            var input = number.querySelector("input.heo-unit-editor, .heo-unit-editor input");
            if (!input) return;
            var value = baseNumber(number);
            var displayed = value === null ? input.value : germanNumber(value / selected.factor, true,
                !input.closest(".heo-number-input--ungrouped"));
            var previous = editors.get(input);
            if (previous && previous.initial === displayed && previous.factor === selected.factor
                && previous.base === value && input.value === displayed) return;
            var source = JSON.parse(number.dataset.unitSource);
            var editorId = {type: "heo-unit-editor", source: number.dataset.unitSource};
            if (input.value !== displayed && !setProps(editorId, {value: displayed})) return;
            editors.set(input, {initial: displayed, factor: selected.factor, base: value, source: source});
        });
        field.querySelectorAll(".heo-unit-value, .heo-unit-reading").forEach(function (valueNode) {
            if (valueNode.closest("[data-unit-field]") !== field) return;
            var value = valueNode.hasAttribute("data-unit-base-value")
                ? Number(valueNode.dataset.unitBaseValue) : profile.value;
            if (!Number.isFinite(value)) return;
            var text = germanNumber(value / selected.factor, true);
            if (valueNode.textContent !== text) valueNode.textContent = text;
        });
        field.querySelectorAll(".heo-unit-button").forEach(function (button) {
            if (button.closest("[data-unit-field]") !== field) return;
            paintUnit(button, selected.unit);
            button.dataset.unitMode = preferred ? "manual" : "auto";
            button.title = preferred ? "Einheit ändern (manuell gewählt)" : "Einheit ändern (automatisch)";
        });
    }

    function refresh() {
        pending = false;
        document.querySelectorAll("[data-unit-field]").forEach(applyField);
        if (activeButton && !activeButton.isConnected) closeMenu(false);
    }

    function schedule() {
        if (pending) return;
        pending = true;
        root.requestAnimationFrame(refresh);
    }

    function synchronize(data) {
        preferences = data && typeof data === "object" && !Array.isArray(data) ? Object.assign({}, data) : {};
        schedule();
        return JSON.stringify(preferences);
    }

    function closeMenu(restoreFocus) {
        if (menu) menu.remove();
        menu = null;
        if (mutedDialog) mutedDialog.classList.toggle("heo-unit-dialog-muted", false);
        mutedDialog = null;
        if (activeButton) {
            activeButton.classList.toggle("heo-unit-active-anchor", false);
            activeButton.setAttribute("aria-expanded", "false");
            if (restoreFocus && activeButton.isConnected) activeButton.focus({preventScroll: true});
        }
        activeButton = null;
    }

    function selectUnit(profile, unit) {
        var next = Object.assign({}, preferences);
        next[profile.key] = unit;
        preferences = next;
        setProps("unit-preferences-store", {data: next});
        closeMenu(true);
        refresh();
    }

    function floatingUnit(unit, anchor, bounds, className) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = anchor.className.split(/\s+/).filter(function (name) {
            return name !== "heo-unit-button";
        }).join(" ") + " " + className;
        paintUnit(button, unit);
        // Der Anker kann durch Dialog- oder KPI-CSS unterschiedlich gestaltet
        // sein. Die Kandidaten übernehmen seine tatsächlich berechnete Darstellung.
        var computed = root.getComputedStyle(anchor);
        ["fontFamily", "fontSize", "fontWeight", "fontStyle", "lineHeight", "letterSpacing",
            "color", "backgroundColor", "borderTop", "borderRight", "borderBottom", "borderLeft",
            "borderRadius", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "boxShadow"
        ].forEach(function (name) { button.style[name] = computed[name]; });
        button.style.width = bounds.width + "px";
        button.style.height = bounds.height + "px";
        button.style.minWidth = "0";
        button.style.minHeight = "0";
        return button;
    }

    function candidate(profile, item, anchor, bounds) {
        var button = floatingUnit(item.unit, anchor, bounds, "heo-unit-candidate");
        button.setAttribute("role", "option");
        button.setAttribute("aria-label", item.unit);
        button.setAttribute("aria-selected", String(preferences[profile.key] === item.unit));
        button.addEventListener("click", function () { selectUnit(profile, item.unit); });
        return button;
    }

    function openMenu(button) {
        if (activeButton === button) { closeMenu(true); return; }
        closeMenu(false);
        var field = button.closest("[data-unit-field]");
        var profile = field && profileFor(field);
        if (!profile || profile.choices.length < 2) return;
        applyField(field);
        activeButton = button;
        button.setAttribute("aria-expanded", "true");
        var bounds = button.getBoundingClientRect();
        var width = bounds.width;
        var left = Math.max(4, Math.min(root.innerWidth - width - 4, bounds.left));
        var selected = button.dataset.unitLabel || profile.unit;
        var index = profile.choices.findIndex(function (item) { return item.unit === selected; });
        menu = document.createElement("div");
        menu.className = "heo-unit-picker";
        menu.setAttribute("role", "listbox");
        menu.setAttribute("aria-label", "Einheit auswählen");
        menu.style.left = left + "px";
        menu.style.width = width + "px";
        // Zwei unabhängig scrollbare Listen lassen den bestehenden Anker unverrückt.
        var above = document.createElement("div");
        above.className = "heo-unit-candidates heo-unit-candidates--above";
        above.style.bottom = (root.innerHeight - bounds.top + 4) + "px";
        above.style.maxHeight = Math.max(0, bounds.top - 8) + "px";
        profile.choices.slice(0, index).forEach(function (item) { above.appendChild(candidate(profile, item, button, bounds)); });
        var below = document.createElement("div");
        below.className = "heo-unit-candidates heo-unit-candidates--below";
        below.style.top = (bounds.bottom + 4) + "px";
        below.style.maxHeight = Math.max(0, root.innerHeight - bounds.bottom - 8) + "px";
        profile.choices.slice(index + 1).forEach(function (item) { below.appendChild(candidate(profile, item, button, bounds)); });
        menu.append(above, below);
        // Wie bei der Topology-Kandidatenauswahl liegt der aktive Ursprung
        // separat über der entsättigten Ebene; sein Rasterplatz bleibt erhalten.
        var origin = floatingUnit(selected, button, bounds, "heo-unit-origin");
        origin.style.top = bounds.top + "px";
        origin.setAttribute("aria-label", "Einheitenauswahl schließen: " + selected);
        origin.setAttribute("aria-expanded", "true");
        origin.addEventListener("click", function () { closeMenu(true); });
        menu.appendChild(origin);
        menu.addEventListener("click", function (event) { event.stopPropagation(); });
        mutedDialog = button.closest(".konfig-inspector-card, .topology-overlay-card")
            || button.closest(".konfig-simulation-settings, .general-info-card, .heo-field");
        if (mutedDialog) mutedDialog.classList.toggle("heo-unit-dialog-muted", true);
        button.classList.toggle("heo-unit-active-anchor", true);
        document.body.appendChild(menu);
        above.scrollTop = above.scrollHeight;
        origin.focus({preventScroll: true});
    }

    document.addEventListener("click", function (event) {
        var button = event.target.closest && event.target.closest(".heo-unit-button");
        if (!button) return;
        event.preventDefault();
        event.stopPropagation();
        openMenu(button);
    }, true);

    document.addEventListener("pointerdown", function (event) {
        // Die Aufnahme übernimmt den aktuellen Auswahlzustand samt Ursprung.
        if (event.target.closest && event.target.closest("#dev-tools-dock")) return;
        if (menu && !menu.contains(event.target) && !activeButton.contains(event.target)) closeMenu(false);
    }, true);

    document.addEventListener("keydown", function (event) {
        if (!menu) return;
        if (event.key === "Escape" || event.key === "Tab") {
            closeMenu(event.key === "Escape");
            if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); }
        } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            var buttons = Array.from(menu.querySelectorAll(".heo-unit-candidates--above button"))
                .concat([menu.querySelector(".heo-unit-origin")], Array.from(menu.querySelectorAll(".heo-unit-candidates--below button")));
            var position = buttons.indexOf(document.activeElement);
            var next = event.key === "ArrowDown" ? position + 1 : (position < 0 ? buttons.length - 1 : position - 1);
            buttons[(next + buttons.length) % buttons.length].focus();
            event.preventDefault();
            event.stopPropagation();
        }
    }, true);

    document.addEventListener("focusin", function (event) {
        var input = event.target;
        if (!input.matches || !input.matches("input") || !input.closest(".heo-unit-editor")) return;
        if (!editors.has(input)) applyField(input.closest("[data-unit-field]"));
        var state = editors.get(input);
        if (state) state.editStart = input.value;
    }, true);

    document.addEventListener("blur", function (event) {
        var input = event.target;
        var state = editors.get(input);
        if (!state) return;
        if (input.value === (state.editStart == null ? state.initial : state.editStart)) {
            editors.delete(input);
            schedule();
            return;
        }
        var value = decodeEdit(input.value, state.editStart || state.initial, state.base, state.factor);
        if (value === null) {
            input.setCustomValidity("Bitte einen gültigen Zahlenwert eingeben.");
            input.reportValidity();
            return;
        }
        input.setCustomValidity("");
        if (value !== state.base) {
            var number = input.closest(".heo-unit-number");
            number.dataset.unitBaseValue = String(value);
            state.base = value;
            // Einheitenfaktor einmal zurückrechnen; bestehende DG-/Prozent-Skalierungen
            // werden anschließend von den unveränderten Formular-Callbacks gelesen.
            setProps(state.source, {value: germanNumber(value, false)});
        }
        delete state.editStart;
        editors.delete(input);
        schedule();
    }, true);

    // Kein Wechsel während der Eingabe. Enter bestätigt, Escape stellt den Bearbeitungsbeginn wieder her.
    document.addEventListener("keydown", function (event) {
        var state = editors.get(event.target);
        if (!state) return;
        if (event.key === "Escape") {
            setProps({type: "heo-unit-editor", source: event.target.closest(".heo-unit-number").dataset.unitSource},
                {value: state.editStart || state.initial});
            event.target.value = state.editStart || state.initial;
            event.target.blur();
            event.preventDefault();
            event.stopImmediatePropagation();
        } else if (event.key === "Enter") {
            event.target.blur();
            event.preventDefault();
        }
    }, true);

    root.addEventListener("resize", function () { closeMenu(false); });
    document.addEventListener("scroll", function (event) {
        if (menu && !menu.contains(event.target)) closeMenu(false);
    }, true);
    new MutationObserver(schedule).observe(document.documentElement, {
        subtree: true, childList: true, attributes: true,
        attributeFilter: ["data-unit-field", "data-unit-base-value"],
    });
    api.synchronize = synchronize;
    root.HEOUnits = api;
    schedule();
}(typeof window !== "undefined" ? window : globalThis));

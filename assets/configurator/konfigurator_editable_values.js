(function () {
    "use strict";

    var composingNumberInputs = new WeakSet();
    var redispatchedNumberInputs = new WeakSet();
    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype, "value"
    ).set;
    var numberMeasureCanvas = document.createElement("canvas");
    var numberMeasureContext = numberMeasureCanvas.getContext("2d");
    var minimumNumberInputWidth = 112;
    var activeLandingPanel = null;

    function releaseLandingPanel() {
        if (activeLandingPanel) activeLandingPanel.classList.remove("is-interaction-open");
        activeLandingPanel = null;
    }

    // Der Bearbeitungszustand gehört zur Startkarte. Ein Fokuswechsel zum
    // schwebenden Einheitenmenü oder zum Screenshot-Werkzeug beendet ihn nicht.
    function updateLandingInteraction(event) {
        var target = event.target;
        if (!target.closest || target.closest(".heo-unit-picker, #dev-tools-dock")) return;
        var panel = target.closest(".konfig-landing-panel");
        var editor = target.closest("input, textarea, select, .konfig-editable-value-display, .konfig-editable-heading-button");
        if (!panel || !editor) {
            releaseLandingPanel();
            return;
        }
        if (activeLandingPanel !== panel) releaseLandingPanel();
        activeLandingPanel = panel;
        panel.classList.add("is-interaction-open");
    }

    document.addEventListener("pointerdown", updateLandingInteraction, true);
    document.addEventListener("focusin", updateLandingInteraction, true);
    // keyup erreicht uns auch dann, wenn ein Editor Enter/Escape beim
    // keydown abfängt und den Fokus anschließend auf den Dokumentkörper setzt.
    document.addEventListener("keyup", function (event) {
        if (event.target.closest && event.target.closest("#dev-tools-dock")) return;
        if (event.key === "Enter" || event.key === "Escape") releaseLandingPanel();
    }, true);

    function groupNumberDigits(digits) {
        return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    }

    function formatGermanNumberInput(rawValue, allowDecimal, groupThousands) {
        var raw = String(rawValue == null ? "" : rawValue);
        var negative = raw.trimStart().startsWith("-");
        var commaIndex = allowDecimal ? raw.indexOf(",") : -1;
        var integerRaw = commaIndex >= 0 ? raw.slice(0, commaIndex) : raw;
        var fractionRaw = commaIndex >= 0 ? raw.slice(commaIndex + 1) : "";
        var integerDigits = integerRaw.replace(/\D/g, "");
        var fractionDigits = fractionRaw.replace(/\D/g, "");

        if (!integerDigits && commaIndex < 0) {
            return negative ? "-" : "";
        }
        integerDigits = (integerDigits || "0").replace(/^0+(?=\d)/, "");
        return (negative ? "-" : "")
            + (groupThousands === false
                ? integerDigits : groupNumberDigits(integerDigits))
            + (commaIndex >= 0 ? "," + fractionDigits : "");
    }

    function caretAfterNumberDigits(text, digitCount, startAt) {
        var seen = 0;
        var start = startAt || 0;
        if (digitCount === 0) {
            return start;
        }
        for (var index = start; index < text.length; index += 1) {
            if (/\d/.test(text[index])) {
                seen += 1;
                if (seen === digitCount) {
                    return index + 1;
                }
            }
        }
        return text.length;
    }

    function formattedNumberCaret(raw, formatted, originalCaret, allowDecimal) {
        var rawComma = allowDecimal ? raw.indexOf(",") : -1;
        if (rawComma >= 0 && originalCaret > rawComma) {
            var decimalDigits = raw.slice(rawComma + 1, originalCaret)
                .replace(/\D/g, "").length;
            return caretAfterNumberDigits(
                formatted, decimalDigits, formatted.indexOf(",") + 1
            );
        }
        return caretAfterNumberDigits(
            formatted,
            raw.slice(0, originalCaret).replace(/\D/g, "").length,
            formatted.startsWith("-") ? 1 : 0
        );
    }

    function isNumberInput(target) {
        return target instanceof HTMLInputElement
            && Boolean(target.closest(".heo-number-input"));
    }

    function numberInputHasClass(input, className) {
        var container = input.closest(".heo-number-input");
        return input.classList.contains(className)
            || Boolean(container && container.classList.contains(className));
    }

    function resizeNumberInput(input) {
        if (!isNumberInput(input)) {
            return;
        }
        var container = input.closest(".heo-number-input");
        var editor = input.closest(".konfig-editable-value");
        var inputStyle = window.getComputedStyle(input);
        var visibleValue = String(input.value || input.placeholder || "0");
        var measuredTextWidth = visibleValue.length * 9;
        if (numberMeasureContext) {
            numberMeasureContext.font = inputStyle.font || [
                inputStyle.fontWeight,
                inputStyle.fontSize,
                inputStyle.fontFamily,
            ].join(" ");
            measuredTextWidth = numberMeasureContext.measureText(
                visibleValue
            ).width;
        }
        var horizontalPadding = parseFloat(inputStyle.paddingLeft || 0)
            + parseFloat(inputStyle.paddingRight || 0);
        // Zusätzlicher Platz verhindert, dass Cursor oder letzte Ziffer bei
        // rechtsbündigen Feldern am Rand abgeschnitten werden.
        var requiredWidth = Math.max(
            minimumNumberInputWidth,
            Math.ceil(measuredTextWidth + horizontalPadding + 16)
        );
        var width = requiredWidth + "px";
        container.style.setProperty("--heo-number-input-width", width);
        if (editor) {
            editor.style.setProperty("--heo-number-input-width", width);
        }
    }

    function resizeNumberInputs(root) {
        if (!root || root.nodeType !== Node.ELEMENT_NODE) {
            return;
        }
        if (root.matches && root.matches(".heo-number-input input")) {
            resizeNumberInput(root);
        }
        if (root.querySelectorAll) {
            root.querySelectorAll(".heo-number-input input").forEach(
                resizeNumberInput
            );
        }
    }

    function setFormattedNumberValue(input, formatted, caret, notifyDash) {
        // Den nativen Setter verwenden, damit React/Dash den formatierten
        // Wert als echte Änderung erkennt und nicht auf den Rohwert zurücksetzt.
        nativeInputValueSetter.call(input, formatted);
        resizeNumberInput(input);
        if (document.activeElement === input && input.setSelectionRange) {
            input.setSelectionRange(caret, caret);
        }
        if (notifyDash) {
            redispatchedNumberInputs.add(input);
            input.dispatchEvent(new Event("input", { bubbles: true }));
            redispatchedNumberInputs.delete(input);
        }
    }

    function formatNumberInput(input, notifyDash) {
        var raw = input.value;
        var caret = input.selectionStart == null ? raw.length : input.selectionStart;
        var allowDecimal = !numberInputHasClass(
            input, "heo-number-input--integer"
        );
        var groupThousands = !numberInputHasClass(
            input, "heo-number-input--ungrouped"
        );
        var formatted = formatGermanNumberInput(
            raw, allowDecimal, groupThousands
        );
        var nextCaret = formattedNumberCaret(raw, formatted, caret, allowDecimal);

        if (formatted !== raw) {
            setFormattedNumberValue(input, formatted, nextCaret, notifyDash);

            // Manche Dash-/React-Versionen schreiben den Wert nach ihrem
            // delegierten Handler nochmals zurück. Nach dem Paint wird genau
            // dieser Fall korrigiert und erneut an Dash gemeldet.
            window.requestAnimationFrame(function () {
                if (input.isConnected && input.value !== formatted) {
                    setFormattedNumberValue(input, formatted, nextCaret, true);
                }
            });
        }
        resizeNumberInput(input);
        return formatted;
    }

    function editorFor(element) {
        return element && element.closest(".konfig-editable-value");
    }

    function inputFor(editor) {
        return editor && editor.querySelector("input.konfig-editable-value-input");
    }

    function displayFor(editor) {
        return editor && editor.querySelector(".konfig-editable-value-display");
    }

    function beginEditing(editor) {
        var input = inputFor(editor);
        if (!input) {
            return;
        }
        editor.dataset.editOriginal = input.value;
        editor.classList.add("is-editing");
        // Erst nach dem Reflow ist das zuvor ausgeblendete Input zuverlässig
        // fokussierbar. Das gilt insbesondere für Formularfelder im
        // Landing-Panel und für Touch-Eingaben.
        window.requestAnimationFrame(function () {
            input.focus({ preventScroll: true });
            input.select();
        });
    }

    function finishEditing(editor) {
        var input = inputFor(editor);
        var display = displayFor(editor);
        if (!input || !display) {
            return;
        }
        display.textContent = input.value;
        editor.classList.remove("is-editing");
        delete editor.dataset.editOriginal;
    }

    function activateDisplay(event) {
        var display = event.target.closest
            && event.target.closest(".konfig-editable-value-display");
        if (!display) {
            return;
        }
        beginEditing(editorFor(display));
        event.preventDefault();
        event.stopPropagation();
    }

    // Capture stellt sicher, dass die Anzeige nicht von einer übergeordneten
    // Dash-/Landing-Interaktion abgefangen wird, bevor sie editierbar wird.
    document.addEventListener("pointerdown", activateDisplay, true);
    document.addEventListener("click", activateDisplay, true);

    document.addEventListener("click", function (event) {
        var confirm = event.target.closest
            && event.target.closest(".konfig-scenario-check");
        if (confirm) {
            window.requestAnimationFrame(function () {
                confirm.blur();
            });
        }
    });

    document.addEventListener("compositionstart", function (event) {
        if (isNumberInput(event.target)) {
            composingNumberInputs.add(event.target);
        }
    }, true);

    document.addEventListener("focusin", function (event) {
        if (isNumberInput(event.target)) {
            resizeNumberInput(event.target);
        }
    }, true);

    document.addEventListener("compositionend", function (event) {
        if (isNumberInput(event.target)) {
            composingNumberInputs.delete(event.target);
            formatNumberInput(event.target, true);
        }
    }, true);

    // Normale Tastatureingaben werden schon vor der DOM-Änderung übernommen.
    // So existiert für React nie ein Zwischenzustand wie "2000", den es als
    // kontrollierten Wert zurückschreiben könnte; die vierte Ziffer erzeugt
    // unmittelbar "2.000".
    document.addEventListener("beforeinput", function (event) {
        var input = event.target;
        if (
            !isNumberInput(input)
            || composingNumberInputs.has(input)
            || event.inputType !== "insertText"
            || typeof event.data !== "string"
        ) {
            return;
        }

        var start = input.selectionStart == null
            ? input.value.length : input.selectionStart;
        var end = input.selectionEnd == null ? start : input.selectionEnd;
        var proposed = input.value.slice(0, start)
            + event.data
            + input.value.slice(end);
        var allowDecimal = !numberInputHasClass(
            input, "heo-number-input--integer"
        );
        var groupThousands = !numberInputHasClass(
            input, "heo-number-input--ungrouped"
        );
        var formatted = formatGermanNumberInput(
            proposed, allowDecimal, groupThousands
        );
        var nextCaret = formattedNumberCaret(
            proposed, formatted, start + event.data.length, allowDecimal
        );

        event.preventDefault();
        setFormattedNumberValue(input, formatted, nextCaret, true);
    }, true);

    // Capture formatiert vor dem React-/Dash-Handler. Der Punkt erscheint
    // dadurch schon mit der vierten Ziffer und nicht erst beim Bestätigen.
    document.addEventListener("input", function (event) {
        if (
            isNumberInput(event.target)
            && !composingNumberInputs.has(event.target)
            && !redispatchedNumberInputs.has(event.target)
        ) {
            formatNumberInput(event.target, true);
        }
    }, true);

    document.addEventListener("keydown", function (event) {
        if (!event.target.classList.contains("konfig-editable-value-input")) {
            return;
        }
        var editor = editorFor(event.target);
        if (event.key === "Enter") {
            event.target.blur();
            event.preventDefault();
        } else if (event.key === "Escape") {
            event.target.value = editor.dataset.editOriginal || event.target.value;
            event.target.blur();
            event.preventDefault();
        }
    });

    document.addEventListener("blur", function (event) {
        if (event.target.classList.contains("konfig-editable-value-input")) {
            finishEditing(editorFor(event.target));
        }
    }, true);

    window.HEOGermanNumberInput = {
        format: formatGermanNumberInput,
    };

    new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            mutation.addedNodes.forEach(resizeNumberInputs);
        });
    }).observe(document.documentElement, {
        childList: true,
        subtree: true,
    });
    resizeNumberInputs(document.documentElement);

}());

(function () {
    "use strict";

    var activeDial = null;
    var activePointerId = null;

    function number(value, fallback) {
        var parsed = Number(String(value).replace(",", "."));
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    function clamp(value, minimum, maximum) {
        return Math.max(minimum, Math.min(maximum, value));
    }

    function inputFor(dial) {
        var editor = dial && dial.closest(".konfig-angle-editor");
        if (!editor) {
            return null;
        }
        var control = editor.querySelector(".konfig-angle-input");
        if (!control) {
            return null;
        }
        return control.matches("input") ? control : control.querySelector("input");
    }

    function limits(dial) {
        return {
            minimum: number(dial.dataset.angleMin, -180),
            maximum: number(dial.dataset.angleMax, 180)
        };
    }

    function render(dial, rawValue) {
        if (!dial) {
            return;
        }
        var range = limits(dial);
        var value = clamp(number(rawValue, 0), range.minimum, range.maximum);
        var pointer = value + (dial.dataset.angleKind === "orientation" ? 180 : 0);
        dial.style.setProperty("--konfig-angle", pointer + "deg");
        dial.setAttribute("aria-valuenow", String(value));
        if (dial.dataset.angleKind === "inclination") {
            renderInclinationGeometry(dial, value);
        }
    }

    function renderInclinationGeometry(dial, value) {
        // Die Kindpositionen dürfen hier nicht zurückgemessen werden: Sie
        // hängen selbst von den folgenden CSS-Variablen ab. Bei wiederholten
        // Dash-Renderings führt das zu einer Rückkopplung, durch die die
        // Zeichnung schrittweise nach rechts unten wandert. Die Geometrie wird
        // deshalb ausschließlich aus der stabilen inneren Dial-Größe bestimmt.
        var innerWidth = dial.clientWidth;
        var innerHeight = dial.clientHeight;
        var pivotX = Math.min(28, Math.max(16, innerWidth - 32));
        var pivotY = Math.min(38, Math.max(28, innerHeight - 40));
        var groundY = Math.max(pivotY + 42, innerHeight - 10);
        var moduleLength = Math.max(
            42,
            Math.min(innerWidth - pivotX - 12, groundY - pivotY - 4)
        );
        var radians = value * Math.PI / 180;
        var endX = pivotX + Math.cos(radians) * moduleLength;
        var endY = pivotY + Math.sin(radians) * moduleLength;
        dial.style.setProperty("--konfig-pivot-x", pivotX + "px");
        dial.style.setProperty("--konfig-pivot-y", pivotY + "px");
        dial.style.setProperty("--konfig-ground-y", groundY + "px");
        dial.style.setProperty("--konfig-module-length", moduleLength + "px");
        dial.style.setProperty("--konfig-end-x", endX + "px");
        dial.style.setProperty("--konfig-end-y", endY + "px");
        dial.style.setProperty(
            "--konfig-right-post-height",
            Math.max(0, groundY - endY) + "px"
        );
    }

    function setNativeValue(input, value, commit) {
        if (!input) {
            return;
        }
        var setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, "value"
        ).set;
        setter.call(input, String(Math.round(value)));
        var valueEditor = input.closest(".konfig-editable-value");
        var valueDisplay = valueEditor
            && valueEditor.querySelector(".konfig-editable-value-display");
        if (valueDisplay) {
            valueDisplay.textContent = input.value;
        }
        if (commit) {
            // React verwaltet für kontrollierte Eingaben einen eigenen
            // Wert-Tracker. Bei einer grafischen Änderung muss dieser bewusst
            // von dem neuen DOM-Wert abweichen, damit Dash das native Event als
            // tatsächliche Änderung übernimmt.
            if (input._valueTracker) {
                input._valueTracker.setValue("__konfig_angle_stale__");
            }
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.dispatchEvent(new Event("change", { bubbles: true }));
        }
    }

    function valueFromPointer(dial, event) {
        if (dial.dataset.angleKind === "inclination") {
            var pivot = dial.querySelector(".konfig-inclination-pivot");
            var pivotRect = pivot.getBoundingClientRect();
            var pivotX = (pivotRect.left + pivotRect.right) / 2;
            var pivotY = (pivotRect.top + pivotRect.bottom) / 2;
            var inclination = Math.atan2(
                event.clientY - pivotY,
                event.clientX - pivotX
            ) * 180 / Math.PI;
            var inclinationRange = limits(dial);
            return Math.round(clamp(
                inclination,
                inclinationRange.minimum,
                inclinationRange.maximum
            ));
        }
        var rect = dial.getBoundingClientRect();
        var x = event.clientX - (rect.left + rect.width / 2);
        var y = event.clientY - (rect.top + rect.height / 2);
        var pointer = Math.atan2(x, -y) * 180 / Math.PI;
        if (pointer < 0) {
            pointer += 360;
        }
        var value = pointer - (dial.dataset.angleKind === "orientation" ? 180 : 0);
        var range = limits(dial);
        while (value < range.minimum) {
            value += 360;
        }
        while (value > range.maximum) {
            value -= 360;
        }
        return Math.round(clamp(value, range.minimum, range.maximum));
    }

    function updateFromPointer(dial, event) {
        var input = inputFor(dial);
        if (!input) {
            return null;
        }
        var value = valueFromPointer(dial, event);
        render(dial, value);
        // Während des Ziehens bleibt die Kopplung lokal. Ein Dash-Update bei
        // jeder Bewegung würde den Dialog neu rendern und den Drag abbrechen.
        setNativeValue(input, value, false);
        return input;
    }

    function commitInput(input) {
        if (!input) {
            return;
        }
        // Den aktuellen DOM-Wert unmittelbar vor dem Event nochmals über den
        // nativen Setter schreiben. So erkennt auch React/Dash die endgültige
        // Änderung nach einer Folge rein lokaler Drag-Bewegungen zuverlässig.
        setNativeValue(input, number(input.value, 0), true);
        if (document.activeElement !== input) {
            input.focus({ preventScroll: true });
            input.blur();
        }
    }

    function finishDrag(event, updatePosition) {
        if (!activeDial) {
            return;
        }
        var eventPointerId = event && event.pointerId;
        if (
            eventPointerId !== undefined
            && eventPointerId !== null
            && activePointerId !== null
            && eventPointerId !== activePointerId
        ) {
            return;
        }
        var dial = activeDial;
        var input = updatePosition && event
            ? updateFromPointer(dial, event)
            : inputFor(dial);
        var pointerId = activePointerId;
        activeDial = null;
        activePointerId = null;
        if (
            pointerId !== null
            && dial.hasPointerCapture
            && dial.hasPointerCapture(pointerId)
        ) {
            dial.releasePointerCapture(pointerId);
        }
        commitInput(input);
    }

    document.addEventListener("pointerdown", function (event) {
        var dial = event.target.closest && event.target.closest(".konfig-angle-dial");
        if (!dial) {
            return;
        }
        activeDial = dial;
        activePointerId = event.pointerId;
        dial.focus({ preventScroll: true });
        if (dial.setPointerCapture) {
            dial.setPointerCapture(event.pointerId);
        }
        updateFromPointer(dial, event);
        event.preventDefault();
    });

    document.addEventListener("pointermove", function (event) {
        if (activeDial && event.pointerId === activePointerId) {
            // Sicherheitsnetz für Browser, die pointerup außerhalb des
            // Dokuments nicht zustellen: ohne gedrückte Maustaste ist der
            // Drag definitiv beendet.
            if (event.pointerType === "mouse" && event.buttons === 0) {
                finishDrag(event, false);
                return;
            }
            updateFromPointer(activeDial, event);
            event.preventDefault();
        }
    });

    window.addEventListener("pointerup", function (event) {
        finishDrag(event, true);
    }, true);

    window.addEventListener("pointercancel", function (event) {
        finishDrag(event, false);
    }, true);

    document.addEventListener("lostpointercapture", function (event) {
        finishDrag(event, false);
    }, true);

    window.addEventListener("blur", function () {
        finishDrag(null, false);
    });

    function renderFromInputEvent(event) {
        var editor = event.target.closest && event.target.closest(".konfig-angle-editor");
        if (!editor) {
            return;
        }
        var dial = editor.querySelector(".konfig-angle-dial");
        var input = inputFor(dial);
        if (input && event.target === input) {
            var range = limits(dial);
            var value = clamp(
                number(input.value, 0), range.minimum, range.maximum
            );
            render(dial, value);
        }
    }

    document.addEventListener("input", renderFromInputEvent);
    document.addEventListener("change", renderFromInputEvent);

    document.addEventListener("keydown", function (event) {
        var dial = event.target.closest && event.target.closest(".konfig-angle-dial");
        if (!dial || !["ArrowLeft", "ArrowDown", "ArrowRight", "ArrowUp"].includes(event.key)) {
            return;
        }
        var input = inputFor(dial);
        var direction = ["ArrowLeft", "ArrowDown"].includes(event.key) ? -1 : 1;
        var range = limits(dial);
        var value = clamp(Math.round(number(input.value, 0)) + direction, range.minimum, range.maximum);
        render(dial, value);
        setNativeValue(input, value, true);
        event.preventDefault();
    });

    var dialResizeObserver = typeof ResizeObserver === "function"
        ? new ResizeObserver(function (entries) {
            entries.forEach(function (entry) {
                var dial = entry.target;
                var input = inputFor(dial);
                render(dial, input ? input.value : 0);
            });
        }) : null;
    var observedDials = new Set();

    function renderAll() {
        observedDials.forEach(function (dial) {
            if (!dial.isConnected) {
                dialResizeObserver.unobserve(dial);
                observedDials.delete(dial);
            }
        });
        document.querySelectorAll(".konfig-angle-dial").forEach(function (dial) {
            var input = inputFor(dial);
            render(dial, input ? input.value : 0);
            if (dialResizeObserver && !observedDials.has(dial)) {
                dialResizeObserver.observe(dial);
                observedDials.add(dial);
            }
        });
    }

    new MutationObserver(renderAll).observe(document.documentElement, {
        childList: true,
        subtree: true
    });
    renderAll();
}());

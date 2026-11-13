(function () {
    "use strict";

    if (typeof document === "undefined") return;

    var tooltip = document.createElement("div");
    tooltip.id = "konfig-parameter-tooltip";
    tooltip.className = "konfig-parameter-tooltip";
    tooltip.setAttribute("role", "tooltip");
    tooltip.hidden = true;
    document.body.appendChild(tooltip);

    var activeField = null;
    var focusedControl = null;
    var previousDescription = null;

    function fieldFor(target) {
        return target && target.closest
            ? target.closest(".konfig-inspector-card .heo-field, .konfig-simulation-settings .heo-field, .energy-comparison-kpi[data-kpi-description]") : null;
    }

    function restoreDescription() {
        if (!focusedControl) return;
        if (previousDescription === null) {
            focusedControl.removeAttribute("aria-describedby");
        } else {
            focusedControl.setAttribute("aria-describedby", previousDescription);
        }
        focusedControl = null;
        previousDescription = null;
    }

    function position() {
        if (!activeField || !activeField.isConnected || tooltip.hidden) {
            hide();
            return;
        }
        var card = activeField.closest(".konfig-inspector-card, #konfig-simulation-choice, .energy-comparison-column");
        if (!card) {
            hide();
            return;
        }
        var rect = activeField.getBoundingClientRect();
        var clip = card.getBoundingClientRect();
        if (rect.bottom <= clip.top || rect.top >= clip.bottom) {
            hide();
            return;
        }
        var gap = 8;
        var margin = 12;
        var width = tooltip.offsetWidth;
        var height = tooltip.offsetHeight;
        var left = Math.max(margin, Math.min(rect.left, window.innerWidth - width - margin));
        var below = rect.bottom + gap;
        var above = rect.top - height - gap;
        var top = below + height <= window.innerHeight - margin
            ? below : above >= margin ? above
                : Math.max(margin, Math.min(below, window.innerHeight - height - margin));
        tooltip.style.left = Math.round(left) + "px";
        tooltip.style.top = Math.round(top) + "px";
    }

    function hide() {
        tooltip.hidden = true;
        activeField = null;
        restoreDescription();
    }

    function show(field, control) {
        if (!field) {
            hide();
            return;
        }
        var help = field.querySelector(":scope > .konfig-help");
        var description = field.getAttribute("data-kpi-description") || (help && help.textContent.trim());
        if (!description) {
            hide();
            return;
        }
        if (activeField !== field) {
            restoreDescription();
            activeField = field;
            tooltip.textContent = description;
        }
        tooltip.hidden = false;
        if (control && control !== focusedControl) {
            restoreDescription();
            focusedControl = control;
            previousDescription = control.getAttribute("aria-describedby");
            control.setAttribute("aria-describedby", [previousDescription, tooltip.id]
                .filter(Boolean).join(" "));
        }
        position();
    }

    document.addEventListener("pointerover", function (event) {
        var field = fieldFor(event.target);
        if (field) show(field);
    });
    document.addEventListener("pointerout", function (event) {
        var field = fieldFor(event.target);
        if (field && field === activeField && !field.contains(event.relatedTarget)) {
            if (focusedControl && field.contains(document.activeElement)) {
                position();
            } else {
                hide();
            }
        }
    });
    document.addEventListener("focusin", function (event) {
        var field = fieldFor(event.target);
        if (field) show(field, event.target);
        else if (!activeField || !activeField.matches(":hover")) hide();
    });
    document.addEventListener("focusout", function (event) {
        var field = fieldFor(event.target);
        if (field && field === activeField && !field.contains(event.relatedTarget)) {
            restoreDescription();
            if (field.matches(":hover")) position();
            else hide();
        } else {
            restoreDescription();
        }
    });
    document.addEventListener("scroll", position, true);
    window.addEventListener("resize", position);
})();

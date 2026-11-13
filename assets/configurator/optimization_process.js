(function () {
    "use strict";

    var overlayOpen = false;
    var processBackOpen = false;
    var currentHost = null;
    var currentSimulateButton = null;
    var simulateResizeObserver = null;
    var durationNode = null;
    var durationRunId = null;
    var durationStartSeconds = 0;
    var durationStartTick = 0;
    var durationTimeout = null;

    function formatDuration(totalSeconds) {
        var hours = Math.floor(totalSeconds / 3600);
        var minutes = Math.floor(totalSeconds % 3600 / 60);
        var seconds = totalSeconds % 60;
        return hours + ":" + String(minutes).padStart(2, "0") + ":" +
            String(seconds).padStart(2, "0");
    }

    function updateDuration() {
        durationTimeout = null;
        if (!durationNode || !durationNode.isConnected) {
            return;
        }
        var elapsed = Math.max(
            0, durationStartSeconds +
            (window.performance.now() - durationStartTick) / 1000
        );
        var label = "Dauer: " + formatDuration(Math.floor(elapsed));
        if (durationNode.textContent !== label) {
            var textNode = durationNode.firstChild;
            if (textNode && textNode.nodeType === 3 && !textNode.nextSibling) {
                textNode.nodeValue = label;
            } else {
                durationNode.textContent = label;
            }
        }
        if (!document.hidden) {
            // Immer zur nächsten vollen Sekunde; kein zusätzlicher Dash-Callback.
            durationTimeout = window.setTimeout(
                updateDuration, Math.max(20, Math.ceil((1 - elapsed % 1) * 1000) + 5)
            );
        }
    }

    function syncDuration() {
        var monitor = document.querySelector(".konfig-simulation-monitor");
        var node = monitor && monitor.querySelector(".konfig-progress-duration");
        var running = monitor && monitor.dataset.running === "true";
        if (!running || !node) {
            window.clearTimeout(durationTimeout);
            durationTimeout = null;
            durationNode = null;
            durationRunId = null;
            return;
        }
        var now = window.performance.now();
        var reported = Number(monitor.dataset.elapsedSeconds);
        if (!Number.isFinite(reported)) {
            reported = 0;
        }
        var runId = monitor.dataset.runId;
        var adjusted = false;
        if (runId !== durationRunId) {
            durationRunId = runId;
            durationStartSeconds = Math.max(0, reported);
            durationStartTick = now;
            adjusted = true;
        } else if (reported > durationStartSeconds + (now - durationStartTick) / 1000 + 1) {
            // Nach Schlafmodus oder gedrosseltem Tab an den Serverstand angleichen.
            durationStartSeconds = reported;
            durationStartTick = now;
            adjusted = true;
        }
        if (node === durationNode && !adjusted) {
            return;
        }
        durationNode = node;
        window.clearTimeout(durationTimeout);
        updateDuration();
    }

    function positionSimulateInfoButton() {
        if (!currentSimulateButton) {
            return;
        }
        var width = currentSimulateButton.offsetWidth;
        var height = currentSimulateButton.offsetHeight;
        if (!width || !height) {
            return;
        }
        // Die Kapsel hat einen Radius von der halben kleineren Seitenlänge.
        // Der 45°-Punkt liegt um r · (1 − 1/√2) von beiden Kanten entfernt.
        var radius = Math.min(width, height) / 2;
        var inset = radius * (1 - Math.SQRT1_2);
        currentSimulateButton.parentElement.style.setProperty(
            "--konfig-simulate-corner-inset", inset + "px"
        );
    }

    function syncSimulateInfoButton() {
        var button = document.querySelector(".konfig-simulate-control > .konfig-simulate-button");
        if (button === currentSimulateButton) {
            return;
        }
        if (simulateResizeObserver) {
            simulateResizeObserver.disconnect();
        }
        currentSimulateButton = button;
        if (button && window.ResizeObserver) {
            simulateResizeObserver = new ResizeObserver(positionSimulateInfoButton);
            simulateResizeObserver.observe(button);
        }
        positionSimulateInfoButton();
    }

    function host() {
        return document.getElementById("konfigurator-main-dashboard-info-flip");
    }

    function hasProcessBack(panel) {
        return Boolean(panel && panel.querySelector(".konfig-process-info-content"));
    }

    function showOverlay(open) {
        var panel = host();
        var overlay = document.getElementById("konfig-process-overlay");
        var toggle = document.querySelector(
            "[data-main-panel-info-toggle='konfig-process-overlay']"
        );
        overlayOpen = Boolean(open && overlay && panel);
        if (overlay) {
            overlay.hidden = !overlayOpen;
            overlay.setAttribute("aria-hidden", overlayOpen ? "false" : "true");
        }
        if (toggle) {
            toggle.setAttribute("aria-expanded", overlayOpen ? "true" : "false");
        }
    }

    function restoreProcessBack(panel, open) {
        if (!panel || !hasProcessBack(panel)) {
            return;
        }
        if (panel.dashboardInfoAnimation) {
            panel.dashboardInfoAnimation.cancel();
            delete panel.dashboardInfoAnimation;
        }
        panel.classList.remove("is-flipping", "uses-css-flip-fallback");
        panel.classList.toggle("is-flipped", open);
        panel.style.removeProperty("--dashboard-info-locked-width");
        panel.style.removeProperty("--dashboard-info-locked-height");
        delete panel.dataset.dashboardInfoBusy;
        var front = panel.querySelector(".dashboard-info-front");
        var back = panel.querySelector(".dashboard-info-back");
        var openButton = panel.querySelector('[data-dashboard-info-toggle="open"]');
        var closeButton = panel.querySelector('[data-dashboard-info-toggle="close"]');
        if (front) {
            front.setAttribute("aria-hidden", open ? "true" : "false");
            front.inert = open;
        }
        if (back) {
            back.setAttribute("aria-hidden", open ? "false" : "true");
            back.inert = !open;
        }
        if (openButton) {
            openButton.setAttribute("aria-expanded", open ? "true" : "false");
            openButton.tabIndex = open ? -1 : 0;
        }
        if (closeButton) {
            closeButton.tabIndex = open ? 0 : -1;
        }
    }

    function closeProcessBack(panel) {
        processBackOpen = false;
        if (!panel || !hasProcessBack(panel)) {
            return;
        }
        if (panel.dataset.dashboardInfoBusy === "true") {
            window.setTimeout(function () {
                if (host() === panel && !processBackOpen) {
                    closeProcessBack(panel);
                }
            }, 150);
            return;
        }
        if (panel.classList.contains("is-flipped")) {
            var closeButton = panel.querySelector('[data-dashboard-info-toggle="close"]');
            if (closeButton) {
                closeButton.click();
            }
        }
    }

    function syncNewPanel() {
        syncSimulateInfoButton();
        var panel = host();
        if (panel === currentHost) {
            return;
        }
        currentHost = panel;
        if (!panel) {
            return;
        }
        if (!hasProcessBack(panel)) {
            processBackOpen = false;
        } else if (processBackOpen) {
            restoreProcessBack(panel, true);
        }
        showOverlay(overlayOpen);
    }

    document.addEventListener("click", function (event) {
        if (!(event.target instanceof Element)) {
            return;
        }
        var close = event.target.closest(
            "[data-main-panel-info-close='konfig-process-overlay']"
        );
        if (close) {
            showOverlay(false);
            return;
        }

        var toggle = event.target.closest(
            "[data-main-panel-info-toggle='konfig-process-overlay']"
        );
        if (toggle) {
            showOverlay(!overlayOpen);
            return;
        }

        var panel = host();
        if (!panel) {
            return;
        }
        var flipToggle = event.target.closest("[data-dashboard-info-toggle]");
        if (flipToggle && panel.contains(flipToggle) && hasProcessBack(panel)) {
            processBackOpen = flipToggle.dataset.dashboardInfoToggle === "open";
            if (processBackOpen) {
                showOverlay(false);
            }
            return;
        }
        if (!panel.contains(event.target)) {
            showOverlay(false);
            // Die Parameteransicht wird über die geöffnete Rückseite gelegt.
            if (!event.target.closest(
                "[data-main-panel-info-toggle='konfig-parameters-overlay']"
            ) &&
                hasProcessBack(panel) && processBackOpen) {
                closeProcessBack(panel);
            }
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            if (overlayOpen) {
                showOverlay(false);
                return;
            }
            processBackOpen = false;
        }
    });

    new MutationObserver(function (changes) {
        if (changes.some(function (change) { return change.type === "childList"; })) {
            syncNewPanel();
        }
        syncDuration();
    }).observe(document.documentElement, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["data-running", "data-elapsed-seconds", "data-run-id"],
    });
    document.addEventListener("visibilitychange", function () {
        window.clearTimeout(durationTimeout);
        durationTimeout = null;
        if (!document.hidden) {
            syncDuration();
            if (durationNode && durationTimeout === null) {
                updateDuration();
            }
        }
    });
    window.addEventListener("resize", positionSimulateInfoButton);
    syncNewPanel();
    syncDuration();
})();

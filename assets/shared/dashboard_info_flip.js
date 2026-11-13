(function () {
    "use strict";

    var FLIP_DURATION_MS = 1200;
    var REDUCED_FLIP_DURATION_MS = 620;

    function lockPanelGeometry(host) {
        var bounds = host.getBoundingClientRect();
        host.style.setProperty("--dashboard-info-locked-width", bounds.width + "px");
        host.style.setProperty("--dashboard-info-locked-height", bounds.height + "px");
        host.classList.add("is-flipping");
    }

    function unlockPanelGeometry(host) {
        host.classList.remove("is-flipping");
        host.classList.remove("uses-css-flip-fallback");
        host.style.removeProperty("--dashboard-info-locked-width");
        host.style.removeProperty("--dashboard-info-locked-height");
        delete host.dataset.dashboardInfoBusy;
    }

    function setFlipped(host, flipped, returnFocus) {
        if (!host || host.dataset.dashboardInfoBusy === "true") {
            return;
        }

        var front = host.querySelector(".dashboard-info-front");
        var back = host.querySelector(".dashboard-info-back");
        var inner = host.querySelector(".dashboard-info-flip-inner");
        var openButton = host.querySelector('[data-dashboard-info-toggle="open"]');
        var closeButton = host.querySelector('[data-dashboard-info-toggle="close"]');
        var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        var duration = reducedMotion ? REDUCED_FLIP_DURATION_MS : FLIP_DURATION_MS;

        if (!inner || host.classList.contains("is-flipped") === flipped) {
            return;
        }

        host.dataset.dashboardInfoBusy = "true";
        lockPanelGeometry(host);

        if (front) {
            front.setAttribute("aria-hidden", flipped ? "true" : "false");
            if ("inert" in front) {
                front.inert = flipped;
            }
        }
        if (back) {
            back.setAttribute("aria-hidden", flipped ? "false" : "true");
            if ("inert" in back) {
                back.inert = !flipped;
            }
        }
        if (openButton) {
            openButton.setAttribute("aria-expanded", flipped ? "true" : "false");
            openButton.tabIndex = flipped ? -1 : 0;
        }
        if (closeButton) {
            closeButton.tabIndex = flipped ? 0 : -1;
        }

        var finished = false;
        function finishFlip() {
            if (finished) {
                return;
            }
            finished = true;
            host.classList.toggle("is-flipped", flipped);
            if (host.dashboardInfoAnimation) {
                host.dashboardInfoAnimation.cancel();
                delete host.dashboardInfoAnimation;
            }
            unlockPanelGeometry(host);
            var focusTarget = flipped ? closeButton : (returnFocus ? openButton : null);
            if (focusTarget && document.contains(focusTarget)) {
                focusTarget.focus({preventScroll: true});
            }
        }

        var startAngle = flipped ? 0 : 180;
        var endAngle = flipped ? 180 : 0;

        if (typeof inner.animate === "function") {
            host.dashboardInfoAnimation = inner.animate(
                [
                    {transform: "rotateY(" + startAngle + "deg) translateZ(0)"},
                    {transform: "rotateY(" + endAngle + "deg) translateZ(0)"},
                ],
                {
                    duration: duration,
                    easing: "cubic-bezier(.22, .68, .20, 1)",
                    fill: "forwards",
                }
            );
            host.dashboardInfoAnimation.addEventListener("finish", finishFlip, {once: true});
            window.setTimeout(finishFlip, duration + 220);
            return;
        }

        host.classList.add("uses-css-flip-fallback");
        function handleTransitionEnd(event) {
            if (event.target === inner && event.propertyName === "transform") {
                inner.removeEventListener("transitionend", handleTransitionEnd);
                finishFlip();
            }
        }
        inner.addEventListener("transitionend", handleTransitionEnd);

        /* Zwei Frames halten Ausgangsgeometrie und Ausgangstransform fest,
           bevor die eigentliche Drehung beginnt. */
        window.requestAnimationFrame(function () {
            window.requestAnimationFrame(function () {
                host.classList.toggle("is-flipped", flipped);
            });
        });
        window.setTimeout(finishFlip, duration + 220);
    }

    document.addEventListener("click", function (event) {
        if (!(event.target instanceof Element)) {
            return;
        }
        var toggle = event.target.closest("[data-dashboard-info-toggle]");
        if (!toggle) {
            return;
        }
        var host = toggle.closest(".dashboard-info-flip");
        setFlipped(host, toggle.dataset.dashboardInfoToggle === "open", true);
    });

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") {
            return;
        }
        var host = document.querySelector(".dashboard-info-flip.is-flipped");
        if (host) {
            var parameters = host.querySelector(
                ".konfig-parameters-overlay .konfig-all-parameters"
            );
            if (parameters) {
                host.querySelector("#konfig-parameters-close").click();
                return;
            }
            var processOverlay = host.querySelector("#konfig-process-overlay");
            if (processOverlay && !processOverlay.hidden) {
                return;
            }
            setFlipped(host, false, true);
        }
    });
})();

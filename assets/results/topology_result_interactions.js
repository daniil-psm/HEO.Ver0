/* Root-gescoppte Interaktionen der iframe-freien Topologien. Edge-Fokus ist
 * gemeinsam; Ergebnis-Overlays bleiben eine optionale Zusatzfunktion. */
(function () {
    "use strict";

    const timers = new WeakMap();
    let activeOverlay = null;
    let activeObserver = null;

    function rootOf(element) {
        if (!element || !element.closest) return null;
        const root = element.closest(".topology-renderer");
        if (root) return root;
        const portal = element.closest(".energy-result-overlay.is-portal");
        return activeOverlay && activeOverlay.shell === portal ? activeOverlay.root : null;
    }

    function clearTimer(root) {
        window.clearTimeout(timers.get(root));
        timers.delete(root);
    }

    function hide(root) {
        if (!root) return;
        clearTimer(root);
        if (activeOverlay && activeOverlay.root === root) {
            if (activeObserver) activeObserver.disconnect();
            activeObserver = null;
            activeOverlay.shell.remove();
            activeOverlay = null;
        }
        root.querySelectorAll(".energy-result-overlay").forEach((shell) => {
            shell.classList.remove("is-positioned", "is-pinned");
        });
        root.classList.remove("is-topology-desaturated");
    }

    function scheduleHide(root) {
        if (!root) return;
        clearTimer(root);
        timers.set(root, window.setTimeout(() => {
            if (!activeOverlay || activeOverlay.root !== root
                || !activeOverlay.shell.classList.contains("is-pinned")) hide(root);
        }, 140));
    }

    function overlayFor(root, anchorKey) {
        return Array.from(root.querySelectorAll(".energy-result-overlay"))
            .find((shell) => shell.dataset.topologyAnchor === anchorKey) || null;
    }

    function position(action, shell, card, pointerPosition) {
        const root = rootOf(action);
        const preferred = activeOverlay && activeOverlay.shell === shell && window.HEOFormViewports
            && window.HEOFormViewports.preferredWidth(card) ? activeOverlay.placement : null;
        const place = () => window.TopologyOverlay.positionCard({
            viewport: root,
            shell: shell,
            card: card,
            anchorKey: action.dataset.topologyAnchor,
            pointerPosition: pointerPosition,
            preferredPosition: preferred,
            color: shell.dataset.topologyColor,
            sizeCard: function (currentCard, width, height) {
                const margin = 14;
                currentCard.style.width = Math.round(Math.max(0, Math.min(430, width - 2 * margin))) + "px";
                currentCard.style.maxHeight = Math.round(Math.max(0,
                    height - margin - (preferred ? preferred.top : margin))) + "px";
                if (window.HEOFormViewports) window.HEOFormViewports.layout(currentCard);
                const rect = currentCard.getBoundingClientRect();
                return { width: rect.width, height: rect.height, margin: margin };
            },
        });
        const placement = window.HEOFormViewports ? window.HEOFormViewports.preserve(card, place) : place();
        if (activeOverlay && activeOverlay.shell === shell) activeOverlay.placement = placement;
    }

    function positionActive() {
        if (!activeOverlay) return;
        const {root, shell, action} = activeOverlay;
        const bounds = root.getBoundingClientRect();
        if (!root.isConnected || !action.isConnected
            || bounds.width <= 0 || bounds.height <= 0) {
            hide(root);
            return;
        }
        const card = shell.querySelector(".energy-result-card");
        if (card) position(action, shell, card, null);
    }

    function show(action, persistent, pointerPosition) {
        const root = rootOf(action);
        if (!root || !window.TopologyOverlay) return;
        if (activeOverlay) hide(activeOverlay.root);
        clearTimer(root);
        hide(root);
        const anchorKey = action.dataset.topologyAnchor;
        const template = overlayFor(root, anchorKey);
        const shell = template && template.cloneNode(true);
        const card = shell && shell.querySelector(".energy-result-card");
        if (!shell || !card) return;
        shell.classList.add("is-portal", "is-positioned");
        document.body.appendChild(shell);
        activeOverlay = {root, shell, action};
        position(action, shell, card, pointerPosition);
        if (persistent) shell.classList.add("is-pinned");
        root.classList.add("is-topology-desaturated");
        activeObserver = new MutationObserver(() => {
            const bounds = root.getBoundingClientRect();
            if (!root.isConnected || !action.isConnected
                || bounds.width <= 0 || bounds.height <= 0) hide(root);
        });
        if (root.parentNode) {
            activeObserver.observe(root.parentNode, {
                childList: true, subtree: true,
                attributes: true, attributeFilter: ["style", "class", "hidden"],
            });
        }
        for (let ancestor = root.parentElement && root.parentElement.parentElement;
            ancestor; ancestor = ancestor.parentElement) {
            activeObserver.observe(ancestor, {
                attributes: true, attributeFilter: ["style", "class", "hidden"],
            });
        }
    }

    function focusEdge(action, focused) {
        const root = rootOf(action);
        if (!root) return;
        const edgeId = action.closest("[data-topology-edge-id]")
            ?.dataset.topologyEdgeId;
        root.classList.toggle(
            "is-topology-edge-focused",
            Boolean(focused),
        );
        root.querySelectorAll(
            ".topology-svg-edge-group, .topology-svg-edge-particles",
        ).forEach((group) => {
            group.classList.toggle(
                "is-edge-muted",
                Boolean(focused && group.dataset.topologyEdgeId !== edgeId),
            );
        });
    }

    document.addEventListener("pointerover", (event) => {
        const edge = event.target.closest("[data-topology-edge-focus='true']");
        if (edge && !edge.contains(event.relatedTarget)) {
            focusEdge(edge, true);
            if (edge.dataset.topologyAction === "result-edge") show(edge, false, event);
        }
        const action = event.target.closest("[data-topology-action]");
        if (action && !action.contains(event.relatedTarget)) {
            if (action.dataset.topologyAction === "result-node") show(action, false);
        }
        const card = event.target.closest(".energy-result-card");
        if (card) clearTimer(rootOf(card));
    });

    document.addEventListener("pointermove", (event) => {
        const edge = event.target.closest("[data-topology-action='result-edge']");
        if (!edge || !window.TopologyOverlay) return;
        const root = rootOf(edge);
        if (!root || !activeOverlay || activeOverlay.root !== root
            || activeOverlay.action !== edge) return;
        const shell = activeOverlay.shell;
        if (!shell.classList.contains("is-positioned")
            || shell.classList.contains("is-pinned")) return;
        const card = shell.querySelector(".energy-result-card");
        if (card) position(edge, shell, card, event);
    });

    document.addEventListener("pointerout", (event) => {
        const edge = event.target.closest("[data-topology-edge-focus='true']");
        if (edge && !edge.contains(event.relatedTarget)) {
            focusEdge(edge, false);
        }
        const action = event.target.closest("[data-topology-action]");
        if (action && !action.contains(event.relatedTarget)) {
            scheduleHide(rootOf(action));
        }
        const card = event.target.closest(".energy-result-card");
        if (card && !card.contains(event.relatedTarget)) scheduleHide(rootOf(card));
    });

    document.addEventListener("click", (event) => {
        const close = event.target.closest("[data-topology-action='close-result']");
        if (close) {
            event.stopPropagation();
            hide(rootOf(close));
            return;
        }
        const action = event.target.closest(
            "[data-topology-action='result-node'], [data-topology-action='result-edge']",
        );
        if (action) {
            event.stopPropagation();
            show(
                action,
                true,
                action.dataset.topologyAction === "result-edge" && event.detail > 0
                    ? event : null,
            );
            return;
        }
        const root = rootOf(event.target);
        if (activeOverlay && !event.target.closest(".energy-result-card")) {
            hide(activeOverlay.root);
        } else if (root && !event.target.closest(".energy-result-card")) {
            hide(root);
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            if (activeOverlay) hide(activeOverlay.root);
            document.querySelectorAll(".topology-renderer").forEach(hide);
            return;
        }
        if (event.key !== "Enter" && event.key !== " ") return;
        const action = event.target.closest("[data-topology-action='result-edge']");
        if (action) {
            event.preventDefault();
            show(action, true);
        }
    });

    window.addEventListener("resize", positionActive);
    document.addEventListener("heo:form-layout-needed", (event) => {
        if (activeOverlay && activeOverlay.shell.contains(event.target)) positionActive();
    });
    window.addEventListener("scroll", (event) => {
        if (activeOverlay && !activeOverlay.shell.contains(event.target)) positionActive();
    }, true);
    document.addEventListener("toggle", (event) => {
        if (activeOverlay && activeOverlay.shell.contains(event.target)) {
            window.requestAnimationFrame(positionActive);
        }
    }, true);
}());

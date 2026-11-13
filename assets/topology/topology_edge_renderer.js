/* Native SVG-Ausgabe für den serverseitig fertig berechneten TopologyRenderPlan.
 * Der Browser übernimmt die gelieferten Pfade unverändert. */
(function () {
    "use strict";

    const SVG_NS = "http://www.w3.org/2000/svg";
    const particleStateCache = new Map();
    const activeParticleGroups = new Set();
    let particleAnimationFrame = null;

    function svgElement(name, attributes) {
        const element = document.createElementNS(SVG_NS, name);
        Object.entries(attributes || {}).forEach(([key, value]) => {
            if (value !== null && value !== undefined && value !== "") {
                element.setAttribute(key, String(value));
            }
        });
        return element;
    }

    function createPath(item, className, width, stroke) {
        const path = svgElement("path", {
            class: className,
        });
        updatePath(path, item, width, stroke);
        return path;
    }

    function updatePath(path, item, width, stroke) {
        Object.entries({
            d: item.path,
            fill: "none",
            stroke: stroke,
            "stroke-width": width,
            "stroke-linecap": item.linecap || "butt",
            opacity: item.opacity,
        }).forEach(([key, value]) => path.setAttribute(key, String(value)));
        if (!item.scales_with_scene) {
            path.setAttribute("vector-effect", "non-scaling-stroke");
        } else {
            path.removeAttribute("vector-effect");
        }
        if (item.dotted) {
            path.setAttribute("stroke-dasharray", "8 8");
        } else {
            path.removeAttribute("stroke-dasharray");
        }
    }

    function positiveModulo(value, divisor) {
        return ((value % divisor) + divisor) % divisor;
    }

    function topologyInstanceId(host) {
        const root = host.closest("[data-topology-instance]");
        return root ? root.dataset.topologyInstance : "default";
    }

    function instanceParticleStates(host) {
        const instanceId = topologyInstanceId(host);
        if (!particleStateCache.has(instanceId)) {
            particleStateCache.set(instanceId, new Map());
        }
        return particleStateCache.get(instanceId);
    }

    function advanceParticleState(state, now) {
        const elapsed = Math.min(
            0.1,
            Math.max(0, now - state.updatedAt) / 1000,
        );
        const duration = Math.max(0.001, Number(state.duration) || 0.001);
        const direction = state.direction === "reverse" ? -1 : 1;
        if (elapsed > 0) {
            state.phases = state.phases.map((phase) => positiveModulo(
                phase + direction * elapsed / duration,
                1,
            ));
        }
        state.updatedAt = now;
    }

    function positionParticleGroup(binding) {
        if (!Number.isFinite(binding.pathLength) || binding.pathLength <= 0) {
            try {
                binding.pathLength = binding.path.getTotalLength();
            } catch (_error) {
                return;
            }
        }
        const pathLength = binding.pathLength;
        if (!Number.isFinite(pathLength) || pathLength <= 0) return;
        binding.particles.forEach((particle, index) => {
            const phase = binding.state.phases[index];
            if (!Number.isFinite(phase)) return;
            const point = binding.path.getPointAtLength(phase * pathLength);
            particle.setAttribute(
                "transform",
                "translate(" + point.x + " " + point.y + ")",
            );
        });
    }

    function animateParticleGroups(now) {
        particleAnimationFrame = null;
        let visibleGroups = false;
        activeParticleGroups.forEach((group) => {
            const binding = group.__heoParticleBinding;
            if (!group.isConnected || !binding) {
                activeParticleGroups.delete(group);
                return;
            }
            const scene = group.closest(".energy-prepared-topology")
                || group.closest("[data-topology-instance]") || group;
            if (!scene.getClientRects().length) {
                binding.state.updatedAt = now;
                return;
            }
            visibleGroups = true;
            advanceParticleState(binding.state, now);
            positionParticleGroup(binding);
        });
        if (activeParticleGroups.size) {
            particleAnimationFrame = visibleGroups
                ? requestAnimationFrame(animateParticleGroups)
                : setTimeout(() => animateParticleGroups(performance.now()), 250);
        }
    }

    function registerParticleGroup(group, path, particles, state) {
        let pathLength = 0;
        try {
            pathLength = path.getTotalLength();
        } catch (_error) {
            pathLength = 0;
        }
        group.__heoParticleBinding = {
            path: path,
            pathLength: pathLength,
            particles: particles,
            state: state,
        };
        activeParticleGroups.add(group);
        positionParticleGroup(group.__heoParticleBinding);
        if (particleAnimationFrame === null) {
            particleAnimationFrame = requestAnimationFrame(animateParticleGroups);
        }
    }

    function unregisterParticleGroup(group) {
        activeParticleGroups.delete(group);
        delete group.__heoParticleBinding;
    }

    function stablePhaseSeed(edgeId) {
        let hash = 0;
        for (let index = 0; index < edgeId.length; index += 1) {
            hash = ((hash << 5) - hash + edgeId.charCodeAt(index)) >>> 0;
        }
        return ((hash % 1009) + 0.5) / 1009;
    }

    function initialPhysicalPhase(item, index, previousPhases, now) {
        const plan = item.particles;
        const direction = plan.direction === "reverse" ? -1 : 1;
        const anchor = previousPhases && previousPhases.length
            ? previousPhases[0]
            : stablePhaseSeed(item.id)
                + direction * now / 1000 / Math.max(0.001, plan.duration);
        return positiveModulo(anchor + index / plan.count, 1);
    }

    function updateParticleGroup(
        group,
        item,
        previousPhases,
        now,
    ) {
        const plan = item.particles;
        group.setAttribute("class", "topology-svg-edge-particles");
        group.dataset.topologyEdgeId = item.id;
        const phases = [];
        const existingParticles = Array.from(group.children).filter(
            (element) => element.tagName.toLowerCase() === "ellipse",
        );
        for (let index = 0; index < plan.count; index += 1) {
            const particle = existingParticles[index] || svgElement("ellipse");
            Object.entries({
                rx: plan.radius,
                ry: plan.radius,
                fill: item.color,
                opacity: ".88",
                "data-energy-circle-radius": plan.radius,
                "data-flow-speed": plan.speed,
                "data-flow-gap": plan.gap,
                "data-flow-direction": plan.direction,
            }).forEach(([key, value]) => {
                particle.setAttribute(key, String(value));
            });
            const physicalPhase = initialPhysicalPhase(
                item,
                index,
                previousPhases,
                now,
            );
            phases.push(physicalPhase);
            particle.querySelectorAll("animateMotion").forEach((motion) => {
                motion.remove();
            });
            if (!particle.parentNode) group.appendChild(particle);
        }
        existingParticles.slice(plan.count).forEach((particle) => {
            particle.remove();
        });
        return {
            particles: Array.from(group.children).filter(
                (element) => element.tagName.toLowerCase() === "ellipse",
            ),
            phases: phases,
        };
    }

    function directChildrenByEdgeId(layer) {
        return new Map(Array.from(layer.children).map((element) => [
            element.dataset.topologyEdgeId,
            element,
        ]));
    }

    function ensureSvg(host, width, height) {
        let svg = Array.from(host.children).find(
            (element) => element.classList.contains("topology-edge-svg"),
        );
        if (!svg) {
            svg = svgElement("svg", { class: "topology-edge-svg" });
            host.replaceChildren(svg);
        }
        svg.setAttribute("viewBox", "0 0 " + width + " " + height);
        svg.setAttribute("preserveAspectRatio", "none");
        svg.setAttribute("aria-hidden", "true");

        let paths = Array.from(svg.children).find(
            (element) => element.classList.contains("topology-edge-path-layer"),
        );
        if (!paths) {
            paths = svgElement("g", { class: "topology-edge-path-layer" });
            svg.appendChild(paths);
        }
        let particles = Array.from(svg.children).find(
            (element) => element.classList.contains("topology-edge-particle-layer"),
        );
        if (!particles) {
            particles = svgElement("g", {
                class: "topology-edge-particle-layer",
            });
            svg.appendChild(particles);
        }
        return { paths: paths, particles: particles };
    }

    function updateStorageBand(group, item, className, width, stroke, offsetY) {
        let band = group.querySelector("." + className);
        if (!item.storage_split || !(width > 0)) {
            if (band) band.remove();
            return;
        }
        if (!band) {
            band = createPath(item, className, width, stroke);
            group.appendChild(band);
        } else {
            updatePath(band, item, width, stroke);
        }
        band.setAttribute("transform", "translate(0 " + offsetY + ")");
        band.setAttribute("pointer-events", "none");
    }

    function updateEdgeGroup(group, item) {
        group.setAttribute("class", "topology-svg-edge-group");
        group.dataset.topologyEdgeId = item.id;
        let line = group.querySelector(".topology-svg-edge-line");
        if (!line) {
            line = createPath(
                item,
                "topology-svg-edge-line",
                item.width,
                item.color,
            );
            group.appendChild(line);
        } else {
            updatePath(line, item, item.width, item.color);
        }
        // Die Ladebreite bleibt unter beiden Speicherbändern sichtbar.
        // Das Verlustband tönt diese Grundkante je nach Theme ab oder auf.
        const split = item.storage_split || {};
        updateStorageBand(
            group, item, "topology-svg-edge-storage-discharge",
            Number(split.discharged_width) || 0,
            item.color,
            Number(split.discharged_offset_y) || 0,
        );
        updateStorageBand(
            group, item, "topology-svg-edge-storage-loss",
            Number(split.loss_width) || 0,
            item.color,
            Number(split.loss_offset_y) || 0,
        );
        let hitbox = group.querySelector(".topology-svg-edge-hitbox");
        if (!hitbox) {
            hitbox = createPath(
                item,
                "topology-svg-edge-hitbox",
                Math.max(14, Number(item.width) || 0),
                "transparent",
            );
            group.appendChild(hitbox);
        } else {
            updatePath(
                hitbox,
                item,
                Math.max(14, Number(item.width) || 0),
                "transparent",
            );
        }
        group.appendChild(hitbox);
        hitbox.setAttribute("opacity", "1");
        if (item.hover_focus) {
            hitbox.dataset.topologyEdgeFocus = "true";
        } else {
            delete hitbox.dataset.topologyEdgeFocus;
        }
        if (item.anchor) {
            hitbox.dataset.topologyAction = "result-edge";
            hitbox.dataset.topologyAnchor = item.anchor;
            hitbox.setAttribute("tabindex", "0");
            hitbox.setAttribute("role", "button");
            if (item.label) hitbox.setAttribute("aria-label", item.label);
        } else {
            delete hitbox.dataset.topologyAction;
            delete hitbox.dataset.topologyAnchor;
            hitbox.removeAttribute("tabindex");
            hitbox.removeAttribute("role");
            hitbox.removeAttribute("aria-label");
        }
        if (item.hover_focus && item.label) {
            hitbox.setAttribute("aria-label", item.label);
        }
        return line;
    }

    function renderHost(host) {
        if (!host || !host.dataset.topologyEdgePlan) return;
        const serialized = host.dataset.topologyEdgePlan;
        if (host.dataset.topologyRenderedPlan === serialized) return;
        const particleStates = instanceParticleStates(host);
        const now = performance.now();
        let plan;
        try {
            plan = JSON.parse(serialized);
        } catch (_error) {
            host.replaceChildren();
            host.dataset.topologyRenderedPlan = "invalid";
            return;
        }
        const layers = ensureSvg(
            host,
            Number(host.dataset.topologyCanvasWidth) || 1600,
            Number(host.dataset.topologyCanvasHeight) || 820,
        );
        const pathGroups = directChildrenByEdgeId(layers.paths);
        const particleGroups = directChildrenByEdgeId(layers.particles);
        const activeEdgeIds = new Set();
        plan.forEach((item) => {
            activeEdgeIds.add(item.id);
            let group = pathGroups.get(item.id);
            if (!group) {
                group = svgElement("g");
                layers.paths.appendChild(group);
            }
            const line = updateEdgeGroup(group, item);

            const previousState = particleStates.get(item.id);
            if (previousState) {
                // Erst mit den alten Parametern bis exakt zum Tick fortschreiben;
                // danach dürfen Tempo und Richtung ohne Positionssprung wechseln.
                advanceParticleState(previousState, now);
            }
            const previousPhases = previousState
                ? previousState.phases.slice()
                : null;
            let particleGroup = particleGroups.get(item.id);
            if (item.particles && item.particles.count) {
                if (!particleGroup) {
                    particleGroup = svgElement("g");
                    layers.particles.appendChild(particleGroup);
                }
                const particleResult = updateParticleGroup(
                    particleGroup,
                    item,
                    previousPhases,
                    now,
                );
                const state = previousState || {};
                state.phases = particleResult.phases;
                state.duration = item.particles.duration;
                state.direction = item.particles.direction;
                state.updatedAt = now;
                particleStates.set(item.id, state);
                registerParticleGroup(
                    particleGroup,
                    line,
                    particleResult.particles,
                    state,
                );
            } else if (particleGroup) {
                unregisterParticleGroup(particleGroup);
                particleGroup.remove();
            }
        });
        pathGroups.forEach((group, edgeId) => {
            if (!activeEdgeIds.has(edgeId)) group.remove();
        });
        particleGroups.forEach((group, edgeId) => {
            if (!activeEdgeIds.has(edgeId)) {
                unregisterParticleGroup(group);
                group.remove();
            }
        });
        host.dataset.topologyRenderedPlan = serialized;
    }

    function renderAll(root) {
        (root || document).querySelectorAll("[data-topology-edge-plan]")
            .forEach(renderHost);
    }

    function observe() {
        renderAll();
        new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === "attributes") renderHost(mutation.target);
                mutation.addedNodes.forEach((node) => {
                    if (!(node instanceof Element)) return;
                    if (node.matches("[data-topology-edge-plan]")) renderHost(node);
                    renderAll(node);
                });
            });
        }).observe(document.documentElement, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["data-topology-edge-plan"],
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", observe, { once: true });
    } else {
        observe();
    }

    window.HEOTopologyEdges = {
        renderAll: renderAll,
    };
}());

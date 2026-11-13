(function () {
    "use strict";

    function clamp(value, minimum, maximum) {
        return Math.max(minimum, Math.min(maximum, value));
    }

    function findAnchor(viewport, attribute, key) {
        if (!viewport || !key) return null;
        var selector = "[" + attribute + "]";
        var candidates = viewport.querySelectorAll(selector);
        for (var index = 0; index < candidates.length; index += 1) {
            if (candidates[index].getAttribute(attribute) === key) {
                return candidates[index];
            }
        }
        return null;
    }

    function overflowAmount(left, top, width, height, boundsWidth, boundsHeight, margin) {
        return Math.max(0, margin - left)
            + Math.max(0, margin - top)
            + Math.max(0, left + width + margin - boundsWidth)
            + Math.max(0, top + height + margin - boundsHeight);
    }

    function tangentCandidates(nodeRect, localX, localY, radius, dimensions, boundsWidth, boundsHeight) {
        var nodeRadius = Math.min(nodeRect.width, nodeRect.height) / 2;
        var verticalHalfSegment = Math.max(0, (nodeRect.height - nodeRect.width) / 2);
        var horizontalHalfSegment = Math.max(0, (nodeRect.width - nodeRect.height) / 2);
        var result = [];
        [-1, 1].forEach(function (directionX) {
            [-1, 1].forEach(function (directionY) {
                for (var degrees = 0; degrees <= 90; degrees += 5) {
                    var radians = degrees * Math.PI / 180;
                    var normalX = directionX * Math.cos(radians);
                    var normalY = directionY * Math.sin(radians);
                    var skeletonXs = [localX + (horizontalHalfSegment ? directionX * horizontalHalfSegment : 0)];
                    var skeletonYs = [localY + (verticalHalfSegment ? directionY * verticalHalfSegment : 0)];
                    if (verticalHalfSegment && Math.abs(normalY) < 0.0001) {
                        skeletonYs = [localY - verticalHalfSegment, localY, localY + verticalHalfSegment];
                    }
                    if (horizontalHalfSegment && Math.abs(normalX) < 0.0001) {
                        skeletonXs = [localX - horizontalHalfSegment, localX, localX + horizontalHalfSegment];
                    }
                    skeletonXs.forEach(function (skeletonX) {
                        skeletonYs.forEach(function (skeletonY) {
                            var distance = nodeRadius + radius;
                            var cornerX = skeletonX + normalX * distance;
                            var cornerY = skeletonY + normalY * distance;
                            var left = directionX > 0 ? cornerX - radius : cornerX + radius - dimensions.width;
                            var top = directionY > 0 ? cornerY - radius : cornerY + radius - dimensions.height;
                            var overflow = overflowAmount(left, top, dimensions.width, dimensions.height, boundsWidth, boundsHeight, dimensions.margin);
                            result.push({
                                left: left,
                                top: top,
                                score: (overflow > 0.5 ? 1000000 : 0) + overflow * 1000 + Math.abs(degrees - 45)
                            });
                        });
                    });
                }
            });
        });
        result.sort(function (first, second) { return first.score - second.score; });
        return result;
    }

    function pointerPlacement(pointer, shellRect, dimensions) {
        var gap = 18;
        var localX = pointer.clientX - shellRect.left;
        var localY = pointer.clientY - shellRect.top;
        var right = localX + gap;
        var left = localX - gap - dimensions.width;
        var below = localY + gap;
        var above = localY - gap - dimensions.height;
        return {
            left: Math.max(0, right + dimensions.width + dimensions.margin - shellRect.width)
                <= Math.max(0, dimensions.margin - left) ? right : left,
            top: Math.max(0, below + dimensions.height + dimensions.margin - shellRect.height)
                <= Math.max(0, dimensions.margin - above) ? below : above
        };
    }

    function positionCard(options) {
        var viewport = options.viewport;
        var shell = options.shell;
        var card = options.card;
        var anchor = findAnchor(viewport, options.anchorAttribute || "data-topology-anchor", options.anchorKey);
        if (!viewport || !shell || !card || !anchor) return null;
        var viewportRect = viewport.getBoundingClientRect();
        if (viewportRect.width <= 0 || viewportRect.height <= 0) return null;
        var shellRect = shell.getBoundingClientRect();
        var nodeRect = anchor.getBoundingClientRect();
        var size = options.sizeCard(card, shellRect.width, shellRect.height);
        var localX = (nodeRect.left + nodeRect.right) / 2 - shellRect.left;
        var localY = (nodeRect.top + nodeRect.bottom) / 2 - shellRect.top;
        var radius = clamp(Math.min(nodeRect.width, nodeRect.height) / 2, 28, 76);
        var placement = options.preferredPosition
            || (options.pointerPosition
                && pointerPlacement(options.pointerPosition, shellRect, size))
            || tangentCandidates(nodeRect, localX, localY, radius, size, shellRect.width, shellRect.height)[0];
        var maximumLeft = Math.max(size.margin, shellRect.width - size.width - size.margin);
        var maximumTop = Math.max(size.margin, shellRect.height - size.height - size.margin);
        var left = Math.round(clamp(placement.left, size.margin, maximumLeft));
        var top = Math.round(clamp(placement.top, size.margin, maximumTop));
        card.style.left = left + "px";
        card.style.top = top + "px";
        card.style.setProperty("--topology-overlay-radius", Math.round(radius) + "px");
        card.style.setProperty("--topology-overlay-color", options.color || "#43564d");
        shell.classList.add("is-positioned");
        return { radius: radius, anchor: anchor, left: left, top: top };
    }

    window.TopologyOverlay = {
        findAnchor: findAnchor,
        positionCard: positionCard
    };
}());

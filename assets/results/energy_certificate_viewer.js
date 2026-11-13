(function () {
    "use strict";

    const DEFAULT_COPY_LABEL = "Seite als Bild kopieren";
    const viewers = [
        {
            stageId: "energy-certificate-page-stage",
            labelId: "energy-certificate-page-label",
            copyId: "energy-certificate-copy",
            previousId: "energy-certificate-previous",
            nextId: "energy-certificate-next",
            widthVariable: "--energy-certificate-economic-width"
        },
        {
            stageId: "energy-certificate-ecological-page-stage",
            labelId: "energy-certificate-ecological-page-label",
            copyId: "energy-certificate-ecological-copy",
            previousId: "energy-certificate-ecological-previous",
            nextId: "energy-certificate-ecological-next",
            widthVariable: "--energy-certificate-ecological-width"
        }
    ].map(function (viewer) {
        return Object.assign(viewer, {
            stage: null,
            attributeObserver: null,
            sizeObserver: null,
            pendingImage: null,
            requestedSource: null,
            displayedSource: null,
            loadSequence: 0
        });
    });

    function pageImage(viewer) {
        return viewer.stage && viewer.stage.querySelector(".energy-certificate-page-image");
    }

    function syncToolbarWidth(viewer) {
        const image = pageImage(viewer);
        const width = image && image.getAttribute("src")
            ? image.getBoundingClientRect().width
            : 0;
        document.documentElement.style.setProperty(viewer.widthVariable, width + "px");
    }

    function setDisplayedPageLabel(viewer) {
        const label = document.getElementById(viewer.labelId);
        if (label && viewer.stage) {
            label.textContent = viewer.stage.getAttribute("data-page-label") || "Seite 1 / 1";
        }
    }

    function resetCopyButton(viewer) {
        const button = document.getElementById(viewer.copyId);
        if (!button) return;
        const label = button.querySelector(".energy-certificate-copy-label");
        if (label) label.textContent = DEFAULT_COPY_LABEL;
        button.classList.remove("is-success", "is-error");
    }

    function updatePageImage(viewer) {
        const stage = viewer.stage;
        if (!stage) return;
        const source = stage.getAttribute("data-page-src") || "";
        if (source === viewer.requestedSource) {
            if (source === viewer.displayedSource) setDisplayedPageLabel(viewer);
            return;
        }

        viewer.requestedSource = source;
        const sequence = ++viewer.loadSequence;
        if (viewer.pendingImage) {
            viewer.pendingImage.onload = null;
            viewer.pendingImage.onerror = null;
            viewer.pendingImage = null;
        }

        const image = pageImage(viewer);
        if (!image) return;
        stage.classList.remove("is-error");

        if (!source) {
            viewer.displayedSource = null;
            stage.classList.remove("is-ready");
            image.removeAttribute("src");
            setDisplayedPageLabel(viewer);
            resetCopyButton(viewer);
            return;
        }
        if (source === viewer.displayedSource) {
            setDisplayedPageLabel(viewer);
            return;
        }

        const preload = new Image();
        viewer.pendingImage = preload;

        function isCurrentRequest() {
            return sequence === viewer.loadSequence && viewer.stage === stage &&
                stage.getAttribute("data-page-src") === source;
        }

        function showPage() {
            if (!isCurrentRequest()) return;
            viewer.pendingImage = null;
            image.src = source;
            viewer.displayedSource = source;
            stage.classList.add("is-ready");
            setDisplayedPageLabel(viewer);
            resetCopyButton(viewer);
        }

        preload.onload = function () {
            if (typeof preload.decode === "function") {
                preload.decode().then(showPage, showPage);
            } else {
                showPage();
            }
        };
        preload.onerror = function () {
            if (!isCurrentRequest()) return;
            viewer.pendingImage = null;
            viewer.displayedSource = null;
            image.removeAttribute("src");
            stage.classList.remove("is-ready");
            stage.classList.add("is-error");
            setDisplayedPageLabel(viewer);
        };
        preload.src = source;
    }

    function bindPageStage(viewer) {
        const stage = document.getElementById(viewer.stageId);
        if (stage === viewer.stage) return;
        if (viewer.attributeObserver) viewer.attributeObserver.disconnect();
        if (viewer.sizeObserver) viewer.sizeObserver.disconnect();
        ++viewer.loadSequence;
        viewer.stage = stage;
        viewer.pendingImage = null;
        viewer.requestedSource = null;
        viewer.displayedSource = null;
        if (!stage) {
            syncToolbarWidth(viewer);
            return;
        }
        viewer.attributeObserver = new MutationObserver(function () {
            updatePageImage(viewer);
        });
        viewer.attributeObserver.observe(stage, {
            attributes: true,
            attributeFilter: ["data-page-src", "data-page-label"]
        });
        viewer.sizeObserver = new ResizeObserver(function () {
            syncToolbarWidth(viewer);
        });
        viewer.sizeObserver.observe(stage);
        viewer.sizeObserver.observe(pageImage(viewer));
        syncToolbarWidth(viewer);
        updatePageImage(viewer);
    }

    function startPageViewer() {
        viewers.forEach(bindPageStage);
        new MutationObserver(function () {
            viewers.forEach(function (viewer) {
                if (!viewer.stage || !viewer.stage.isConnected) bindPageStage(viewer);
            });
        }).observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", startPageViewer, { once: true });
    } else {
        startPageViewer();
    }

    function certificateViewIsVisible() {
        const view = document.getElementById("energy-certificate-view");
        return Boolean(view && view.offsetParent !== null);
    }

    document.addEventListener("keydown", function (event) {
        if (!certificateViewIsVisible()) return;
        const target = event.target;
        if (target && /INPUT|TEXTAREA|SELECT/.test(target.tagName)) return;
        const direction = event.key === "ArrowLeft" ? "previousId"
            : event.key === "ArrowRight" ? "nextId" : null;
        if (!direction) return;

        const pane = target && target.closest && target.closest(".energy-certificate-pane");
        const viewer = pane && pane.classList.contains("energy-certificate-pane--ecological")
            ? viewers[1] : viewers[0];
        const button = document.getElementById(viewer[direction]);
        if (!button || button.disabled) return;
        event.preventDefault();
        button.click();
    });

    document.addEventListener("load", function (event) {
        const viewer = viewers.find(function (item) {
            return event.target && event.target.id === item.stageId.replace("-stage", "-image");
        });
        if (viewer) resetCopyButton(viewer);
    }, true);

    document.addEventListener("click", async function (event) {
        const viewer = viewers.find(function (item) {
            return event.target.closest && event.target.closest("#" + item.copyId);
        });
        if (!viewer) return;

        const button = document.getElementById(viewer.copyId);
        const image = pageImage(viewer);
        if (!button || !image || !image.src) return;

        button.disabled = true;
        const label = button.querySelector(".energy-certificate-copy-label");
        if (label) label.textContent = "Wird kopiert …";
        button.classList.remove("is-success", "is-error");
        try {
            if (!navigator.clipboard || typeof ClipboardItem === "undefined") {
                throw new Error("Bild-Zwischenablage wird nicht unterstützt");
            }
            const response = await fetch(image.src, { cache: "force-cache" });
            if (!response.ok) throw new Error("Bild konnte nicht geladen werden");
            const blob = await response.blob();
            const pngBlob = blob.type === "image/png"
                ? blob
                : new Blob([await blob.arrayBuffer()], { type: "image/png" });
            await navigator.clipboard.write([
                new ClipboardItem({ "image/png": pngBlob })
            ]);
            if (label) label.textContent = "Seite kopiert ✓";
            button.classList.add("is-success");
        } catch (error) {
            if (label) label.textContent = "Kopieren nicht möglich";
            button.classList.add("is-error");
        } finally {
            button.disabled = false;
        }
    });
})();

/* ####################################################################
   ##  ACHTUNG: REKONSTRUIERTE DATEI (22.10.2026)                     ##
   ####################################################################
   Nur die ersten 4.096 Bytes (ein Speicherblock) waren durch einen
   Dateisystemschaden mit fremdem Inhalt und Nullbytes ueberschrieben.
   Original archiviert unter _archiv_beschaedigt_20261022/assets/.
   Wiederhergestellt mit KI-Unterstuetzung (Claude):
   - Bytes 0 bis 4.095 aus 'sed -n 1,240p assets/dev_tools.js' vom
     15.10.2026 im Codex-Protokoll 10/15/rollout-2026-10-15T13-39-46-...
   - Rest unveraendert aus der beschaedigten Datei.
   - Danach die Codex-Aenderung vom 21.10.2026 18:35 (UTC) nachgetragen
     (Bedingung panel.closest(".dashboard-info-flip-inner")), die im
     beschaedigten Stand fehlte.
   Pruefung: Der Protokolltext passt exakt an die Blockgrenze (die
   folgenden 3.907 Bytes stimmen ueberein). Groesse 26.180 Bytes wie
   im Original, JS-Syntaxpruefung bestanden.
   #################################################################### */

(function () {
    "use strict";

    if (window.HEODevTools) {
        return;
    }

    var GRID_STORAGE_KEY = "heo.devTools.gridVisible";
    var GRID_HIDDEN_CLASS = "heo-grid-lines-hidden";
    var NATIVE_CAPTURE_CLASS = "heo-native-capture";
    var MAIN_PANEL_CAPTURE_CLASS = "heo-main-panel-native-capture";
    var CAPTURE_ROOT_ATTRIBUTE = "data-heo-native-capture-root";
    var CAPTURE_MODE_MAIN_PANEL = "main-panel";
    var CAPTURE_MODE_DASHBOARD = "dashboard";
    var CAPTURE_MODE_APP = "app";
    var CAPTURE_FRAME_RATE = 1;
    var CAPTURE_FRAME_WAIT_MS = 1500;
    var registeredFrames = new WeakSet();
    var gridVisible = readGridVisible();
    var THEME_STORAGE_KEY = "heo.devTools.darkMode";
    var darkMode = readDarkMode();
    var menuOpen = false;
    var captureRunning = false;
    var captureStream = null;
    var captureVideo = null;

    function readDarkMode() {
        try {
            return window.localStorage.getItem(THEME_STORAGE_KEY) === "true";
        } catch (_error) {
            return false;
        }
    }

    function updateThemeUI() {
        var button = document.querySelector('[data-dev-tool="dark-mode"]');
        if (button) {
            button.classList.toggle("is-active", darkMode);
            button.setAttribute("aria-checked", darkMode ? "true" : "false");
            button.setAttribute("title", darkMode ? "Dark Mode ausschalten" : "Dark Mode einschalten");
        }
        var logo = document.querySelector(".header-logo");
        var source = darkMode ? "/assets/images/Logo weiß.png" : "/assets/images/Logo grün.png";
        if (logo && logo.getAttribute("src") !== source) {
            logo.setAttribute("src", source);
        }
    }

    function setDarkMode(enabled, persist) {
        darkMode = Boolean(enabled);
        document.documentElement.dataset.theme = darkMode ? "dark" : "light";
        if (persist !== false) {
            try {
                window.localStorage.setItem(THEME_STORAGE_KEY, String(darkMode));
            } catch (_error) {
                /* Ohne Browser-Speicher bleibt der Switch weiterhin bedienbar. */
            }
        }
        updateThemeUI();
    }

    function readGridVisible() {
        try {
            return window.localStorage.getItem(GRID_STORAGE_KEY) === "true";
        } catch (_error) {
            return false;
        }
    }

    function persistGridVisible(visible) {
        try {
            window.localStorage.setItem(GRID_STORAGE_KEY, visible ? "true" : "false");
        } catch (_error) {
            /* Private Browsermodi dürfen die Einstellung flüchtig halten. */
        }
    }

    function setFrameGridVisible(frame, visible) {
        try {
            var frameDocument = frame.contentDocument;
            if (frameDocument && frameDocument.documentElement) {
                frameDocument.documentElement.classList.toggle(
                    GRID_HIDDEN_CLASS,
                    !visible
                );
            }
        } catch (_error) {
            /* Fremde Frames werden nicht verändert; die App-Frames sind same-origin. */
        }
    }

    function registerFrame(frame) {
        if (!registeredFrames.has(frame)) {
            frame.addEventListener("load", function () {
                setFrameGridVisible(frame, gridVisible);
            });
            registeredFrames.add(frame);
        }
        setFrameGridVisible(frame, gridVisible);
    }

    function syncAllFrames() {
        document.querySelectorAll("iframe").forEach(registerFrame);
    }

    function updateGridButton() {
        var button = document.querySelector('[data-dev-tool="grid"]');
        if (!button) {
            return;
        }
        var label = gridVisible
            ? "Rasterlinien ausblenden"
            : "Rasterlinien einblenden";
        button.classList.toggle("is-active", gridVisible);
        button.setAttribute("aria-pressed", gridVisible ? "true" : "false");
        button.setAttribute("aria-label", label);
        button.setAttribute("title", label);
    }

    function setGridVisible(visible, persist) {
        gridVisible = Boolean(visible);
        document.documentElement.classList.toggle(
            GRID_HIDDEN_CLASS,
            !gridVisible
        );
        if (persist !== false) {
            persistGridVisible(gridVisible);
        }
        updateGridButton();
        syncAllFrames();
    }

    function updateMenuUI() {
        var dock = document.getElementById("dev-tools-dock");
        var panel = document.getElementById("dev-tools-panel");
        var toggle = document.getElementById("dev-tools-nav-button");
        if (!dock || !panel || !toggle) {
            return;
        }
        var label = menuOpen
            ? "Entwicklerwerkzeuge schließen"
            : "Entwicklerwerkzeuge öffnen";
        dock.classList.toggle("is-open", menuOpen);
        panel.setAttribute("aria-hidden", menuOpen ? "false" : "true");
        toggle.setAttribute("aria-expanded", menuOpen ? "true" : "false");
        toggle.setAttribute("aria-label", label);
        toggle.setAttribute("title", label);
        panel.querySelectorAll("button").forEach(function (button) {
            button.tabIndex = menuOpen ? 0 : -1;
        });
    }

    function setMenuOpen(open) {
        menuOpen = Boolean(open);
        updateMenuUI();
    }

    function refreshTopologyLabels(target) {
        if (
            target && window.HEOTopologyLabels &&
            typeof window.HEOTopologyLabels.updateAll === "function"
        ) {
            window.HEOTopologyLabels.updateAll(target);
        }
    }

    function stopCaptureMedia() {
        var video = captureVideo;
        var stream = captureStream;
        captureVideo = null;
        captureStream = null;

        if (video) {
            video.pause();
            video.srcObject = null;
            video.remove();
        }
        if (stream) {
            stream.getTracks().forEach(function (track) {
                if (track.readyState !== "ended") {
                    track.stop();
                }
            });
        }
    }

    function captureMediaIsActive() {
        if (!captureStream || !captureVideo) {
            return false;
        }
        var track = captureStream.getVideoTracks()[0];
        return Boolean(
            track && track.readyState === "live" &&
            captureVideo.srcObject === captureStream
        );
    }

    function limitCaptureFrameRate(track) {
        if (typeof track.applyConstraints !== "function") {
            return Promise.resolve();
        }
        return track.applyConstraints({
            frameRate: {
                ideal: CAPTURE_FRAME_RATE,
                max: CAPTURE_FRAME_RATE,
            },
        }).catch(function (error) {
            // Die Aufnahmeanforderung enthält dasselbe Limit bereits. Falls ein
            // Browser die nachträgliche Einschränkung nicht unterstützt, bleibt
            // die Screenshot-Funktion deshalb trotzdem verwendbar.
            window.console.warn(
                "HEO-Screenshot: 1-FPS-Limit nicht bestätigt:",
                error
            );
        });
    }

    function waitForCaptureVideo(stream) {
        return new Promise(function (resolve, reject) {
            var video = document.createElement("video");
            var starting = false;
            var settled = false;
            var timeout = window.setTimeout(function () {
                fail(new Error("Der freigegebene Tab liefert kein Bild."));
            }, 10000);

            function fail(error) {
                if (settled) {
                    return;
                }
                settled = true;
                window.clearTimeout(timeout);
                video.pause();
                video.srcObject = null;
                video.remove();
                if (captureVideo === video) {
                    captureVideo = null;
                }
                reject(error);
            }

            function finish() {
                if (starting || !video.videoWidth || !video.videoHeight) {
                    return;
                }
                var track = stream.getVideoTracks()[0];
                if (
                    !track || track.readyState !== "live" ||
                    captureStream !== stream
                ) {
                    fail(new Error("Die Tab-Freigabe wurde beendet."));
                    return;
                }
                starting = true;
                window.clearTimeout(timeout);
                video.play().then(function () {
                    var activeTrack = stream.getVideoTracks()[0];
                    if (
                        !activeTrack || activeTrack.readyState !== "live" ||
                        captureStream !== stream
                    ) {
                        fail(new Error("Die Tab-Freigabe wurde beendet."));
                        return;
                    }
                    settled = true;
                    resolve(video);
                }).catch(fail);
            }

            video.autoplay = true;
            video.muted = true;
            video.playsInline = true;
            video.setAttribute("aria-hidden", "true");
            video.style.position = "fixed";
            video.style.left = "-10000px";
            video.style.top = "0";
            video.style.width = "1px";
            video.style.height = "1px";
            video.style.opacity = "0";
            video.style.pointerEvents = "none";
            video.addEventListener("loadedmetadata", finish);
            document.body.appendChild(video);
            captureVideo = video;
            video.srcObject = stream;
            finish();
        });
    }

    function requestCurrentTabVideo() {
        if (
            !window.isSecureContext || !navigator.mediaDevices ||
            typeof navigator.mediaDevices.getDisplayMedia !== "function"
        ) {
            return Promise.reject(new Error(
                "Die Tab-Aufnahme benötigt localhost oder HTTPS und einen " +
                "Browser mit Bildschirmfreigabe."
            ));
        }

        if (captureMediaIsActive()) {
            return Promise.resolve(captureVideo);
        }
        stopCaptureMedia();

        var streamPromise;
        try {
            // Die nicht verpflichtenden Hinweise stellen „Dieser Tab“ im
            // Browserdialog nach vorn. Die Auswahl bleibt aus Sicherheitsgründen
            // immer beim Benutzer.
            streamPromise = navigator.mediaDevices.getDisplayMedia({
                video: {
                    displaySurface: "browser",
                    frameRate: {
                        ideal: CAPTURE_FRAME_RATE,
                        max: CAPTURE_FRAME_RATE,
                    },
                },
                audio: false,
                preferCurrentTab: true,
                selfBrowserSurface: "include",
            });
        } catch (error) {
            return Promise.reject(error);
        }

        return streamPromise.then(function (stream) {
            var track = stream.getVideoTracks()[0];
            if (!track) {
                stream.getTracks().forEach(function (item) {
                    item.stop();
                });
                throw new Error("Die Freigabe enthält kein Bild.");
            }
            var settings = typeof track.getSettings === "function"
                ? track.getSettings()
                : {};
            if (settings.displaySurface && settings.displaySurface !== "browser") {
                stream.getTracks().forEach(function (item) {
                    item.stop();
                });
                throw new Error(
                    "Bitte im Freigabedialog „Dieser Tab“ auswählen."
                );
            }
            captureStream = stream;
            track.addEventListener("ended", stopCaptureMedia, {once: true});
            return limitCaptureFrameRate(track).then(function () {
                return waitForCaptureVideo(stream);
            }).catch(function (error) {
                stopCaptureMedia();
                throw error;
            });
        });
    }

    function collectCaptureDocuments(target) {
        var documents = [];
        var seen = new Set();

        function addDocument(currentDocument) {
            if (!currentDocument || seen.has(currentDocument)) {
                return;
            }
            seen.add(currentDocument);
            documents.push(currentDocument);
            currentDocument.querySelectorAll("iframe").forEach(function (frame) {
                try {
                    addDocument(frame.contentDocument);
                } catch (_error) {
                    /* Fremde Frames werden vom Browser selbst zusammengesetzt. */
                }
            });
        }

        addDocument(target.ownerDocument);
        return documents;
    }

    function waitForCapturePaint(target) {
        var fontPromises = collectCaptureDocuments(target).map(
            function (currentDocument) {
                if (!currentDocument.fonts || !currentDocument.fonts.ready) {
                    return Promise.resolve();
                }
                return currentDocument.fonts.ready.catch(function () {
                    return undefined;
                });
            }
        );
        return Promise.all(fontPromises).then(function () {
            return new Promise(function (resolve) {
                window.requestAnimationFrame(function () {
                    window.requestAnimationFrame(resolve);
                });
            });
        });
    }

    function waitForCapturedFrame(video) {
        return new Promise(function (resolve) {
            var completed = false;
            var fallback = window.setTimeout(finish, CAPTURE_FRAME_WAIT_MS);

            function finish() {
                if (completed) {
                    return;
                }
                completed = true;
                window.clearTimeout(fallback);
                resolve();
            }

            if (typeof video.requestVideoFrameCallback === "function") {
                video.requestVideoFrameCallback(finish);
            }
        });
    }

    function setNativeCaptureState(target, mode) {
        var root = document.documentElement;
        var state = {
            hadNativeClass: root.classList.contains(NATIVE_CAPTURE_CLASS),
            hadMainPanelClass: root.classList.contains(MAIN_PANEL_CAPTURE_CLASS),
            previousRootValue: target.getAttribute(CAPTURE_ROOT_ATTRIBUTE),
        };
        root.classList.add(NATIVE_CAPTURE_CLASS);
        target.setAttribute(CAPTURE_ROOT_ATTRIBUTE, mode);
        if (mode === CAPTURE_MODE_MAIN_PANEL) {
            root.classList.add(MAIN_PANEL_CAPTURE_CLASS);
        }
        return state;
    }

    function clearNativeCaptureState(target, state) {
        if (!state) {
            return;
        }
        var root = document.documentElement;
        root.classList.toggle(
            NATIVE_CAPTURE_CLASS,
            state.hadNativeClass
        );
        root.classList.toggle(
            MAIN_PANEL_CAPTURE_CLASS,
            state.hadMainPanelClass
        );
        if (target && state.previousRootValue === null) {
            target.removeAttribute(CAPTURE_ROOT_ATTRIBUTE);
        } else if (target) {
            target.setAttribute(CAPTURE_ROOT_ATTRIBUTE, state.previousRootValue);
        }
    }

    function validateCaptureGeometry(video) {
        var viewportRatio = window.innerWidth / window.innerHeight;
        var videoRatio = video.videoWidth / video.videoHeight;
        if (
            !Number.isFinite(viewportRatio) || !Number.isFinite(videoRatio) ||
            Math.abs(videoRatio / viewportRatio - 1) > 0.035
        ) {
            throw new Error(
                "Die Freigabe passt nicht zum App-Viewport. Bitte „Dieser Tab“ " +
                "auswählen."
            );
        }
    }

    function cropCapturedFrame(video, target) {
        validateCaptureGeometry(video);
        var rect = target.getBoundingClientRect();
        var scaleX = video.videoWidth / window.innerWidth;
        var scaleY = video.videoHeight / window.innerHeight;
        var rightEdgeInset = (
            target.getAttribute(CAPTURE_ROOT_ATTRIBUTE) === CAPTURE_MODE_MAIN_PANEL
        ) ? Math.max(1, Math.ceil(scaleX)) : 0;
        // Die Crop-Kanten immer innerhalb des Elements halten. Rundung kann
        // rechts/unten einen Pixel des umgebenden Hintergrunds einschließen.
        // Beim Main-Panel wird rechts zusätzlich ein CSS-Pixel abgeschnitten,
        // da die native Tab-Aufnahme dort die äußere Rasterkante mitliefert.
        var sourceLeft = Math.max(0, Math.ceil(rect.left * scaleX));
        var sourceTop = Math.max(0, Math.ceil(rect.top * scaleY));
        var sourceRight = Math.min(
            video.videoWidth,
            Math.floor(rect.right * scaleX) - rightEdgeInset
        );
        var sourceBottom = Math.min(
            video.videoHeight,
            Math.floor(rect.bottom * scaleY)
        );
        var width = sourceRight - sourceLeft;
        var height = sourceBottom - sourceTop;
        if (width < 2 || height < 2) {
            throw new Error("Der Aufnahmebereich liegt außerhalb des Viewports.");
        }

        var canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        var context = canvas.getContext("2d", {alpha: false});
        if (!context) {
            throw new Error("Der Browser konnte kein PNG-Canvas erzeugen.");
        }
        context.drawImage(
            video,
            sourceLeft,
            sourceTop,
            width,
            height,
            0,
            0,
            width,
            height
        );
        return canvas;
    }

    function canvasToPngBlob(canvas) {
        return new Promise(function (resolve, reject) {
            canvas.toBlob(function (blob) {
                if (!blob) {
                    reject(new Error("Das PNG konnte nicht erzeugt werden."));
                    return;
                }
                resolve(blob);
            }, "image/png");
        });
    }

    function imageClipboardAvailable() {
        return Boolean(
            window.isSecureContext && navigator.clipboard &&
            typeof navigator.clipboard.write === "function" &&
            typeof window.ClipboardItem === "function"
        );
    }

    function copyCanvasToClipboard(canvas) {
        if (!imageClipboardAvailable()) {
            return Promise.reject(new Error(
                "Die Bild-Zwischenablage ist nur über localhost oder HTTPS verfügbar."
            ));
        }

        var pngBlob = canvasToPngBlob(canvas);
        var clipboardItem = new window.ClipboardItem({"image/png": pngBlob});
        return navigator.clipboard.write([clipboardItem]);
    }

    function captureElement(target, mode) {
        if (captureRunning || !target) {
            return Promise.reject(new Error("Kein Aufnahmebereich verfügbar."));
        }
        if (!imageClipboardAvailable()) {
            return Promise.reject(new Error(
                "Die Bild-Zwischenablage ist nur über localhost oder HTTPS verfügbar."
            ));
        }

        captureRunning = true;
        refreshTopologyLabels(target);
        var captureState = null;
        var canvasPromise = Promise.resolve().then(function () {
            captureState = setNativeCaptureState(target, mode);
            return waitForCapturePaint(target);
        }).then(function () {
            return requestCurrentTabVideo();
        }).then(function (video) {
            return waitForCapturedFrame(video).then(function () {
                return cropCapturedFrame(video, target);
            });
        }).finally(function () {
            clearNativeCaptureState(target, captureState);
        });

        return canvasPromise.then(copyCanvasToClipboard).finally(
            function () {
                captureRunning = false;
            }
        );
    }

    function activeMainPanelCaptureTarget(panel) {
        var flip = panel.closest(".dashboard-info-flip");
        if (!flip) {
            return panel;
        }

        var back = flip.querySelector(".dashboard-info-back");
        if (
            panel.closest(".dashboard-info-flip-inner") && back && (
                flip.classList.contains("is-flipped") ||
                back.getAttribute("aria-hidden") === "false"
            )
        ) {
            return back;
        }
        return panel;
    }

    function visibleMainPanel() {
        var panels = Array.prototype.slice.call(
            document.querySelectorAll('[data-heo-capture-target="main-panel"]')
        );
        var targets = panels.map(activeMainPanelCaptureTarget);
        return targets.find(function (target) {
            var rect = target.getBoundingClientRect();
            var style = window.getComputedStyle(target);
            if (
                rect.width <= 1 || rect.height <= 1 ||
                style.display === "none" || style.visibility === "hidden" ||
                style.opacity === "0"
            ) {
                return false;
            }
            var hit = document.elementFromPoint(
                rect.left + rect.width / 2,
                rect.top + rect.height / 2
            );
            return Boolean(hit && (hit === target || target.contains(hit)));
        }) || null;
    }

    function setCaptureButtonBusy(button, busy, fallbackTitle) {
        button.classList.toggle("is-busy", busy);
        button.disabled = busy;
        button.setAttribute("aria-busy", busy ? "true" : "false");
        if (busy) {
            button.setAttribute("title", "Bild wird kopiert …");
        } else if (fallbackTitle) {
            button.setAttribute("title", fallbackTitle);
        }
    }

    function runCapture(button, target, mode) {
        var originalTitle = button.getAttribute("title") || "Bild kopieren";
        setCaptureButtonBusy(button, true, originalTitle);
        captureElement(target, mode).then(function () {
            button.setAttribute("title", "Bild in die Zwischenablage kopiert");
            window.setTimeout(function () {
                button.setAttribute("title", originalTitle);
            }, 1500);
        }).catch(function (error) {
            window.console.error("HEO-Screenshot fehlgeschlagen:", error);
            var message = error && error.message
                ? error.message
                : "Aufnahme fehlgeschlagen – erneut versuchen";
            button.setAttribute("title", message);
            window.setTimeout(function () {
                button.setAttribute("title", originalTitle);
            }, 2600);
        }).finally(function () {
            setCaptureButtonBusy(button, false, button.getAttribute("title"));
        });
    }

    function handleToolClick(button) {
        var tool = button.dataset.devTool;
        if (tool === "dark-mode") {
            setDarkMode(!darkMode);
            return;
        }
        if (tool === "grid") {
            setGridVisible(!gridVisible, true);
            return;
        }
        if (tool === "capture-dashboard") {
            runCapture(
                button,
                document.querySelector(".dashboard-screen"),
                CAPTURE_MODE_DASHBOARD
            );
            return;
        }
        if (tool === "capture-main-panel") {
            runCapture(
                button,
                visibleMainPanel(),
                CAPTURE_MODE_MAIN_PANEL
            );
            return;
        }
        if (tool === "capture-app") {
            runCapture(
                button,
                document.querySelector(".app-shell"),
                CAPTURE_MODE_APP
            );
        }
    }

    document.addEventListener("click", function (event) {
        if (!(event.target instanceof Element)) {
            return;
        }
        var toggle = event.target.closest("[data-dev-tools-toggle]");
        if (toggle) {
            event.preventDefault();
            setMenuOpen(!menuOpen);
            return;
        }
        var tool = event.target.closest("[data-dev-tool]");
        if (tool) {
            event.preventDefault();
            handleToolClick(tool);
            return;
        }
        if (menuOpen && !event.target.closest("#dev-tools-dock")) {
            setMenuOpen(false);
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && menuOpen) {
            setMenuOpen(false);
            var toggle = document.getElementById("dev-tools-nav-button");
            if (toggle) {
                toggle.focus({preventScroll: true});
            }
        }
    });

    function refreshDynamicUI() {
        updateMenuUI();
        updateThemeUI();
        updateGridButton();
        syncAllFrames();
    }

    setDarkMode(darkMode, false);
    setGridVisible(gridVisible, false);
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", refreshDynamicUI, {once: true});
    } else {
        refreshDynamicUI();
    }

    new MutationObserver(refreshDynamicUI).observe(document.documentElement, {
        childList: true,
        subtree: true,
    });
    window.addEventListener("pagehide", stopCaptureMedia);

    window.HEODevTools = {
        setDarkMode: setDarkMode,
        setGridVisible: setGridVisible,
        captureDashboard: function () {
            return captureElement(
                document.querySelector(".dashboard-screen"),
                CAPTURE_MODE_DASHBOARD
            );
        },
        captureMainPanel: function () {
            return captureElement(
                visibleMainPanel(),
                CAPTURE_MODE_MAIN_PANEL
            );
        },
        captureAppView: function () {
            return captureElement(
                document.querySelector(".app-shell"),
                CAPTURE_MODE_APP
            );
        },
    };
})();

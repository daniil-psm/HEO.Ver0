(function () {
    "use strict";

    var openSections = new Map();
    var selector = "details.konfig-advanced, details.konfig-progress-details";
    var logSelector = "#konfig-progress-log-table";
    var activeLogTable = null;
    var logScrollState = {
        scrollTop: 0,
        stickToBottom: true
    };

    function sectionKey(details) {
        return details && details.id ? details.id : null;
    }

    function remember(details) {
        var key = sectionKey(details);
        if (key) {
            openSections.set(key, details.open);
        }
    }

    function restoreOpenSections() {
        if (!document.getElementById("konfig-progress-log-details")) {
            openSections.delete("konfig-progress-log-details");
        }
        document.querySelectorAll(selector).forEach(function (details) {
            var key = sectionKey(details);
            if (key && openSections.has(key) && details.open !== openSections.get(key)) {
                details.open = openSections.get(key);
            }
        });
    }

    function rememberLogScroll(logTable) {
        if (!logTable) {
            return;
        }
        logScrollState.scrollTop = logTable.scrollTop;
        logScrollState.stickToBottom = (
            logTable.scrollHeight - logTable.clientHeight - logTable.scrollTop <= 4
        );
    }

    function restoreLogScroll(force) {
        var logTable = document.querySelector(logSelector);
        if (!logTable) {
            activeLogTable = null;
            logScrollState = {scrollTop: 0, stickToBottom: true};
            return;
        }
        if (!force && logTable === activeLogTable) {
            return;
        }
        if (
            activeLogTable &&
            activeLogTable !== logTable &&
            activeLogTable.isConnected
        ) {
            rememberLogScroll(activeLogTable);
        }
        activeLogTable = logTable;
        window.requestAnimationFrame(function () {
            if (!activeLogTable || !activeLogTable.isConnected) {
                return;
            }
            if (logScrollState.stickToBottom) {
                activeLogTable.scrollTop = activeLogTable.scrollHeight;
            } else {
                activeLogTable.scrollTop = Math.min(
                    logScrollState.scrollTop,
                    Math.max(0, activeLogTable.scrollHeight - activeLogTable.clientHeight)
                );
            }
        });
    }

    // Der Klick wird vor der nativen Umschaltung verarbeitet. Dadurch kennt
    // der MutationObserver bereits die vom Nutzer beabsichtigte Stellung und
    // verwechselt ein bewusstes Zuklappen nicht mit einem veralteten Render.
    document.addEventListener("click", function (event) {
        var summary = event.target.closest && event.target.closest("summary");
        var details = summary && summary.parentElement;
        if (details && details.matches(selector)) {
            var key = sectionKey(details);
            if (key) {
                openSections.set(key, !details.open);
            }
        }
    }, true);

    // Das native toggle-Ereignis ist die unmittelbarste Quelle. So bleibt der
    // sichtbare Zustand auch dann stabil, wenn parallele Dash-Callbacks in
    // unterschiedlicher Reihenfolge einen Dialog neu aufbauen.
    document.addEventListener("toggle", function (event) {
        if (event.target.matches && event.target.matches(selector)) {
            remember(event.target);
            if (event.target.id === "konfig-progress-log-details" && event.target.open) {
                restoreLogScroll(true);
            }
        }
    }, true);

    document.addEventListener("scroll", function (event) {
        if (event.target.matches && event.target.matches(logSelector)) {
            rememberLogScroll(event.target);
        }
    }, true);

    new MutationObserver(function () {
        restoreOpenSections();
        restoreLogScroll(false);
    }).observe(document.documentElement, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["open"]
    });
    restoreOpenSections();
    restoreLogScroll(false);
}());

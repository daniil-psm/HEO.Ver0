(function () {
    "use strict";

    if (typeof document === "undefined") return;

    var observedMenu = null;
    var menuObserver = null;

    function openAnchor() {
        return document.querySelector(
            "#konfig-landing .konfig-scenario-row.is-delete-open " +
            ".konfig-scenario-delete-control"
        );
    }

    function placeMenu(anchor) {
        var menu = document.getElementById("konfig-scenario-delete-options");
        if (!menu || !anchor || !anchor.isConnected) return;
        var panel = menu.closest(".konfig-load-panel");
        if (!panel) return;

        var anchorRect = anchor.getBoundingClientRect();
        var panelRect = panel.getBoundingClientRect();
        var menuWidth = menu.offsetWidth || 260;
        var menuHeight = menu.offsetHeight || 78;
        var right = Math.max(8, panelRect.right - anchorRect.right);
        right = Math.min(right, Math.max(8, panelRect.width - menuWidth - 8));
        var top = Math.max(8, Math.min(
            anchorRect.top - panelRect.top,
            panelRect.height - menuHeight - 8
        ));

        menu.style.setProperty("--konfig-scenario-delete-top", top + "px");
        menu.style.setProperty("--konfig-scenario-delete-right", right + "px");

        if (observedMenu !== menu && typeof MutationObserver === "function") {
            if (menuObserver) menuObserver.disconnect();
            observedMenu = menu;
            menuObserver = new MutationObserver(function () {
                if (!menu.hidden) placeMenu(openAnchor());
            });
            menuObserver.observe(menu, {attributes: true, attributeFilter: ["hidden"]});
        }
    }

    document.addEventListener("click", function (event) {
        var target = event.target;
        if (!target || !target.closest) return;
        var trash = target.closest(".konfig-scenario-delete");
        if (trash) {
            placeMenu(trash.closest(".konfig-scenario-delete-control"));
            return;
        }

        var menu = document.getElementById("konfig-scenario-delete-options");
        if (!menu || menu.hidden || target.closest(
            "#konfig-delete-results, #konfig-delete-entire"
        )) return;

        var dismiss = document.getElementById("konfig-delete-dismiss");
        if (dismiss) {
            menu.hidden = true;
            dismiss.click();
        }
    }, true);

    window.addEventListener("resize", function () {
        placeMenu(openAnchor());
    });
    document.addEventListener("scroll", function () {
        placeMenu(openAnchor());
    }, true);
}());

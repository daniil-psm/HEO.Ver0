(function () {
    "use strict";

    var draggedUid = null;

    function buildingNode(target) {
        return target && target.closest
            ? target.closest(".konfig-node-building[data-building-uid]")
            : null;
    }

    function publishMove(sourceUid, targetUid) {
        var input = document.getElementById("konfig-building-drag-event");
        if (!input || !sourceUid || !targetUid || sourceUid === targetUid) {
            return;
        }
        // dcc.Input ist ein kontrolliertes React-Element. Der native Setter
        // plus bubbling input-Event sorgt dafür, dass Dash die Änderung wie
        // eine echte Nutzereingabe an den Server weitergibt.
        var descriptor = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, "value"
        );
        descriptor.set.call(input, JSON.stringify({
            source_uid: Number(sourceUid),
            before_uid: Number(targetUid),
            nonce: Date.now()
        }));
        input.dispatchEvent(new Event("input", { bubbles: true }));
    }

    document.addEventListener("dragstart", function (event) {
        var node = buildingNode(event.target);
        if (!node) {
            return;
        }
        draggedUid = node.dataset.buildingUid;
        node.classList.add("is-building-dragging");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", draggedUid);
    });

    document.addEventListener("dragover", function (event) {
        var node = buildingNode(event.target);
        if (!draggedUid || !node || node.dataset.buildingUid === draggedUid) {
            return;
        }
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        node.classList.add("is-building-drop-target");
    });

    document.addEventListener("dragleave", function (event) {
        var node = buildingNode(event.target);
        if (node) {
            node.classList.remove("is-building-drop-target");
        }
    });

    document.addEventListener("drop", function (event) {
        var node = buildingNode(event.target);
        if (!draggedUid || !node) {
            return;
        }
        event.preventDefault();
        node.classList.remove("is-building-drop-target");
        publishMove(draggedUid, node.dataset.buildingUid);
    });

    document.addEventListener("dragend", function () {
        document.querySelectorAll(".is-building-dragging, .is-building-drop-target")
            .forEach(function (node) {
                node.classList.remove("is-building-dragging", "is-building-drop-target");
            });
        draggedUid = null;
    });
}());

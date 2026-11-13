/* Alle offenen HEO-Tabs erneuern dieselbe Serverfrist; kein unzuverlässiges unload-Signal. */
(function () {
    "use strict";
    var pending = false;
    async function heartbeat() {
        if (pending) return;
        pending = true;
        try {
            var status = await fetch("/_heo/status", {cache: "no-store", signal: AbortSignal.timeout(5000)});
            if (!status.ok) return;
            var instance = await status.json();
            await fetch("/_heo/heartbeat", {
                method: "POST",
                headers: {"X-HEO-Instance": instance.instance},
                signal: AbortSignal.timeout(5000)
            });
        } catch (_) {
            // Nach Schlafzustand oder Serverneustart beim nächsten Intervall erneut versuchen.
        } finally {
            pending = false;
        }
    }
    heartbeat();
    window.setInterval(heartbeat, 5000);
    window.addEventListener("pageshow", heartbeat);
    document.addEventListener("visibilitychange", function () {
        if (!document.hidden) heartbeat();
    });
}());

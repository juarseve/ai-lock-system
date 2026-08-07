/**
 * Dynamic Header Badge Controller
 * Periodically polls /api/serial-status/ to display real-time ESP32 hardware serial connection status.
 */
document.addEventListener('DOMContentLoaded', () => {
    const badge = document.getElementById('esp32-status-badge');
    const badgeText = document.getElementById('esp32-status-text');

    async function updateSerialStatus() {
        if (!badge || !badgeText) return;
        try {
            const response = await fetch('/api/serial-status/');
            const data = await response.json();

            if (data.connected) {
                badge.className = 'system-status-badge connected';
                badgeText.textContent = `ESP32 CONECTADO`;
                badge.title = data.message;
            } else {
                badge.className = 'system-status-badge disconnected';
                badgeText.textContent = `ESP32 DESCONECTADO`;
                badge.title = data.message;
                console.warn('[HeaderStatus] Serial check detail:', data.message);
            }
        } catch (err) {
            console.warn('[HeaderStatus] Error polling serial status:', err);
            if (badge && badgeText) {
                badge.className = 'system-status-badge disconnected';
                badgeText.textContent = 'ESP32 DESCONECTADO';
            }
        }
    }

    updateSerialStatus();
    // Poll every 2 seconds
    setInterval(updateSerialStatus, 2000);
});

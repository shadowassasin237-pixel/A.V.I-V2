/**
 * A.V.I. - Python <-> JavaScript API Bridge
 * Handles communication between the web frontend and the Python backend via pywebview.
 */

window.API = {
    ready: false,
    pollingInterval: null,
    listeners: {},

    async init() {
        return new Promise((resolve) => {
            let attempts = 0;
            const check = setInterval(() => {
                if (window.pywebview && window.pywebview.api) {
                    clearInterval(check);
                    this.ready = true;
                    this.emit('ready', true);
                    resolve(true);
                } else if (attempts > 80) { // 8 seconds timeout
                    clearInterval(check);
                    console.warn('API: pywebview not detected. Running in preview/demo mode.');
                    resolve(false);
                }
                attempts++;
            }, 100);
        });
    },

    on(event, callback) {
        if (!this.listeners[event]) this.listeners[event] = [];
        this.listeners[event].push(callback);
    },

    emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(cb => {
                try { cb(data); } catch (e) { console.error(e); }
            });
        }
    },

    async sendMessage(text) {
        if (!this.ready) {
            return `A.V.I. Core offline. Command received: "${text}"`;
        }
        try {
            return await window.pywebview.api.send_message(text);
        } catch (e) {
            console.error('API Error (sendMessage):', e);
            return 'Communication failure with A.V.I. neural core.';
        }
    },

    async startMic() {
        if (!this.ready) return null;
        try {
            const res = await window.pywebview.api.start_mic();
            return typeof res === 'string' ? JSON.parse(res) : res;
        } catch (e) {
            console.error('API Error (startMic):', e);
            return null;
        }
    },

    async stopMic() {
        if (!this.ready) return null;
        try {
            const res = await window.pywebview.api.stop_mic();
            return typeof res === 'string' ? JSON.parse(res) : res;
        } catch (e) {
            console.error('API Error (stopMic):', e);
            return null;
        }
    },

    async getSystemStats() {
        if (!this.ready) return null;
        try {
            const res = await window.pywebview.api.get_system_stats();
            return typeof res === 'string' ? JSON.parse(res) : res;
        } catch (e) {
            console.error('API Error (getSystemStats):', e);
            return null;
        }
    },

    async saveSettings(data) {
        if (!this.ready) {
            return { success: true, preview: true };
        }
        try {
            const res = await window.pywebview.api.save_settings(JSON.stringify(data));
            return typeof res === 'string' ? JSON.parse(res) : res;
        } catch (e) {
            console.error('API Error (saveSettings):', e);
            return { success: false, error: String(e) };
        }
    },

    async loadSettings() {
        if (!this.ready) return null;
        try {
            const res = await window.pywebview.api.load_settings();
            return typeof res === 'string' ? JSON.parse(res) : res;
        } catch (e) {
            console.error('API Error (loadSettings):', e);
            return null;
        }
    },

    async onModeChange(mode) {
        if (!this.ready) return null;
        try {
            return await window.pywebview.api.on_mode_change(mode);
        } catch (e) {
            console.error('API Error (onModeChange):', e);
            return null;
        }
    },

    async getChatHistory() {
        if (!this.ready) return [];
        try {
            const res = await window.pywebview.api.get_chat_history();
            return typeof res === 'string' ? JSON.parse(res) : res;
        } catch (e) {
            console.error('API Error (getChatHistory):', e);
            return [];
        }
    },

    startTelemetryPolling(intervalMs = 2000) {
        if (this.pollingInterval) clearInterval(this.pollingInterval);

        const poll = async () => {
            if (document.visibilityState === 'visible' && this.ready) {
                const stats = await this.getSystemStats();
                if (stats && window.updateTelemetry) {
                    window.updateTelemetry(stats);
                }
            }
        };

        // Initial poll after short delay
        setTimeout(poll, 600);
        this.pollingInterval = setInterval(poll, intervalMs);

        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                poll();
            }
        });
    }
};

// Initialize bridge
window.API.init();

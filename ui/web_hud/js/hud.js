/**
 * A.V.I. - Holographic HUD Controller
 * Handles UI interactions, animated mode switching (including Focus Mode),
 * Web Audio API synthesized sound FX, microphone input, telemetry, and settings.
 */

// ============================================================
// SOUND FX SYSTEM (Web Audio API - No external mp3 files required)
// ============================================================

const SoundFX = {
    audioCtx: null,

    init() {
        if (!this.audioCtx) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (AudioContextClass) {
                this.audioCtx = new AudioContextClass();
            }
        }
        if (this.audioCtx && this.audioCtx.state === 'suspended') {
            this.audioCtx.resume();
        }
    },

    playTone(frequency, type, duration, sweepTo = null, reverb = false, volume = 0.3) {
        try {
            this.init();
            if (!this.audioCtx) return;
            const t = this.audioCtx.currentTime;
            const osc = this.audioCtx.createOscillator();
            const gain = this.audioCtx.createGain();

            osc.type = type;
            osc.frequency.setValueAtTime(frequency, t);
            if (sweepTo) {
                osc.frequency.exponentialRampToValueAtTime(sweepTo, t + duration);
            }

            gain.gain.setValueAtTime(volume, t);
            gain.gain.exponentialRampToValueAtTime(0.001, t + (reverb ? duration * 1.4 : duration));

            osc.connect(gain);
            gain.connect(this.audioCtx.destination);

            osc.start(t);
            osc.stop(t + (reverb ? duration * 1.5 : duration));
        } catch (e) {
            // Audio context failure guard
        }
    },

    click() { this.playTone(1800, 'sine', 0.04, null, false, 0.25); },
    modeChange() { this.playTone(850, 'sine', 0.25, 220, true, 0.35); },
    transmit() { this.playTone(400, 'sine', 0.2, 1400, false, 0.3); },
    alert() {
        try {
            this.init();
            if (!this.audioCtx) return;
            const t = this.audioCtx.currentTime;
            for (let i = 0; i < 2; i++) {
                const osc = this.audioCtx.createOscillator();
                const gain = this.audioCtx.createGain();
                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(900, t + i * 0.25);
                osc.frequency.setValueAtTime(1400, t + i * 0.25 + 0.1);
                gain.gain.setValueAtTime(0.3, t + i * 0.25);
                gain.gain.exponentialRampToValueAtTime(0.001, t + i * 0.25 + 0.22);
                osc.connect(gain);
                gain.connect(this.audioCtx.destination);
                osc.start(t + i * 0.25);
                osc.stop(t + i * 0.25 + 0.23);
            }
        } catch (e) {}
    },
    boot() {
        try {
            this.init();
            if (!this.audioCtx) return;
            const t = this.audioCtx.currentTime;

            // Low frequency rumble
            const rumble = this.audioCtx.createOscillator();
            const rumbleGain = this.audioCtx.createGain();
            rumble.type = 'sawtooth';
            rumble.frequency.setValueAtTime(65, t);
            rumbleGain.gain.setValueAtTime(0.001, t);
            rumbleGain.gain.linearRampToValueAtTime(0.25, t + 0.8);
            rumbleGain.gain.linearRampToValueAtTime(0.001, t + 2.2);
            rumble.connect(rumbleGain);
            rumbleGain.connect(this.audioCtx.destination);
            rumble.start(t);
            rumble.stop(t + 2.2);

            // Upward sweep
            const sweep = this.audioCtx.createOscillator();
            const sweepGain = this.audioCtx.createGain();
            sweep.type = 'sine';
            sweep.frequency.setValueAtTime(180, t + 0.3);
            sweep.frequency.exponentialRampToValueAtTime(1800, t + 1.8);
            sweepGain.gain.setValueAtTime(0.001, t + 0.3);
            sweepGain.gain.linearRampToValueAtTime(0.35, t + 1.2);
            sweepGain.gain.linearRampToValueAtTime(0.001, t + 2.0);
            sweep.connect(sweepGain);
            sweepGain.connect(this.audioCtx.destination);
            sweep.start(t + 0.3);
            sweep.stop(t + 2.0);

            // Resonant high ping
            setTimeout(() => this.playTone(1600, 'sine', 0.8, null, true, 0.4), 1600);
        } catch (e) {}
    },
    micOn() {
        this.playTone(750, 'sine', 0.08, null, false, 0.3);
        setTimeout(() => this.playTone(1050, 'sine', 0.08, null, false, 0.3), 80);
        setTimeout(() => this.playTone(1350, 'sine', 0.08, null, false, 0.3), 160);
    },
    micOff() {
        this.playTone(1350, 'sine', 0.08, null, false, 0.3);
        setTimeout(() => this.playTone(1050, 'sine', 0.08, null, false, 0.3), 80);
        setTimeout(() => this.playTone(750, 'sine', 0.08, null, false, 0.3), 160);
    },
    save() {
        this.playTone(600, 'sine', 0.09, null, false, 0.35);
        setTimeout(() => this.playTone(950, 'sine', 0.12, null, false, 0.35), 100);
    },
    error() {
        this.playTone(220, 'sawtooth', 0.3, null, false, 0.4);
    }
};

// ============================================================
// MAIN HUD CONTROLLER
// ============================================================

window.HUD = {
    currentMode: 'tactical',
    isListening: false,
    orbState: 'idle',
    spectrumInterval: null,

    init() {
        this.bindEvents();
        this.startClock();
        this.initSpectrumBars();
        this.runBootSequence();
    },

    bindEvents() {
        // Global Keyboard Shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeSettings();
                if (this.currentMode === 'focus') {
                    this.switchMode('tactical');
                }
            }
            if (e.key === 'F1') {
                e.preventDefault();
                this.toggleMic();
            }
            if (e.key === 'F2') {
                e.preventDefault();
                const modes = ['tactical', 'sentinel', 'focus', 'diagnostic', 'god'];
                const nextIndex = (modes.indexOf(this.currentMode) + 1) % modes.length;
                this.switchMode(modes[nextIndex]);
            }
        });

        // Command Input (Enter key)
        const commandInput = document.getElementById('command-input');
        if (commandInput) {
            commandInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.submitCommand();
                }
            });
        }

        // Transmit Button
        const transmitBtn = document.getElementById('transmit-btn');
        if (transmitBtn) {
            transmitBtn.addEventListener('click', () => this.submitCommand());
        }

        // Mic Button
        const micBtn = document.getElementById('mic-btn');
        if (micBtn) {
            micBtn.addEventListener('click', () => this.toggleMic());
        }

        // Clear Chat Button
        const clearBtn = document.getElementById('clear-chat-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearChat());
        }

        // Mode Switcher Buttons
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const targetMode = btn.dataset.mode;
                if (targetMode) this.switchMode(targetMode);
            });
        });

        // Settings Open / Close / Overlay
        const settingsBtn = document.getElementById('settings-btn');
        if (settingsBtn) {
            settingsBtn.addEventListener('click', () => this.openSettings());
        }

        const settingsClose = document.getElementById('settings-close');
        if (settingsClose) {
            settingsClose.addEventListener('click', () => this.closeSettings());
        }

        const modalOverlay = document.getElementById('modal-overlay');
        if (modalOverlay) {
            modalOverlay.addEventListener('click', () => this.closeSettings());
        }

        // Password Reveal Buttons
        this.bindToggleVis('toggle-api-key', 'settings-api-key');
        this.bindToggleVis('toggle-lk-key', 'settings-lk-key');
        this.bindToggleVis('toggle-lk-secret', 'settings-lk-secret');

        // Settings API Key Input Monitor
        const apiKeyInput = document.getElementById('settings-api-key');
        if (apiKeyInput) {
            apiKeyInput.addEventListener('input', () => this.updateApiKeyStatus(apiKeyInput.value));
        }

        // Settings Save Buttons
        const saveBtn = document.getElementById('save-settings-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveSettings(false));
        }

        const saveRestartBtn = document.getElementById('save-restart-btn');
        if (saveRestartBtn) {
            saveRestartBtn.addEventListener('click', () => this.saveSettings(true));
        }

        // SoundFX trigger on any UI button click
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('button');
            if (btn && !btn.id.includes('mic')) {
                SoundFX.click();
            }
        });
    },

    bindToggleVis(btnId, inputId) {
        const btn = document.getElementById(btnId);
        const input = document.getElementById(inputId);
        if (btn && input) {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                if (input.type === 'password') {
                    input.type = 'text';
                    btn.textContent = 'HIDE';
                    btn.style.color = '#ff1133';
                } else {
                    input.type = 'password';
                    btn.textContent = 'SHOW';
                    btn.style.color = '#ffe0e8';
                }
            });
        }
    },

    updateApiKeyStatus(key) {
        const statusEl = document.getElementById('api-key-status');
        if (!statusEl) return;
        const trimmed = (key || '').trim();
        if (!trimmed) {
            statusEl.textContent = '▸ NO KEY SET — Enter your OpenRouter API key above';
            statusEl.style.color = '#6b1a2a';
        } else if (trimmed.length < 15) {
            statusEl.textContent = '▸ KEY TOO SHORT';
            statusEl.style.color = '#ffaa00';
        } else {
            const masked = trimmed.slice(0, 6) + '●●●●●●●●' + trimmed.slice(-4);
            statusEl.textContent = `▸ KEY CONFIGURED: ${masked}`;
            statusEl.style.color = '#00ff66';
        }
    },

    // ========================================================
    // MODE SWITCHING & ANIMATED FOCUS MODE
    // ========================================================

    switchMode(mode) {
        if (!mode) return;
        SoundFX.modeChange();

        document.body.classList.remove('mode-tactical', 'mode-sentinel', 'mode-focus', 'mode-diagnostic', 'mode-god');
        document.body.classList.remove('focus-mode', 'god-mode');

        this.currentMode = mode;
        document.body.classList.add(`mode-${mode}`);

        const statusText = document.getElementById('status-text');
        const threatLevel = document.getElementById('threat-level');
        const telemMode = document.getElementById('telem-mode');

        if (telemMode) telemMode.textContent = mode.toUpperCase();

        if (mode === 'focus') {
            document.body.classList.add('focus-mode');
            if (statusText) statusText.textContent = 'FOCUS PROTOCOL ENGAGED';
            if (threatLevel) threatLevel.textContent = '◆ TELEMETRY COLLAPSED // IMMERSIVE LINK';
            this.notify('FOCUS MODE ACTIVATED — TELEMETRY COLLAPSED', 'info');
        } else if (mode === 'god') {
            document.body.classList.add('god-mode');
            if (statusText) statusText.textContent = 'OVERCLOCK: GOD MODE';
            if (threatLevel) threatLevel.textContent = '⚡ MAXIMUM COGNITIVE SURGE';
            if (window.ReactorCore) window.ReactorCore.setState('speaking');
            this.notify('GOD MODE: PROTOCOLS UNBOUND', 'danger');
            setTimeout(() => {
                if (this.currentMode === 'god' && window.ReactorCore) {
                    window.ReactorCore.setState('idle');
                }
            }, 3000);
        } else if (mode === 'sentinel') {
            if (statusText) statusText.textContent = 'SENTINEL ACTIVE';
            if (threatLevel) threatLevel.textContent = '◆ AUTONOMOUS PERIMETER GUARD';
            this.notify('SENTINEL MODE ACTIVE', 'info');
        } else if (mode === 'diagnostic') {
            if (statusText) statusText.textContent = 'DIAGNOSTIC TELEMETRY';
            if (threatLevel) threatLevel.textContent = '◆ HARDWARE INTROSPECTION';
            this.notify('DIAGNOSTIC SUITE RUNNING', 'info');
        } else {
            if (statusText) statusText.textContent = 'SYSTEM ONLINE';
            if (threatLevel) threatLevel.textContent = '◆ THREAT LEVEL: NOMINAL';
        }

        // Highlight active mode button
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });

        // Resize 3D reactor after layout transitions
        setTimeout(() => {
            if (window.ReactorCore) window.ReactorCore.resize();
        }, 550);

        if (window.API) window.API.onModeChange(mode);
    },

    // ========================================================
    // CHAT & COMMAND TRANSMIT
    // ========================================================

    addMessage(sender, text, type = 'system') {
        const log = document.getElementById('chat-log');
        if (!log) return;

        const container = document.createElement('div');
        container.className = `msg-container msg-${type}`;

        const time = new Date().toLocaleTimeString([], { hour12: false });
        container.innerHTML = `
            <div class="msg-meta">
                <span class="msg-timestamp">[${time}]</span>
                <span class="msg-sender">${sender}</span>
            </div>
            <div class="msg-content">${text}</div>
        `;

        log.appendChild(container);
        log.scrollTop = log.scrollHeight;
    },

    clearChat() {
        const log = document.getElementById('chat-log');
        if (log) {
            log.innerHTML = `
                <div class="msg-container msg-system">
                    <div class="msg-meta">
                        <span class="msg-timestamp">[SYSTEM]</span>
                        <span class="msg-sender">CONSOLE</span>
                    </div>
                    <div class="msg-content">Neural memory display cleared. Protocols intact.</div>
                </div>
            `;
            this.notify('CHAT CONSOLE CLEARED', 'info');
        }
    },

    async submitCommand() {
        const input = document.getElementById('command-input');
        if (!input || !input.value.trim()) return;

        const text = input.value.trim();
        input.value = '';

        this.addMessage('YOU', text, 'user');
        this._updateOrbState('thinking');
        SoundFX.transmit();

        if (window.API) {
            const response = await window.API.sendMessage(text);
            this.addMessage('A.V.I.', response || 'Protocol acknowledgment.', 'avi');
            this._updateOrbState('speaking');
        }
    },

    _updateOrbState(state) {
        this.orbState = state;
        const ind = document.getElementById('ind-state');
        const telemVoice = document.getElementById('telem-voice');
        if (ind) ind.textContent = `STATE: ${state.toUpperCase()}`;
        if (telemVoice) telemVoice.textContent = state.toUpperCase();

        if (window.ReactorCore) {
            window.ReactorCore.setState(state);
            if (state === 'speaking') {
                window.ReactorCore.setVoiceLevel(0.7);
            } else if (state === 'listening') {
                window.ReactorCore.setVoiceLevel(0.85);
            } else {
                window.ReactorCore.setVoiceLevel(0.08);
            }
        }
    },

    // ========================================================
    // MICROPHONE & VOICE COMMANDS
    // ========================================================

    toggleMic() {
        this.isListening = !this.isListening;
        const micBtn = document.getElementById('mic-btn');

        if (this.isListening) {
            SoundFX.micOn();
            if (micBtn) {
                micBtn.classList.add('active');
                micBtn.innerHTML = '◉ LISTENING...';
            }
            this._updateOrbState('listening');
            this.notify('MICROPHONE ENGAGED — LISTENING...', 'info');

            if (window.API) window.API.startMic();
        } else {
            this.stopMicUI();
            if (window.API) window.API.stopMic();
        }
    },

    stopMicUI() {
        this.isListening = false;
        SoundFX.micOff();
        const micBtn = document.getElementById('mic-btn');
        if (micBtn) {
            micBtn.classList.remove('active');
            micBtn.innerHTML = '◉ MIC';
        }
        this._updateOrbState('idle');
    },

    handleVoiceCommand(rawText) {
        if (!rawText) return false;
        const text = rawText.toLowerCase().trim();

        if (text.includes('focus mode')) {
            this.switchMode('focus');
            return true;
        }
        if (text.includes('tactical mode')) {
            this.switchMode('tactical');
            return true;
        }
        if (text.includes('sentinel mode')) {
            this.switchMode('sentinel');
            return true;
        }
        if (text.includes('diagnostic mode') || text.includes('diagnostics')) {
            this.switchMode('diagnostic');
            return true;
        }
        if (text.includes('god mode') || text.includes('overclock')) {
            this.switchMode('god');
            return true;
        }
        if (text.includes('open settings') || text.includes('open config')) {
            this.openSettings();
            return true;
        }
        if (text.includes('close settings') || text.includes('close config')) {
            this.closeSettings();
            return true;
        }
        if (text.includes('clear chat') || text.includes('clear screen')) {
            this.clearChat();
            return true;
        }
        return false;
    },

    // ========================================================
    // SETTINGS MODAL
    // ========================================================

    async openSettings() {
        SoundFX.click();
        const panel = document.getElementById('settings-panel');
        const overlay = document.getElementById('modal-overlay');
        if (panel) panel.classList.add('open');
        if (overlay) overlay.style.display = 'block';

        if (window.API) {
            const data = await window.API.loadSettings();
            if (data && window.loadSettingsData) {
                window.loadSettingsData(data);
            }
        }
    },

    closeSettings() {
        SoundFX.click();
        const panel = document.getElementById('settings-panel');
        const overlay = document.getElementById('modal-overlay');
        if (panel) panel.classList.remove('open');
        if (overlay) overlay.style.display = 'none';
    },

    async saveSettings(restartVoice = false) {
        SoundFX.save();
        const apiKey = document.getElementById('settings-api-key')?.value || '';
        const model = document.getElementById('settings-model')?.value || '';
        const voice = document.getElementById('settings-voice')?.value || '';
        const lkUrl = document.getElementById('settings-lk-url')?.value || '';
        const lkKey = document.getElementById('settings-lk-key')?.value || '';
        const lkSecret = document.getElementById('settings-lk-secret')?.value || '';

        const payload = {
            openrouter_api_key: apiKey,
            llm_model: model,
            avi_voice: voice,
            livekit_url: lkUrl,
            livekit_api_key: lkKey,
            livekit_api_secret: lkSecret,
            restart_voice: restartVoice,
        };

        if (window.API) {
            const res = await window.API.saveSettings(payload);
            const telemPersona = document.getElementById('telem-persona');
            if (telemPersona && voice) telemPersona.textContent = voice;

            if (res && res.success) {
                this.notify('SETTINGS SAVED // CONFIG PERSISTED', 'success');
                if (res.restart_msg) {
                    this.notify(res.restart_msg, 'info');
                }
                this.closeSettings();
            } else {
                this.notify('SETTINGS PERSISTENCE FAILED', 'danger');
            }
        }
    },

    // ========================================================
    // TELEMETRY & AUDIO SPECTRUM
    // ========================================================

    initSpectrumBars() {
        const spectrum = document.getElementById('audio-spectrum');
        if (!spectrum) return;

        // Animate spectrum bars randomly
        setInterval(() => {
            const bars = spectrum.querySelectorAll('.spectrum-bar');
            bars.forEach((bar, idx) => {
                let h = 4;
                if (this.orbState === 'listening') {
                    h = Math.floor(Math.random() * 32) + 8;
                } else if (this.orbState === 'speaking') {
                    h = Math.floor(Math.sin(Date.now() * 0.01 + idx) * 16 + 18);
                } else {
                    h = Math.floor(Math.sin(Date.now() * 0.003 + idx) * 3 + 6);
                }
                bar.style.height = `${h}px`;
            });
        }, 80);
    },

    startClock() {
        const update = () => {
            const now = new Date();
            const timeEl = document.getElementById('clock-time');
            const dateEl = document.getElementById('clock-date');
            if (timeEl) timeEl.textContent = now.toLocaleTimeString([], { hour12: false });
            if (dateEl) {
                const options = { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' };
                dateEl.textContent = now.toLocaleDateString(undefined, options).toUpperCase();
            }
        };
        update();
        setInterval(update, 1000);
    },

    runBootSequence() {
        const overlay = document.getElementById('boot-overlay');
        if (!overlay) return;

        SoundFX.boot();

        const messages = [
            '▸ INITIALIZING A.V.I. HOLOGRAPHIC CORE...',
            '▸ LOADING QUANTUM SENTINEL PROTOCOLS...',
            '▸ ENGAGING NEURAL SYNAPSE MATRIX...',
            '▸ CALIBRATING 3D THREE.JS REACTOR ENGINE...',
            '▸ MOUNTING REAL HARDWARE WIDGETS...',
            '▸ THREAT ASSESSMENT: NOMINAL',
            '▸ A.V.I. SYSTEMS 100% OPERATIONAL'
        ];

        const log = document.getElementById('boot-log');
        const progressBar = document.getElementById('boot-progress-bar');
        const statusEl = document.getElementById('boot-status');
        let index = 0;

        const nextStep = () => {
            if (index < messages.length) {
                if (log) {
                    const p = document.createElement('div');
                    p.textContent = messages[index];
                    p.style.fontSize = '12px';
                    p.style.color = '#ffe0e8';
                    p.style.fontFamily = "'Share Tech Mono', monospace";
                    p.style.marginBottom = '4px';
                    log.appendChild(p);
                    log.scrollTop = log.scrollHeight;
                }

                const pct = Math.floor(((index + 1) / messages.length) * 100);
                if (progressBar) progressBar.style.width = `${pct}%`;
                if (statusEl) statusEl.textContent = `LOADING PROTOCOLS [${pct}%]`;

                index++;
                setTimeout(nextStep, 260);
            } else {
                setTimeout(() => {
                    overlay.style.transition = 'opacity 0.6s ease';
                    overlay.style.opacity = '0';
                    setTimeout(() => {
                        overlay.style.display = 'none';
                        if (window.ReactorCore) {
                            window.ReactorCore.init('reactor-container');
                        }
                        if (window.API) {
                            window.API.startTelemetryPolling(2000);
                        }
                    }, 600);
                }, 400);
            }
        };

        setTimeout(nextStep, 400);
    },

    notify(message, type = 'info') {
        const container = document.getElementById('notification-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.style.background = '#0c0306';
        toast.style.border = type === 'danger' ? '1px solid #ff4500' : '1px solid #ff1133';
        toast.style.color = '#ffe0e8';
        toast.style.padding = '8px 16px';
        toast.style.fontSize = '12px';
        toast.style.fontFamily = "'Share Tech Mono', monospace";
        toast.style.letterSpacing = '1px';
        toast.style.boxShadow = '0 0 12px rgba(255, 17, 51, 0.4)';
        toast.style.borderRadius = '2px';
        toast.style.marginBottom = '8px';
        toast.style.transition = 'all 0.3s ease';
        toast.textContent = `◈ ${message}`;

        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(-10px)';
            setTimeout(() => toast.remove(), 350);
        }, 3200);
    }
};

// ============================================================
// GLOBAL CALLBACKS ACCESSED BY PYTHON
// ============================================================

window.voiceResult = function(text) {
    if (!text || !text.trim()) {
        window.HUD.stopMicUI();
        return;
    }
    const cleanText = text.trim();

    // Check if voice command triggers a mode switch or UI action
    const handled = window.HUD.handleVoiceCommand(cleanText);
    if (handled) {
        window.HUD.stopMicUI();
        return;
    }

    // Otherwise transmit recognized voice text to brain
    const input = document.getElementById('command-input');
    if (input) input.value = cleanText;
    window.HUD.submitCommand();
    window.HUD.stopMicUI();
};

window.updateLatency = function(ms) {
    const el = document.getElementById('telem-latency');
    if (el) el.textContent = `${ms} MS`;
};

window.updateTelemetry = function(data) {
    if (!data) return;

    // CPU
    if (data.cpu !== undefined) {
        const el = document.getElementById('telem-cpu');
        const gauge = document.getElementById('gauge-cpu');
        if (el) el.textContent = `${data.cpu}%`;
        if (gauge) gauge.style.width = `${Math.min(100, data.cpu)}%`;
    }

    // RAM
    if (data.ram !== undefined) {
        const el = document.getElementById('telem-ram');
        const gauge = document.getElementById('gauge-ram');
        if (el) el.textContent = `${data.ram}% (${data.ram_used || ''}GB)`;
        if (gauge) gauge.style.width = `${Math.min(100, data.ram)}%`;
    }

    // GPU
    if (data.gpu !== undefined) {
        const el = document.getElementById('telem-gpu');
        const gauge = document.getElementById('gauge-gpu');
        if (el) el.textContent = String(data.gpu);
        if (gauge) gauge.style.width = `${Math.min(100, data.gpu_percent || 0)}%`;
    }

    // Jitter simulated core fusion power slightly
    const powerEl = document.getElementById('telem-power');
    const powerGauge = document.getElementById('gauge-power');
    if (powerEl) {
        const currentPower = parseFloat(powerEl.textContent) || 98.2;
        const newPower = Math.max(95.0, Math.min(99.9, currentPower + (Math.random() - 0.5) * 0.15));
        powerEl.textContent = `${newPower.toFixed(1)}%`;
        if (powerGauge) powerGauge.style.width = `${newPower}%`;
    }

    // Radar blips
    const radarBlips = document.getElementById('radar-blips');
    if (radarBlips) {
        radarBlips.innerHTML = '';
        const count = Math.floor(Math.random() * 4) + 1;
        for (let i = 0; i < count; i++) {
            const blip = document.createElement('div');
            blip.style.position = 'absolute';
            blip.style.width = '4px';
            blip.style.height = '4px';
            blip.style.borderRadius = '50%';
            blip.style.background = '#ff1133';
            blip.style.boxShadow = '0 0 6px #ff1133';
            blip.style.left = `${Math.random() * 80 + 10}%`;
            blip.style.top = `${Math.random() * 80 + 10}%`;
            radarBlips.appendChild(blip);
        }
    }
};

window.loadSettingsData = function(data) {
    if (!data) return;

    if (data.openrouter_api_key !== undefined) {
        const el = document.getElementById('settings-api-key');
        if (el) el.value = data.openrouter_api_key;
        window.HUD.updateApiKeyStatus(data.openrouter_api_key);
    }

    if (data.llm_model !== undefined) {
        const el = document.getElementById('settings-model');
        if (el) el.value = data.llm_model;
    }

    if (data.avi_voice !== undefined) {
        const el = document.getElementById('settings-voice');
        if (el) el.value = data.avi_voice;
        const personaEl = document.getElementById('telem-persona');
        if (personaEl) personaEl.textContent = data.avi_voice;
    }

    if (data.livekit_url !== undefined) {
        const el = document.getElementById('settings-lk-url');
        if (el) el.value = data.livekit_url;
    }

    if (data.livekit_api_key !== undefined) {
        const el = document.getElementById('settings-lk-key');
        if (el) el.value = data.livekit_api_key;
    }

    if (data.livekit_api_secret !== undefined) {
        const el = document.getElementById('settings-lk-secret');
        if (el) el.value = data.livekit_api_secret;
    }

    if (data.config_path !== undefined) {
        const el = document.getElementById('config-path-display');
        if (el) el.textContent = `▸ Config File: ${data.config_path}`;
    }
};

// Auto-run when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.HUD.init();
});

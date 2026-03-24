/**
 * SignaturePad - Dual-mode signature capture (Draw + Type)
 * Produces base64 PNG in both modes for consistent API submission.
 * Mobile-optimized with touch support.
 */

const SIGNATURE_FONTS = [
    { name: 'Caveat', weight: '700', url: 'https://fonts.googleapis.com/css2?family=Caveat:wght@700&display=swap' },
    { name: 'Dancing Script', weight: '700', url: 'https://fonts.googleapis.com/css2?family=Dancing+Script:wght@700&display=swap' },
    { name: 'Pacifico', weight: '400', url: 'https://fonts.googleapis.com/css2?family=Pacifico&display=swap' },
];

class SignaturePadComponent {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container #${containerId} not found`);
            return;
        }

        this.signerName = options.signerName || '';
        this.onSignatureChange = options.onSignatureChange || (() => {});

        // State
        this.mode = 'draw'; // 'draw' | 'type'
        this.signaturePad = null;
        this.canvas = null;
        this.isEmpty = true;
        this.isDrawing = false;
        this.typedText = this.signerName;
        this.selectedFont = SIGNATURE_FONTS[0].name;
        this.fontsLoaded = false;
        this.isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
            navigator.userAgent
        );

        this.init();
    }

    async init() {
        await this.loadFonts();
        this.render();
        await this.initSignaturePad();
        this.bindEvents();
    }

    async loadFonts() {
        const promises = SIGNATURE_FONTS.map((font) => {
            return new Promise((resolve) => {
                if (document.querySelector(`link[href="${font.url}"]`)) {
                    resolve();
                    return;
                }
                const link = document.createElement('link');
                link.rel = 'stylesheet';
                link.href = font.url;
                link.onload = resolve;
                link.onerror = resolve; // don't block on font failure
                document.head.appendChild(link);
            });
        });
        await Promise.all(promises);
        // Give fonts time to render
        await document.fonts?.ready?.catch(() => {});
        this.fontsLoaded = true;
    }

    render() {
        this.container.innerHTML = `
            <div class="bg-white rounded-lg p-5 md:p-6 shadow-sm border">
                <div class="mb-4">
                    <h3 class="text-lg font-semibold text-slate-800 mb-1">Unterschrift</h3>
                    <p class="text-sm text-slate-500 mode-hint"></p>
                </div>

                <!-- Mode Tabs -->
                <div class="flex bg-slate-100 rounded-lg p-1 mb-4 gap-1">
                    <button type="button" data-mode="draw"
                        class="mode-tab flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-md text-sm font-medium transition-all">
                        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125" />
                        </svg>
                        Zeichnen
                    </button>
                    <button type="button" data-mode="type"
                        class="mode-tab flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-md text-sm font-medium transition-all">
                        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 0 1 .865-.501 48.172 48.172 0 0 0 3.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z" />
                        </svg>
                        Eintippen
                    </button>
                </div>

                <!-- Draw Mode -->
                <div class="draw-mode-panel">
                    <div class="signature-canvas-wrapper relative bg-white rounded-lg border-2 border-slate-200 overflow-hidden"
                         style="height: 12rem;">
                        <canvas class="signature-canvas w-full h-full touch-action-none"></canvas>
                        <div class="signature-placeholder absolute inset-0 flex items-center justify-center text-slate-300 text-base pointer-events-none px-4 text-center">
                            Hier unterschreiben
                        </div>
                    </div>
                    <div class="mt-2 flex justify-between items-center">
                        <button type="button" class="clear-btn text-xs text-slate-400 hover:text-slate-600 transition-colors">
                            Löschen
                        </button>
                        <p class="draw-status text-xs text-slate-400"></p>
                    </div>
                </div>

                <!-- Type Mode -->
                <div class="type-mode-panel" style="display: none;">
                    <div class="mb-3">
                        <input type="text"
                            class="typed-name-input w-full px-4 py-3 border-2 border-slate-200 rounded-lg text-lg
                                   focus:border-amber-400 focus:ring-2 focus:ring-amber-100 focus:outline-none transition-colors"
                            placeholder="Vor- und Nachname"
                            autocomplete="off" spellcheck="false">
                    </div>

                    <!-- Font Selector -->
                    <div class="font-selector flex gap-2 mb-3 overflow-x-auto pb-1">
                        ${SIGNATURE_FONTS.map(
                            (f) => `
                            <button type="button" data-font="${f.name}"
                                class="font-option flex-shrink-0 px-4 py-2 rounded-lg border-2 transition-all text-lg"
                                style="font-family: '${f.name}', cursive; font-weight: ${f.weight};">
                                ${this.signerName || 'Max Mustermann'}
                            </button>
                        `
                        ).join('')}
                    </div>

                    <!-- Type Preview Canvas (hidden, used for PNG generation) -->
                    <div class="type-preview-wrapper relative bg-white rounded-lg border-2 border-slate-200 overflow-hidden"
                         style="height: 8rem;">
                        <canvas class="type-preview-canvas w-full h-full"></canvas>
                    </div>
                </div>
            </div>
        `;

        // Cache DOM elements
        this.canvas = this.container.querySelector('.signature-canvas');
        this.placeholder = this.container.querySelector('.signature-placeholder');
        this.drawStatusEl = this.container.querySelector('.draw-status');
        this.clearBtn = this.container.querySelector('.clear-btn');
        this.modeHint = this.container.querySelector('.mode-hint');

        this.drawPanel = this.container.querySelector('.draw-mode-panel');
        this.typePanel = this.container.querySelector('.type-mode-panel');
        this.typedNameInput = this.container.querySelector('.typed-name-input');
        this.typePreviewCanvas = this.container.querySelector('.type-preview-canvas');
        this.fontOptions = this.container.querySelectorAll('.font-option');
        this.modeTabs = this.container.querySelectorAll('.mode-tab');

        // Set initial values
        this.typedNameInput.value = this.typedText;
        this.updateModeUI();
    }

    async initSignaturePad() {
        if (typeof SignaturePad === 'undefined') {
            await this.loadScript(
                'https://cdn.jsdelivr.net/npm/signature_pad@4.1.7/dist/signature_pad.umd.min.js'
            );
        }

        this.signaturePad = new SignaturePad(this.canvas, {
            backgroundColor: 'rgb(255, 255, 255)',
            penColor: 'rgb(0, 0, 0)',
            minWidth: this.isMobile ? 1.5 : 1,
            maxWidth: this.isMobile ? 4 : 3,
            velocityFilterWeight: this.isMobile ? 0.6 : 0.7,
            throttle: this.isMobile ? 8 : 16,
        });

        this.resizeDrawCanvas();
        this.resizeTypeCanvas();
        this.renderTypedSignature();
    }

    loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    bindEvents() {
        // Draw pad events
        this.signaturePad.addEventListener('beginStroke', () => {
            this.isDrawing = true;
            this.isEmpty = false;
            this.updateDrawStatus();
            this.onSignatureChange({ isEmpty: false, isDrawing: true });
        });

        this.signaturePad.addEventListener('endStroke', () => {
            this.isDrawing = false;
            this.updateDrawStatus();
            this.onSignatureChange({ isEmpty: false, isDrawing: false });
        });

        // Clear button
        this.clearBtn.addEventListener('click', () => this.clear());

        // Mode tabs
        this.modeTabs.forEach((tab) => {
            tab.addEventListener('click', () => {
                this.mode = tab.dataset.mode;
                this.updateModeUI();
                this.onSignatureChange({ isEmpty: !this.validate(), isDrawing: false });
            });
        });

        // Typed name input
        this.typedNameInput.addEventListener('input', (e) => {
            this.typedText = e.target.value;
            this.renderTypedSignature();
            this.onSignatureChange({ isEmpty: !this.typedText.trim(), isDrawing: false });
        });

        // Font selector
        this.fontOptions.forEach((btn) => {
            btn.addEventListener('click', () => {
                this.selectedFont = btn.dataset.font;
                this.updateFontSelection();
                this.renderTypedSignature();
            });
        });

        // Resize
        window.addEventListener('resize', () => this.handleResize());
        window.addEventListener('orientationchange', () => {
            setTimeout(() => this.handleResize(), 200);
        });

        // Prevent zoom on double-tap (iOS)
        if (this.isMobile) {
            this.canvas.addEventListener(
                'touchstart',
                (e) => {
                    if (e.touches.length > 1) e.preventDefault();
                },
                { passive: false }
            );
        }
    }

    // --- Mode switching ---

    updateModeUI() {
        const isDraw = this.mode === 'draw';

        // Toggle panels
        this.drawPanel.style.display = isDraw ? '' : 'none';
        this.typePanel.style.display = isDraw ? 'none' : '';

        // Update tabs
        this.modeTabs.forEach((tab) => {
            const active = tab.dataset.mode === this.mode;
            tab.className = `mode-tab flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-md text-sm font-medium transition-all ${
                active
                    ? 'bg-white text-slate-800 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
            }`;
        });

        // Update hint
        this.modeHint.textContent = isDraw
            ? 'Zeichnen Sie Ihre Unterschrift mit der Maus oder dem Finger.'
            : 'Geben Sie Ihren Namen ein und wählen Sie eine Schriftart.';

        // Update font selection
        this.updateFontSelection();

        // Focus input in type mode
        if (!isDraw) {
            this.$nextFrame(() => {
                this.typedNameInput.focus();
                this.resizeTypeCanvas();
                this.renderTypedSignature();
            });
        } else {
            this.$nextFrame(() => this.resizeDrawCanvas());
        }
    }

    updateFontSelection() {
        this.fontOptions.forEach((btn) => {
            const active = btn.dataset.font === this.selectedFont;
            btn.className = `font-option flex-shrink-0 px-4 py-2 rounded-lg border-2 transition-all text-lg ${
                active
                    ? 'border-amber-400 bg-amber-50 text-slate-800'
                    : 'border-slate-200 text-slate-500 hover:border-slate-300'
            }`;
        });
    }

    // --- Draw mode ---

    resizeDrawCanvas() {
        if (!this.canvas || !this.signaturePad) return;

        const data = !this.signaturePad.isEmpty() ? this.signaturePad.toData() : null;
        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        const rect = this.canvas.getBoundingClientRect();

        this.canvas.width = rect.width * ratio;
        this.canvas.height = rect.height * ratio;

        const ctx = this.canvas.getContext('2d');
        ctx.scale(ratio, ratio);

        if (data) this.signaturePad.fromData(data);
    }

    updateDrawStatus() {
        this.placeholder.style.display = this.isEmpty ? 'flex' : 'none';
        if (this.isDrawing) {
            this.drawStatusEl.textContent = 'Zeichnen...';
        } else if (this.isEmpty) {
            this.drawStatusEl.textContent = 'Noch nicht unterschrieben';
        } else {
            this.drawStatusEl.textContent = 'Unterschrift erfasst';
        }
    }

    // --- Type mode ---

    resizeTypeCanvas() {
        if (!this.typePreviewCanvas) return;
        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        const rect = this.typePreviewCanvas.getBoundingClientRect();
        this.typePreviewCanvas.width = rect.width * ratio;
        this.typePreviewCanvas.height = rect.height * ratio;
    }

    renderTypedSignature() {
        const canvas = this.typePreviewCanvas;
        if (!canvas) return;

        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        const rect = canvas.getBoundingClientRect();

        // Ensure canvas is sized
        if (canvas.width !== rect.width * ratio || canvas.height !== rect.height * ratio) {
            canvas.width = rect.width * ratio;
            canvas.height = rect.height * ratio;
        }

        const ctx = canvas.getContext('2d');
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.scale(ratio, ratio);

        // Clear with white background
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, rect.width, rect.height);

        const text = this.typedText.trim();
        if (!text) {
            // Draw placeholder
            ctx.fillStyle = '#cbd5e1';
            ctx.font = `32px '${this.selectedFont}', cursive`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('Ihr Name', rect.width / 2, rect.height / 2);
            return;
        }

        // Calculate font size to fit width (max 56px)
        let fontSize = 56;
        ctx.font = `${fontSize}px '${this.selectedFont}', cursive`;
        let measured = ctx.measureText(text).width;
        const maxWidth = rect.width - 40;

        while (measured > maxWidth && fontSize > 20) {
            fontSize -= 2;
            ctx.font = `${fontSize}px '${this.selectedFont}', cursive`;
            measured = ctx.measureText(text).width;
        }

        // Draw signature text
        ctx.fillStyle = '#000000';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(text, rect.width / 2, rect.height / 2);

        // Draw subtle baseline
        const baselineY = rect.height / 2 + fontSize * 0.35;
        ctx.strokeStyle = '#e2e8f0';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(20, baselineY);
        ctx.lineTo(rect.width - 20, baselineY);
        ctx.stroke();
    }

    // --- Shared ---

    handleResize() {
        this.resizeDrawCanvas();
        this.resizeTypeCanvas();
        this.renderTypedSignature();
    }

    $nextFrame(fn) {
        requestAnimationFrame(() => requestAnimationFrame(fn));
    }

    clear() {
        if (this.mode === 'draw') {
            if (this.signaturePad) {
                this.signaturePad.clear();
                this.isEmpty = true;
                this.updateDrawStatus();
            }
        } else {
            this.typedText = '';
            this.typedNameInput.value = '';
            this.renderTypedSignature();
        }
        this.onSignatureChange({ isEmpty: true, isDrawing: false });
    }

    validate() {
        if (this.mode === 'draw') {
            return !this.isEmpty && this.signaturePad && !this.signaturePad.isEmpty();
        }
        return this.typedText.trim().length > 0;
    }

    getSignatureData() {
        if (this.mode === 'draw') {
            if (!this.signaturePad || this.signaturePad.isEmpty()) return null;
            return this.signaturePad.toDataURL('image/png');
        }

        if (!this.typedText.trim()) return null;

        // Generate a high-res PNG from the type canvas
        // Re-render at 2x for crisp output
        const exportCanvas = document.createElement('canvas');
        const width = 600;
        const height = 200;
        exportCanvas.width = width * 2;
        exportCanvas.height = height * 2;

        const ctx = exportCanvas.getContext('2d');
        ctx.scale(2, 2);

        // White background
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, width, height);

        // Render text
        const text = this.typedText.trim();
        let fontSize = 56;
        ctx.font = `${fontSize}px '${this.selectedFont}', cursive`;
        let measured = ctx.measureText(text).width;
        const maxWidth = width - 40;

        while (measured > maxWidth && fontSize > 20) {
            fontSize -= 2;
            ctx.font = `${fontSize}px '${this.selectedFont}', cursive`;
            measured = ctx.measureText(text).width;
        }

        ctx.fillStyle = '#000000';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(text, width / 2, height / 2);

        return exportCanvas.toDataURL('image/png');
    }
}

window.SignaturePadComponent = SignaturePadComponent;

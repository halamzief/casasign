/**
 * SignaturePad - Vanilla JS signature capture component
 * Uses signature_pad library for canvas-based signature capture
 * Mobile-optimized with touch support
 */

class SignaturePadComponent {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container #${containerId} not found`);
            return;
        }

        this.signerName = options.signerName || '';
        this.onSignatureChange = options.onSignatureChange || (() => {});

        this.signaturePad = null;
        this.canvas = null;
        this.isEmpty = true;
        this.isDrawing = false;
        this.isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        this.isLandscape = false;

        this.init();
    }

    async init() {
        this.render();
        await this.initSignaturePad();
        this.bindEvents();
    }

    render() {
        this.container.innerHTML = `
            <div class="bg-white rounded-lg p-6 shadow-sm border">
                <div class="mb-4">
                    <h3 class="text-lg font-semibold mb-2">Unterschrift</h3>
                    <p class="text-sm text-gray-600">
                        Zeichnen Sie Ihre Unterschrift mit der Maus oder dem Finger (Touch)
                    </p>
                </div>

                <div class="signature-canvas-wrapper relative bg-white rounded-lg border-2 border-gray-300 h-48 md:h-48 overflow-hidden" style="height: 12rem;">
                    <canvas class="signature-canvas w-full h-full touch-action-none"></canvas>
                    <div class="signature-placeholder absolute inset-0 flex items-center justify-center text-gray-400 text-lg pointer-events-none px-4 text-center">
                        Bitte hier unterschreiben: ${this.signerName}
                    </div>
                </div>

                <div class="mt-3 flex justify-between items-center">
                    <button type="button" class="clear-btn text-sm text-gray-600 hover:text-gray-900 underline">
                        Loschen
                    </button>
                    <p class="signature-status text-xs text-gray-500">
                        Noch nicht unterschrieben
                    </p>
                </div>
            </div>
        `;

        this.canvas = this.container.querySelector('.signature-canvas');
        this.placeholder = this.container.querySelector('.signature-placeholder');
        this.statusEl = this.container.querySelector('.signature-status');
        this.clearBtn = this.container.querySelector('.clear-btn');
    }

    async initSignaturePad() {
        // Load signature_pad library dynamically
        if (typeof SignaturePad === 'undefined') {
            await this.loadScript('https://cdn.jsdelivr.net/npm/signature_pad@4.1.7/dist/signature_pad.umd.min.js');
        }

        // Initialize with mobile-optimized settings
        this.signaturePad = new SignaturePad(this.canvas, {
            backgroundColor: 'rgb(255, 255, 255)',
            penColor: 'rgb(0, 0, 0)',
            minWidth: this.isMobile ? 1.5 : 1,
            maxWidth: this.isMobile ? 4 : 3,
            velocityFilterWeight: this.isMobile ? 0.6 : 0.7,
            throttle: this.isMobile ? 8 : 16
        });

        this.resizeCanvas();
        this.checkOrientation();
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
        // Signature pad events
        this.signaturePad.addEventListener('beginStroke', () => {
            this.isDrawing = true;
            this.isEmpty = false;
            this.updateUI();
            this.onSignatureChange({ isEmpty: false, isDrawing: true });
        });

        this.signaturePad.addEventListener('endStroke', () => {
            this.isDrawing = false;
            this.updateUI();
            this.onSignatureChange({ isEmpty: false, isDrawing: false });
        });

        // Clear button
        this.clearBtn.addEventListener('click', () => this.clear());

        // Window resize
        window.addEventListener('resize', () => this.handleResize());

        // Orientation change (mobile)
        window.addEventListener('orientationchange', () => {
            setTimeout(() => {
                this.checkOrientation();
                this.resizeCanvas();
            }, 200);
        });

        // Prevent zoom on double-tap (iOS)
        if (this.isMobile) {
            this.canvas.addEventListener('touchstart', (e) => {
                if (e.touches.length > 1) {
                    e.preventDefault();
                }
            }, { passive: false });
        }
    }

    checkOrientation() {
        this.isLandscape = window.matchMedia && window.matchMedia('(orientation: landscape)').matches;

        // Adjust canvas height for landscape on mobile
        const wrapper = this.container.querySelector('.signature-canvas-wrapper');
        if (this.isMobile && this.isLandscape && window.innerWidth <= 896) {
            wrapper.style.height = '10rem';
        } else if (this.isMobile) {
            wrapper.style.height = '16rem';
        } else {
            wrapper.style.height = '12rem';
        }
    }

    handleResize() {
        this.checkOrientation();
        this.resizeCanvas();
    }

    resizeCanvas() {
        if (!this.canvas || !this.signaturePad) return;

        // Save current signature data
        const signatureData = !this.signaturePad.isEmpty() ? this.signaturePad.toData() : null;

        // Calculate pixel ratio for high DPI displays
        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        const rect = this.canvas.getBoundingClientRect();

        // Set canvas dimensions
        this.canvas.width = rect.width * ratio;
        this.canvas.height = rect.height * ratio;

        // Scale context
        const ctx = this.canvas.getContext('2d');
        ctx.scale(ratio, ratio);

        // Restore signature after resize
        if (signatureData) {
            this.signaturePad.fromData(signatureData);
        }
    }

    updateUI() {
        // Update placeholder visibility
        this.placeholder.style.display = this.isEmpty ? 'flex' : 'none';

        // Update status text
        if (this.isDrawing) {
            this.statusEl.textContent = 'Zeichnen...';
        } else if (this.isEmpty) {
            this.statusEl.textContent = 'Noch nicht unterschrieben';
        } else {
            this.statusEl.textContent = 'Unterschrift erfasst';
        }
    }

    clear() {
        if (this.signaturePad) {
            this.signaturePad.clear();
            this.isEmpty = true;
            this.updateUI();
            this.onSignatureChange({ isEmpty: true, isDrawing: false });
        }
    }

    validate() {
        return !this.isEmpty && this.signaturePad && !this.signaturePad.isEmpty();
    }

    getSignatureData() {
        if (!this.signaturePad || this.signaturePad.isEmpty()) {
            return null;
        }
        // Return base64 PNG
        return this.signaturePad.toDataURL('image/png');
    }
}

// Export for use
window.SignaturePadComponent = SignaturePadComponent;

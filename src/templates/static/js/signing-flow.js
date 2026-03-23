/**
 * Signing Flow - Minimal fallback for consent modal data.
 *
 * The consent modal now uses inline Alpine.js x-data directly in the template.
 * This file provides a no-op fallback in case any legacy template references
 * the consentModalData function.
 */

window.consentModalData = function consentModalData() {
    return {
        identityConfirmed: false,
        contractReviewed: false,
        get canProceed() {
            return this.identityConfirmed && this.contractReviewed;
        },
        handleSubmit() {
            if (!this.canProceed) return;
            this.$dispatch('consent-done', {
                identity_confirmed: true,
                contract_reviewed: true,
            });
        },
    };
};

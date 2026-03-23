/**
 * Signing Flow Utilities
 *
 * Lightweight helpers for the signing page.
 * Main logic lives in signingPageData() within signing_page.html.
 */

/**
 * Format amount as German currency string.
 * @param {number} amount
 * @returns {string}
 */
function formatCurrencyDE(amount) {
    return new Intl.NumberFormat('de-DE', {
        style: 'currency',
        currency: 'EUR',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(amount);
}

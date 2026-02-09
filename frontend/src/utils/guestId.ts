/**
 * Guest ID management utilities
 * Generates and persists UUID for guest users
 */

const GUEST_ID_KEY = 'dpe_guest_id';

/**
 * Generate a UUID v4
 */
export function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

/**
 * Get or create guest ID from localStorage
 */
export function getOrCreateGuestId(): string {
  let guestId = localStorage.getItem(GUEST_ID_KEY);
  
  if (!guestId) {
    guestId = generateUUID();
    localStorage.setItem(GUEST_ID_KEY, guestId);
  }
  
  return guestId;
}

/**
 * Get current guest ID (returns null if not set)
 */
export function getGuestId(): string | null {
  return localStorage.getItem(GUEST_ID_KEY);
}

/**
 * Clear guest ID (for testing)
 */
export function clearGuestId(): void {
  localStorage.removeItem(GUEST_ID_KEY);
}

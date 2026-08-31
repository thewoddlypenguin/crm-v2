/**
 * Vitest setup: jsdom polyfills required by Radix UI interaction tests.
 * Radix calls hasPointerCapture/setPointerCapture on open and
 * scrollIntoView when focusing menu items — jsdom implements none of them.
 */
import { vi, beforeAll } from "vitest";

beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false);
  Element.prototype.setPointerCapture = vi.fn();
  Element.prototype.releasePointerCapture = vi.fn();
  Element.prototype.scrollIntoView = vi.fn();
});

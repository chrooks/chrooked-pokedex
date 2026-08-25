/* A random id for filter tokens and editor rows.
 *
 * `crypto.randomUUID` exists only in a secure context, and the dex is served
 * over plain HTTP to the handheld on the LAN — so on the device it was simply
 * undefined, and every call site threw inside its click handler. The visible
 * symptom was "tapping a filter does nothing": the menu stayed open, no token
 * appeared, and the console error never reached the screen.
 *
 * `crypto.getRandomValues` carries no such restriction, so the fallback builds
 * the same RFC-4122 v4 shape from it. Ids must stay random rather than
 * counted: they ride in the URL and in saved expressions, and a per-session
 * counter would hand a fresh token the id of one already decoded from the URL.
 */

function hex(byte: number): string {
  return byte.toString(16).padStart(2, "0");
}

export function uid(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();

  const bytes = crypto.getRandomValues(new Uint8Array(16));
  // Byte 6 carries the version nibble, byte 8 the variant bits.
  const digits = Array.from(bytes, (byte, index) =>
    hex(index === 6 ? (byte & 0x0f) | 0x40 : index === 8 ? (byte & 0x3f) | 0x80 : byte),
  ).join("");

  return [
    digits.slice(0, 8),
    digits.slice(8, 12),
    digits.slice(12, 16),
    digits.slice(16, 20),
    digits.slice(20),
  ].join("-");
}

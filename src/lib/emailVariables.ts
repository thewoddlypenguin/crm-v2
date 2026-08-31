/**
 * Email variable utilities — single frontend source of truth for the
 * supported {{variables}}, mirroring the backend allowlist in
 * email_variables.py. The backend re-renders everything authoritatively
 * before sending; these helpers exist for insertion UX and live previews.
 */

export interface EmailVariableInfo {
  token: string; // literal "{{my_name}}" including braces
  name: string; // "my_name"
  description: string;
}

/** Sender variables — resolve from the current user's Email Settings. */
export const SENDER_VARIABLES: EmailVariableInfo[] = [
  { token: "{{my_name}}", name: "my_name", description: "Your display name" },
  { token: "{{my_email}}", name: "my_email", description: "Your email address" },
  { token: "{{my_phone}}", name: "my_phone", description: "Your phone number" },
];

/** Lead variables — resolve from the lead the email is sent to. */
export const LEAD_VARIABLES: EmailVariableInfo[] = [
  { token: "{{lead_name}}", name: "lead_name", description: "Lead's full name" },
  { token: "{{lead_first_name}}", name: "lead_first_name", description: "Lead's first name" },
  { token: "{{lead_business}}", name: "lead_business", description: "Lead's business name" },
  { token: "{{lead_email}}", name: "lead_email", description: "Lead's email address" },
  { token: "{{lead_phone}}", name: "lead_phone", description: "Lead's phone number" },
];

export const EMAIL_VARIABLES: EmailVariableInfo[] = [...SENDER_VARIABLES, ...LEAD_VARIABLES];

const SUPPORTED_NAMES = new Set(EMAIL_VARIABLES.map((v) => v.name));

/** Unknown {{tokens}} in the text (allowlist check — ANY {{...}} construct
 * is captured so dotted/bracketed junk is flagged, mirroring the backend). */
export function findUnknownVariables(text: string): string[] {
  const names = new Set<string>();
  const re = /\{\{\s*([^{}]+?)\s*\}\}/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (!SUPPORTED_NAMES.has(m[1])) names.add(m[1]);
  }
  return [...names];
}

/**
 * Insert text at the caret of an input/textarea and return the new value
 * plus caret position. Falls back to appending at the end when the element
 * has no selection info (touch keyboards, unmounted inputs, jsdom).
 *
 * Pure/string-based so it is directly unit-testable.
 */
export function insertAtCursor(
  el: HTMLTextAreaElement | HTMLInputElement | null,
  current: string,
  insertion: string,
): { value: string; caret: number } {
  const supportsCursor =
    el &&
    typeof (el as HTMLTextAreaElement).selectionStart === "number" &&
    typeof (el as HTMLTextAreaElement).selectionEnd === "number";

  if (supportsCursor) {
    const start = el.selectionStart!;
    const end = el.selectionEnd!;
    // Ensure a space before the insertion when gluing onto a word
    const before = current.slice(0, start);
    const needsSpaceBefore = before.length > 0 && !/\s$/.test(before) && !before.endsWith("\n");
    const padded = (needsSpaceBefore ? " " : "") + insertion;
    const value = before + padded + current.slice(end);
    const caret = start + padded.length;
    return { value, caret };
  }

  // Fallback: append at end with a separating space
  const needsSpace = current.length > 0 && !/\s$/.test(current);
  const value = current + (needsSpace ? " " : "") + insertion;
  return { value, caret: value.length };
}

/** Restore focus + caret to an element after a React state update. */
export function restoreCursor(
  el: HTMLTextAreaElement | HTMLInputElement | null,
  caret: number,
): void {
  if (!el) return;
  requestAnimationFrame(() => {
    el.focus();
    try {
      el.setSelectionRange(caret, caret);
    } catch {
      // some input types (email/number) don't support selection — ignore
    }
  });
}

/**
 * Frontend tests: email variable utilities + VariablePicker insertion behavior.
 * Run:  bunx vitest run
 */
import { describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useRef } from "react";
import {
  EMAIL_VARIABLES,
  LEAD_VARIABLES,
  SENDER_VARIABLES,
  findUnknownVariables,
  insertAtCursor,
} from "../src/lib/emailVariables";
import VariablePicker from "../src/components/VariablePicker";

// ─── emailVariables: allowlist ───────────────────────────────────────────────

describe("emailVariables definitions", () => {
  it("exposes exactly the 8 supported variables mirroring the backend", () => {
    expect(SENDER_VARIABLES.map((v) => v.token)).toEqual([
      "{{my_name}}", "{{my_email}}", "{{my_phone}}",
    ]);
    expect(LEAD_VARIABLES.map((v) => v.token)).toEqual([
      "{{lead_name}}", "{{lead_first_name}}", "{{lead_business}}",
      "{{lead_email}}", "{{lead_phone}}",
    ]);
    expect(EMAIL_VARIABLES).toHaveLength(8);
  });

  it("flags unknown tokens and ignores supported ones", () => {
    expect(findUnknownVariables("Hi {{lead_first_name}} — {{my_name}}!")).toEqual([]);
    expect(findUnknownVariables("{{bogus}} {{my_name}} {{user.password}}")).toEqual([
      "bogus", "user.password",
    ]);
    expect(findUnknownVariables("no tokens here")).toEqual([]);
  });
});

// ─── insertAtCursor: cursor-position insertion ───────────────────────────────

function makeEl(value: string, start: number, end = start) {
  return {
    selectionStart: start,
    selectionEnd: end,
    setSelectionRange: vi.fn(),
    focus: vi.fn(),
  } as unknown as HTMLTextAreaElement;
}

describe("insertAtCursor", () => {
  it("inserts at cursor in the middle of text (space-glued onto the preceding word)", () => {
    const el = makeEl("Hello world", 5);
    const { value, caret } = insertAtCursor(el, "Hello world", "{{lead_first_name}}");
    expect(value).toBe("Hello {{lead_first_name}} world");
    expect(caret).toBe("Hello {{lead_first_name}}".length);
  });

  it("inserts at start", () => {
    const el = makeEl("", 0);
    const { value, caret } = insertAtCursor(el, "", "{{my_name}}");
    expect(value).toBe("{{my_name}}");
    expect(caret).toBe("{{my_name}}".length);
  });

  it("replaces the current selection", () => {
    const el = makeEl("before SELECT after", 7, 13);
    const { value } = insertAtCursor(el, "before SELECT after", "{{lead_name}}");
    expect(value).toBe("before {{lead_name}} after");
  });

  it("adds a separating space when gluing onto a word", () => {
    const el = makeEl("Hi", 2);
    const { value } = insertAtCursor(el, "Hi", "{{lead_first_name}}");
    expect(value).toBe("Hi {{lead_first_name}}");
  });

  it("does not double-space before whitespace", () => {
    const el = makeEl("Hi ", 3);
    const { value } = insertAtCursor(el, "Hi ", "{{lead_name}}");
    expect(value).toBe("Hi {{lead_name}}");
  });

  it("falls back to append when element is null", () => {
    const { value, caret } = insertAtCursor(null, "existing text", "{{my_email}}");
    expect(value).toBe("existing text {{my_email}}");
    expect(caret).toBe(value.length);
  });

  it("falls back to append when element has no selection info (touch keyboards)", () => {
    const el = {} as HTMLTextAreaElement;
    const { value } = insertAtCursor(el, "draft", "{{lead_phone}}");
    expect(value).toBe("draft {{lead_phone}}");
  });

  it("does not insert into placeholders — value argument is the real field value", () => {
    // Regression: insertion must use the controlled value, not placeholder text
    const el = makeEl("Real subject", 12);
    const { value } = insertAtCursor(el, "Real subject", "{{lead_name}}");
    expect(value).toBe("Real subject {{lead_name}}");
    expect(value).not.toContain("placeholder");
  });
});

// ─── VariablePicker component ────────────────────────────────────────────────

function PickerHarness({ onInsert, initialValue }: { onInsert: (v: string, c: number) => void; initialValue: string }) {
  const ref = useRef<HTMLTextAreaElement>(null);
  return (
    <div>
      <textarea ref={ref} defaultValue={initialValue} data-testid="target" />
      <VariablePicker
        targetRef={ref}
        value={initialValue}
        onInsert={onInsert}
      />
    </div>
  );
}

// Radix DropdownMenu opens on pointerdown gated on pointerType:'mouse' +
// button:0 — jsdom has no PointerEvent, and userEvent's async event queue
// deadlocks with Radix's focus scheduling in jsdom. The deterministic path:
// focus + synchronous keyDown('Enter') inside act(), which Radix handles
// identically to a real keyboard open.
import { act } from "react";

function openPickerMenu() {
  const trigger = screen.getByTestId("variable-picker-trigger");
  trigger.focus();
  act(() => {
    fireEvent.keyDown(trigger, { key: "Enter" });
  });
}

describe("VariablePicker", () => {
  it("renders the Insert variable trigger", () => {
    render(<PickerHarness onInsert={() => {}} initialValue="" />);
    expect(screen.getByTestId("variable-picker-trigger")).toBeTruthy();
    cleanup();
  });

  it("opens a grouped menu with sender + lead variables and inserts into the body at the cursor on select", () => {
    const onInsert = vi.fn();
    render(<PickerHarness onInsert={onInsert} initialValue="Hi " />);

    // Simulate the user having their caret at the end of "Hi " in the body
    const target = screen.getByTestId("target") as HTMLTextAreaElement;
    target.focus();
    target.setSelectionRange(3, 3);

    openPickerMenu();
    const item = screen.getAllByText("{{lead_first_name}}").find((n) => n.tagName === "CODE");
    expect(item).toBeTruthy();

    // Selecting a group item fires onInsert with the caret-replayed value
    act(() => {
      fireEvent.click(item!.closest('[role="menuitem"]')!);
    });
    expect(onInsert).toHaveBeenCalledTimes(1);
    const [newValue, caret] = onInsert.mock.calls[0];
    expect(newValue).toBe("Hi {{lead_first_name}}");
    expect(caret).toBe(newValue.length);
    cleanup();
  });

  it("lists all 8 variables in the menu", () => {
    render(<PickerHarness onInsert={() => {}} initialValue="" />);
    openPickerMenu();
    for (const v of EMAIL_VARIABLES) {
      // token text appears as a <code> element in the menu
      const matches = screen.getAllByText((_, node) => node?.textContent === v.token && node.tagName === "CODE");
      expect(matches.length).toBeGreaterThan(0);
    }
    cleanup();
  });

  it("shows group labels", () => {
    render(<PickerHarness onInsert={() => {}} initialValue="" />);
    openPickerMenu();
    expect(screen.getByText("Sender variables")).toBeTruthy();
    expect(screen.getByText("Lead variables")).toBeTruthy();
    cleanup();
  });

  it("can be disabled", () => {
    const ref = { current: null } as React.RefObject<HTMLTextAreaElement>;
    render(<VariablePicker targetRef={ref} value="" onInsert={() => {}} disabled />);
    const trigger = screen.getByTestId("variable-picker-trigger") as HTMLButtonElement;
    expect(trigger.disabled).toBe(true);
    cleanup();
  });
});

/**
 * Frontend tests: TagInput component (tags feature).
 * Run:  npm run test
 *
 * TagInput is a plain controlled input (no Radix portal), so regular
 * fireEvent/userEvent flows work directly — unlike DropdownMenu.
 */
import { describe, expect, it, vi, afterEach } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import TagInput from "../src/components/TagInput";

afterEach(cleanup);

function setup(props: Partial<Parameters<typeof TagInput>[0]> = {}) {
  const onChange = vi.fn();
  const utils = render(
    <TagInput value={props.value ?? []} onChange={onChange} {...props} />
  );
  // The inner input has no reliable role/label — select it directly.
  const input = document.querySelector("input") as HTMLInputElement;
  return { onChange, input, ...utils };
}

describe("TagInput", () => {
  it("renders existing tags as chips with remove buttons", () => {
    render(<TagInput value={["vip", "hot lead"]} onChange={() => {}} />);
    expect(screen.getByText("vip")).toBeTruthy();
    expect(screen.getByText("hot lead")).toBeTruthy();
    expect(screen.getByLabelText("Remove tag vip")).toBeTruthy();
    expect(screen.getByLabelText("Remove tag hot lead")).toBeTruthy();
  });

  it("normalizes (lowercase, collapse spaces) and adds on Enter", () => {
    const { onChange, input } = setup();
    fireEvent.change(input, { target: { value: "  Hot   LEAD  " } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["hot lead"]);
  });

  it("adds on comma: character never reaches the draft (preventDefault)", () => {
    const { onChange, input } = setup();
    fireEvent.change(input, { target: { value: "vip" } });
    fireEvent.keyDown(input, { key: "," });
    expect(onChange).toHaveBeenCalledWith(["vip"]);
  });

  it("strips a trailing comma if the character still lands in the draft (mobile race)", () => {
    const { onChange, input } = setup();
    fireEvent.change(input, { target: { value: "vip," } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["vip"]);
  });

  it("rejects duplicates and empty tags (onChange never called)", () => {
    const { onChange, input } = setup({ value: ["vip"] });
    fireEvent.change(input, { target: { value: "vip" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).not.toHaveBeenCalled();
  });

  it("Backspace on empty draft removes the last tag", () => {
    const onChange = vi.fn();
    render(<TagInput value={["a", "b"]} onChange={onChange} />);
    const input = document.querySelector("input") as HTMLInputElement;
    fireEvent.keyDown(input, { key: "Backspace" });
    expect(onChange).toHaveBeenCalledWith(["a"]);
  });

  it("clicking a chip's ✕ removes that tag", () => {
    const onChange = vi.fn();
    render(<TagInput value={["a", "b", "c"]} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText("Remove tag b"));
    expect(onChange).toHaveBeenCalledWith(["a", "c"]);
  });

  it("commits the draft on blur", () => {
    const { onChange, input } = setup();
    fireEvent.change(input, { target: { value: "blurme" } });
    fireEvent.blur(input);
    expect(onChange).toHaveBeenCalledWith(["blurme"]);
  });

  it("shows matching unused suggestions once a draft is typed, and clicking adds the tag", () => {
    const onChange = vi.fn();
    render(
      <TagInput value={["vip"]} onChange={onChange} suggestions={["vip", "newsletter", "webinar"]} />
    );
    expect(screen.queryByText("+ newsletter")).toBeNull();

    const input = document.querySelector("input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "new" } });
    expect(screen.getByText("+ newsletter")).toBeTruthy();
    expect(screen.queryByText("+ webinar")).toBeNull();

    fireEvent.click(screen.getByText("+ newsletter"));
    expect(onChange).toHaveBeenCalledWith(["vip", "newsletter"]);
  });

  it("enforces the 20-tag cap", () => {
    const value = Array.from({ length: 20 }, (_, i) => `tag${i}`);
    const { onChange, input } = setup({ value });
    fireEvent.change(input, { target: { value: "onemore" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).not.toHaveBeenCalled();
  });
});

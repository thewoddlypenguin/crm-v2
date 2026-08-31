/**
 * VariablePicker — "Insert variable" dropdown for email composition surfaces.
 *
 * Inserts supported {{variables}} into a subject/body field AT THE CURSOR.
 * Grouped: Sender variables / Lead variables. Works on desktop and mobile:
 * the trigger button is large enough for touch, and the grouped list closes
 * on selection. Works with DropdownMenu or as a controlled popover-like
 * block (for automated tests).
 */
import { useRef } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ChevronDown, Variable } from "lucide-react";
import {
  LEAD_VARIABLES,
  SENDER_VARIABLES,
  insertAtCursor,
  restoreCursor,
  type EmailVariableInfo,
} from "@/lib/emailVariables";

interface VariablePickerProps {
  /** The field being edited — used to read caret + current value. */
  targetRef: React.RefObject<HTMLTextAreaElement | HTMLInputElement | null>;
  /** Current value of the target field. */
  value: string;
  /** Called with the new field value after insertion. */
  onInsert: (newValue: string, caret: number) => void;
  /** Accessible label + button text. */
  label?: string;
  disabled?: boolean;
}

export function VariablePicker({ targetRef, value, onInsert, label = "Insert variable", disabled }: VariablePickerProps) {
  // Remember the caret at pointerdown (mobile keyboards blur inputs before
  // the menu opens; the browser still reports selectionStart correctly).
  const caretRef = useRef<{ start: number; end: number } | null>(null);

  const captureCaret = () => {
    const el = targetRef.current;
    if (el && typeof el.selectionStart === "number") {
      caretRef.current = { start: el.selectionStart, end: el.selectionEnd ?? el.selectionStart };
    } else {
      caretRef.current = null;
    }
  };

  const handleInsert = (variable: EmailVariableInfo) => {
    const el = targetRef.current;
    // Replay the captured caret into the element so insertAtCursor uses it
    if (el && caretRef.current) {
      try {
        el.setSelectionRange(caretRef.current.start, caretRef.current.end);
      } catch {
        // ignore — insertAtCursor falls back to append
      }
    }
    const { value: newValue, caret } = insertAtCursor(el, value, variable.token);
    onInsert(newValue, caret);
    restoreCursor(el, caret);
  };

  const renderGroup = (title: string, vars: EmailVariableInfo[]) => (
    <>
      <DropdownMenuLabel className="text-xs text-muted-foreground">{title}</DropdownMenuLabel>
      {vars.map((v) => (
        <DropdownMenuItem
          key={v.name}
          onSelect={(e) => {
            e.preventDefault(); // keep focus so restoreCursor() can reposition
            handleInsert(v);
          }}
          className="gap-2"
        >
          <code className="text-xs font-semibold text-primary">{v.token}</code>
          <span className="text-xs text-muted-foreground">{v.description}</span>
        </DropdownMenuItem>
      ))}
    </>
  );

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          data-testid="variable-picker-trigger"
          aria-label={label}
          title={label}
          disabled={disabled}
          onPointerDown={captureCaret}
          onMouseDown={captureCaret}
          className="inline-flex h-8 items-center gap-1 rounded-md border border-border bg-background px-2.5 text-xs font-medium text-foreground hover:bg-muted disabled:opacity-50"
        >
          <Variable className="h-3.5 w-3.5" aria-hidden="true" />
          <span>{label}</span>
          <ChevronDown className="h-3 w-3 opacity-60" aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-72 max-h-80 overflow-y-auto">
        {renderGroup("Sender variables", SENDER_VARIABLES)}
        <DropdownMenuSeparator />
        {renderGroup("Lead variables", LEAD_VARIABLES)}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default VariablePicker;

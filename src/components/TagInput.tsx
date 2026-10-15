import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { X } from "lucide-react";

interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  suggestions?: string[];
  placeholder?: string;
  id?: string;
}

const MAX_TAGS = 20;
const MAX_TAG_LENGTH = 40;

/**
 * Tag editor: type + Enter (or comma) to add, click ✕ to remove.
 * Suggestions from the org's existing tags; Enter with an exact suggestion
 * match adds it. Tags are normalized (lowercase, trimmed) to mirror the API.
 */
export default function TagInput({ value, onChange, suggestions = [], placeholder, id }: TagInputProps) {
  const [draft, setDraft] = useState("");

  const addTag = (raw: string) => {
    const tag = raw
      .trim()
      .toLowerCase()
      .replace(/,+$/, "") // defensive: mobile keyboards may commit the comma before keydown preventDefault
      .replace(/\s+/g, " ");
    if (!tag || value.includes(tag) || value.length >= MAX_TAGS || tag.length > MAX_TAG_LENGTH) {
      setDraft("");
      return;
    }
    onChange([...value, tag]);
    setDraft("");
  };

  const removeTag = (tag: string) => {
    onChange(value.filter((t) => t !== tag));
  };

  const openSuggestions = suggestions.filter(
    (s) => !value.includes(s) && s.includes(draft.trim().toLowerCase()) && draft.trim() !== ""
  );

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-input bg-background px-2.5 py-2 focus-within:ring-1 focus-within:ring-ring">
        {value.map((tag) => (
          <Badge key={tag} variant="secondary" className="gap-1 pr-1">
            {tag}
            <button
              type="button"
              aria-label={`Remove tag ${tag}`}
              className="rounded-full hover:bg-muted-foreground/20 p-0.5"
              onClick={() => removeTag(tag)}
            >
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
        <Input
          id={id}
          className="h-6 flex-1 min-w-[120px] border-0 p-0 text-sm shadow-none focus-visible:ring-0"
          value={draft}
          placeholder={value.length === 0 ? (placeholder || "Add tags (Enter to add)") : ""}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              addTag(draft);
            } else if (e.key === "Backspace" && draft === "" && value.length > 0) {
              removeTag(value[value.length - 1]);
            }
          }}
          onBlur={() => {
            if (draft.trim()) addTag(draft);
          }}
        />
      </div>
      {openSuggestions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {openSuggestions.slice(0, 6).map((s) => (
            <button
              key={s}
              type="button"
              className="inline-flex items-center rounded-full border border-dashed border-border px-2 py-0.5 text-xs text-muted-foreground hover:bg-muted"
              onClick={() => addTag(s)}
            >
              + {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

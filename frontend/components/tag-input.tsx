"use client";

import { X } from "lucide-react";
import { useState } from "react";

import { cn } from "@/utils/cn";

interface TagInputProps {
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  id?: string;
  className?: string;
}

/** Chip list editor: Enter or comma adds, Backspace on empty input removes the last chip. */
export function TagInput({ value, onChange, placeholder = "Type and press Enter", id, className }: TagInputProps) {
  const [draft, setDraft] = useState("");

  const add = (raw: string) => {
    const items = raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (!items.length) return;
    const lower = new Set(value.map((v) => v.toLowerCase()));
    const next = [...value];
    for (const item of items) {
      if (!lower.has(item.toLowerCase())) {
        next.push(item);
        lower.add(item.toLowerCase());
      }
    }
    onChange(next);
    setDraft("");
  };

  return (
    <div
      className={cn(
        "flex min-h-10 flex-wrap items-center gap-1.5 rounded-xl border border-input bg-card-solid px-2.5 py-1.5 focus-within:border-transparent focus-within:ring-2 focus-within:ring-ring",
        className,
      )}
    >
      {value.map((tag) => (
        <span key={tag} className="inline-flex items-center gap-1 rounded-full bg-accent px-2.5 py-0.5 text-xs font-medium text-accent-foreground">
          {tag}
          <button
            type="button"
            aria-label={`Remove ${tag}`}
            className="cursor-pointer opacity-70 hover:opacity-100"
            onClick={() => onChange(value.filter((v) => v !== tag))}
          >
            <X className="size-3" />
          </button>
        </span>
      ))}
      <input
        id={id}
        value={draft}
        placeholder={value.length ? "" : placeholder}
        className="min-w-24 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        onChange={(e) => {
          const v = e.target.value;
          if (v.endsWith(",")) add(v);
          else setDraft(v);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            add(draft);
          } else if (e.key === "Backspace" && !draft && value.length) {
            onChange(value.slice(0, -1));
          }
        }}
        onBlur={() => add(draft)}
      />
    </div>
  );
}

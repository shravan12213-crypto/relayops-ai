import { computeWordDiff } from "@/lib/diff-utils";
import { cn } from "@/lib/utils";

export interface WordDiffProps {
  originalText: string;
  editedText: string;
  className?: string;
}

export function WordDiff({ originalText, editedText, className }: WordDiffProps) {
  const tokens = computeWordDiff(originalText, editedText);

  return (
    <div
      className={cn(
        "rounded-md border border-card-border bg-canvas-2 p-2.5 font-sans text-xs leading-relaxed text-ink",
        className,
      )}
    >
      <div className="flex flex-wrap gap-x-1 gap-y-0.5">
        {tokens.map((tok, idx) => {
          if (tok.type === "added") {
            return (
              <span
                key={idx}
                className="rounded bg-verified/20 px-1 text-verified font-medium"
              >
                {tok.word}
              </span>
            );
          }
          if (tok.type === "removed") {
            return (
              <span
                key={idx}
                className="rounded bg-destructive/15 px-1 text-destructive line-through opacity-80"
              >
                {tok.word}
              </span>
            );
          }
          return <span key={idx}>{tok.word}</span>;
        })}
      </div>
    </div>
  );
}

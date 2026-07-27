import type { ClarifyQuestion } from "../../lib/types";

type ClarifyOption = NonNullable<ClarifyQuestion["options"]>[number];

type Props = {
  disabled: boolean;
  option: ClarifyOption;
  selected: boolean;
  onSelect: (value: string) => void;
};

export function ClarifyOptionButton({ disabled, onSelect, option, selected }: Props) {
  return (
    <button
      aria-label={option.label}
      aria-pressed={selected}
      className={
        selected
          ? "min-h-16 rounded-lg border border-accent/60 bg-accent/15 px-3 py-2 text-left text-sm text-fg shadow-[inset_0_0_0_1px_rgb(255_255_255/0.04)]"
          : "min-h-16 rounded-lg border border-border/60 bg-bg-muted/70 px-3 py-2 text-left text-sm text-fg transition hover:border-accent/40 hover:bg-bg-app disabled:text-fg-muted"
      }
      disabled={disabled}
      type="button"
      onClick={() => onSelect(option.value)}
    >
      <span className="block font-semibold leading-5">{option.label}</span>
      {option.description ? (
        <span className="mt-1 block text-xs leading-5 text-fg-muted">{option.description}</span>
      ) : null}
    </button>
  );
}

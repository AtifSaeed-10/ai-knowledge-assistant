import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * The type scale uses names (`text-meta`, `text-ui`) rather than Tailwind's
 * `text-sm`/`text-lg`. Without this, tailwind-merge reads them as colours and
 * drops the size whenever a class list also sets one — so tell it the names.
 */
const FONT_SIZES = [
  "label",
  "meta",
  "ui",
  "body",
  "answer",
  "title",
  "h2",
  "h1",
  "display",
];

const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: FONT_SIZES }],
    },
  },
});

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

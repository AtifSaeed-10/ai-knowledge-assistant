/**
 * Wire values are unchanged — only the user-facing labels differ.
 * `normal` searches every ready document, `super_focused` answers from one.
 */
export type ProductMode = "normal" | "super_focused";

export interface ProductModeOption {
  id: ProductMode;
  label: string;
  description: string;
}

export const PRODUCT_MODES: ProductModeOption[] = [
  {
    id: "normal",
    label: "All documents",
    description: "Search every ready document in this workspace",
  },
  {
    id: "super_focused",
    label: "One document",
    description: "Answer only from the document you select",
  },
];

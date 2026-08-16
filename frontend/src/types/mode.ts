export type ProductMode = "normal" | "super_focused" | "agentic";

export const PRODUCT_MODES: {
  id: ProductMode;
  label: string;
  description: string;
  enabled: boolean;
}[] = [
  {
    id: "normal",
    label: "Normal",
    description: "Search all ready documents",
    enabled: true,
  },
  {
    id: "super_focused",
    label: "Super Focused",
    description: "Answer only from the selected document",
    enabled: true,
  },
  {
    id: "agentic",
    label: "Agentic",
    description: "Multi-step research — coming later",
    enabled: false,
  },
];

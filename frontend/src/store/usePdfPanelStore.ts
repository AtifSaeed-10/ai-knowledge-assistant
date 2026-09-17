import { create } from "zustand";

import {
  clampPdfPanelWidth,
  PDF_PANEL_DEFAULT_WIDTH,
} from "@/lib/workspace/pdfPanel";

const OPEN_KEY = "docusage_pdf_panel_open";
const WIDTH_KEY = "docusage_pdf_panel_width";

function readFlag(key: string, fallback: boolean): boolean {
  if (typeof window === "undefined") return fallback;
  try {
    const stored = window.localStorage.getItem(key);
    if (stored === null) return fallback;
    return stored === "true";
  } catch {
    return fallback;
  }
}

function readWidth(): number {
  if (typeof window === "undefined") return PDF_PANEL_DEFAULT_WIDTH;
  try {
    const stored = window.localStorage.getItem(WIDTH_KEY);
    if (!stored) return PDF_PANEL_DEFAULT_WIDTH;
    return clampPdfPanelWidth(Number(stored));
  } catch {
    return PDF_PANEL_DEFAULT_WIDTH;
  }
}

function persist(key: string, value: string) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* private mode — the pane still works for this visit */
  }
}

interface PdfPanelState {
  isOpen: boolean;
  /** True when the reader pressed Show PDF (phones use this for the overlay). */
  pinned: boolean;
  /** Last file the reader opened or uploaded, when no citation is active. */
  previewDocumentId: string | null;
  width: number;
  focusPage: number | null;
  visiblePage: number;
  pageCount: number | null;
  navToken: number;
  open: (options?: { pinned?: boolean; documentId?: string }) => void;
  close: () => void;
  toggle: () => void;
  setWidth: (width: number, maxAvailable?: number) => void;
  requestPage: (page: number) => void;
  setVisiblePage: (page: number) => void;
  setPageCount: (count: number | null) => void;
}

export const usePdfPanelStore = create<PdfPanelState>((set, get) => ({
  isOpen: readFlag(OPEN_KEY, true),
  pinned: false,
  previewDocumentId: null,
  width: readWidth(),
  focusPage: null,
  visiblePage: 1,
  pageCount: null,
  navToken: 0,

  open: (options) => {
    persist(OPEN_KEY, "true");
    set({
      isOpen: true,
      pinned: options?.pinned ? true : get().pinned,
      previewDocumentId: options?.documentId ?? get().previewDocumentId,
    });
  },

  close: () => {
    persist(OPEN_KEY, "false");
    set({ isOpen: false, pinned: false });
  },

  toggle: () => {
    if (get().isOpen) {
      get().close();
      return;
    }
    get().open({ pinned: true });
  },

  setWidth: (width, maxAvailable) => {
    const next = clampPdfPanelWidth(width, maxAvailable);
    persist(WIDTH_KEY, String(next));
    set({ width: next });
  },

  requestPage: (page) => {
    if (!Number.isFinite(page) || page < 1) return;
    persist(OPEN_KEY, "true");
    set((state) => ({
      isOpen: true,
      pinned: true,
      focusPage: Math.floor(page),
      visiblePage: Math.floor(page),
      navToken: state.navToken + 1,
    }));
  },

  setVisiblePage: (page) => {
    if (!Number.isFinite(page) || page < 1) return;
    set({ visiblePage: Math.floor(page) });
  },

  setPageCount: (count) => {
    if (count === null) {
      set({ pageCount: null });
      return;
    }
    if (!Number.isFinite(count) || count < 1) return;
    const pageCount = Math.floor(count);
    set((state) => {
      const over = state.focusPage != null && state.focusPage > pageCount;
      return {
        pageCount,
        focusPage: over ? pageCount : state.focusPage,
        visiblePage: over ? pageCount : state.visiblePage,
        navToken: over ? state.navToken + 1 : state.navToken,
      };
    });
  },
}));

import { describe, expect, it } from "vitest";
import {
  canDrawHighlights,
  overlayRectsForPage,
  pagesForPdfViewer,
  pymupdfRegionToPdfUserRect,
  regionToOverlayRect,
  resolveEvidenceView,
  type ChunkEvidence,
  type EvidenceRegion,
  type ViewportLike,
} from "./coords";

const PAGE_VIEW = [0, 0, 612, 792] as const;

function region(overrides: Partial<EvidenceRegion> = {}): EvidenceRegion {
  return {
    page: 1,
    x0: 100,
    y0: 50,
    x1: 200,
    y1: 70,
    coord_space: "pdf",
    ...overrides,
  };
}

function evidence(overrides: Partial<ChunkEvidence> = {}): ChunkEvidence {
  return {
    chunk_id: "doc_0",
    document_id: "doc",
    page_start: 1,
    page_end: 1,
    snippet: "Supervised learning uses labeled examples.",
    highlight_available: true,
    regions: [region()],
    ...overrides,
  };
}

/** PDF user space → CSS top-left, matching PDF.js rotation-0 viewport math. */
function viewportAt(scale: number, pageHeight = 792): ViewportLike {
  return {
    convertToViewportRectangle: ([x0, y0, x1, y1]) => [
      x0 * scale,
      (pageHeight - y1) * scale,
      x1 * scale,
      (pageHeight - y0) * scale,
    ],
  };
}

/** Same matrix PDF.js 4.x PageViewport builds for rotation 0. */
function pdfJsRotation0Viewport(
  scale: number,
  viewBox: readonly [number, number, number, number]
): ViewportLike {
  const userScale = scale;
  const centerX = (viewBox[2] + viewBox[0]) / 2;
  const centerY = (viewBox[3] + viewBox[1]) / 2;
  const offsetCanvasX = Math.abs(centerX - viewBox[0]) * userScale;
  const offsetCanvasY = Math.abs(centerY - viewBox[1]) * userScale;
  const transform = [
    userScale,
    0,
    0,
    -userScale,
    offsetCanvasX - userScale * centerX,
    offsetCanvasY + userScale * centerY,
  ];
  const apply = (x: number, y: number) => [
    transform[0] * x + transform[2] * y + transform[4],
    transform[1] * x + transform[3] * y + transform[5],
  ];
  return {
    convertToViewportRectangle: ([x0, y0, x1, y1]) => {
      const a = apply(x0, y0);
      const b = apply(x1, y1);
      return [a[0], a[1], b[0], b[1]];
    },
  };
}

describe("citation → page", () => {
  it("opens the first cited page from stored regions", () => {
    const view = resolveEvidenceView({
      citationPage: 4,
      evidence: evidence({
        page_start: 4,
        page_end: 4,
        regions: [region({ page: 4 })],
      }),
    });
    expect(view.page).toBe(4);
    expect(view.pages).toEqual([4]);
    expect(view.canHighlight).toBe(true);
  });

  it("keeps citation focus while still listing every PDF page", () => {
    expect(pagesForPdfViewer(5)).toEqual([1, 2, 3, 4, 5]);
    expect(pagesForPdfViewer(1)).toEqual([1]);
    expect(pagesForPdfViewer(0)).toEqual([]);
    const view = resolveEvidenceView({
      citationPage: 3,
      evidence: evidence({
        page_start: 3,
        page_end: 3,
        regions: [region({ page: 3 })],
      }),
    });
    expect(view.page).toBe(3);
    expect(pagesForPdfViewer(5)[0]).toBe(1);
    expect(pagesForPdfViewer(5).at(-1)).toBe(5);
    expect(pagesForPdfViewer(5)).toContain(view.page);
  });

  it("falls back to page_start then citation page when highlighting is off", () => {
    const fromEvidence = resolveEvidenceView({
      citationPage: 9,
      evidence: evidence({
        highlight_available: false,
        page_start: 7,
        page_end: 7,
        regions: [],
      }),
    });
    expect(fromEvidence.page).toBe(7);
    expect(fromEvidence.pages).toEqual([7]);
    expect(fromEvidence.canHighlight).toBe(false);

    const fromCitation = resolveEvidenceView({
      citationPage: 9,
      evidence: null,
      citationSnippet: "Page fallback snippet.",
    });
    expect(fromCitation.page).toBe(9);
    expect(fromCitation.pages).toEqual([9]);
    expect(fromCitation.canHighlight).toBe(false);
    expect(fromCitation.snippet).toBe("Page fallback snippet.");
  });
});

describe("highlight policy", () => {
  it("draws stored regions when highlight_available is true", () => {
    const rects = overlayRectsForPage(evidence(), 1, PAGE_VIEW, viewportAt(1));
    expect(rects).toEqual([{ left: 100, top: 50, width: 100, height: 20 }]);
  });

  it("supports multiple regions on one page", () => {
    const packed = evidence({
      regions: [region(), region({ y0: 80, y1: 96 })],
    });
    const rects = overlayRectsForPage(packed, 1, PAGE_VIEW, viewportAt(1));
    expect(rects).toHaveLength(2);
    expect(rects[1]).toEqual({ left: 100, top: 80, width: 100, height: 16 });
  });

  it("keeps multi-page regions on their own pages", () => {
    const packed = evidence({
      page_start: 2,
      page_end: 3,
      regions: [region({ page: 2 }), region({ page: 3, y0: 40, y1: 58 })],
    });
    const view = resolveEvidenceView({ citationPage: 2, evidence: packed });
    expect(view.page).toBe(2);
    expect(view.pages).toEqual([2, 3]);
    expect(overlayRectsForPage(packed, 2, PAGE_VIEW, viewportAt(1))).toHaveLength(1);
    expect(overlayRectsForPage(packed, 3, PAGE_VIEW, viewportAt(1))).toHaveLength(1);
    expect(overlayRectsForPage(packed, 1, PAGE_VIEW, viewportAt(1))).toHaveLength(0);
  });

  it("shows snippet fallback and no overlays when highlighting is unavailable", () => {
    const packed = evidence({
      highlight_available: false,
      snippet: "Unmapped passage.",
      regions: [],
    });
    const view = resolveEvidenceView({ citationPage: 1, evidence: packed });
    expect(view.canHighlight).toBe(false);
    expect(view.snippet).toBe("Unmapped passage.");
    expect(overlayRectsForPage(packed, 1, PAGE_VIEW, viewportAt(1))).toEqual([]);
  });

  it("prefers quote-specific regions over the full chunk", () => {
    const packed = evidence({
      highlight_available: true,
      regions: [region({ y0: 10, y1: 200 }), region({ y0: 210, y1: 400 })],
      quote: "Supervised learning uses labeled examples.",
      quote_highlight_available: true,
      quote_regions: [region({ y0: 50, y1: 70 })],
    });
    const rects = overlayRectsForPage(packed, 1, PAGE_VIEW, viewportAt(1));
    expect(rects).toEqual([{ left: 100, top: 50, width: 100, height: 20 }]);
    const view = resolveEvidenceView({ citationPage: 1, evidence: packed });
    expect(view.canHighlight).toBe(true);
    expect(view.pages).toEqual([1]);
  });

  it("uses chunk regions when no quote is present", () => {
    const packed = evidence({
      quote: null,
      quote_highlight_available: false,
      quote_regions: [],
      highlight_available: true,
      regions: [region()],
    });
    expect(overlayRectsForPage(packed, 1, PAGE_VIEW, viewportAt(1))).toHaveLength(1);
    const view = resolveEvidenceView({ citationPage: 1, evidence: packed });
    expect(view.canHighlight).toBe(true);
  });

  it("does not paint the whole chunk when a quote cannot be mapped", () => {
    const packed = evidence({
      quote: "missing from the page",
      quote_highlight_available: false,
      quote_regions: [],
      quote_mapping_status: "not_in_chunk",
      highlight_available: true,
      regions: [region({ y0: 10, y1: 400 })],
      snippet: "Chunk snippet.",
    });
    expect(overlayRectsForPage(packed, 1, PAGE_VIEW, viewportAt(1))).toEqual([]);
    const view = resolveEvidenceView({ citationPage: 1, evidence: packed });
    expect(view.canHighlight).toBe(false);
    expect(view.page).toBe(1);
    expect(view.snippet).toBe("missing from the page");
  });

  it("does not paint the chunk when quote mapping claimed success without usable boxes", () => {
    const packed = evidence({
      highlight_available: true,
      quote: "Supervised learning uses labeled examples.",
      regions: [region({ y0: 10, y1: 400 })],
      quote_highlight_available: true,
      quote_regions: [region({ coord_space: "guess" })],
    });
    expect(canDrawHighlights(packed)).toBe(false);
    expect(overlayRectsForPage(packed, 1, PAGE_VIEW, viewportAt(1))).toEqual([]);
    const view = resolveEvidenceView({ citationPage: 4, evidence: packed });
    expect(view.canHighlight).toBe(false);
    expect(view.page).toBe(1);
    expect(view.snippet).toBe("Supervised learning uses labeled examples.");
  });

  it("falls back to page and snippet when stored regions are missing", () => {
    const packed = evidence({
      highlight_available: false,
      regions: [],
      snippet: "OCR or unmapped passage.",
      page_start: 7,
      page_end: 7,
    });
    const view = resolveEvidenceView({ citationPage: 1, evidence: packed });
    expect(view.canHighlight).toBe(false);
    expect(view.page).toBe(7);
    expect(view.snippet).toBe("OCR or unmapped passage.");
    expect(overlayRectsForPage(packed, 7, PAGE_VIEW, viewportAt(1))).toEqual([]);
  });

  it("does not treat relevance as highlight availability", () => {
    const packed = evidence({
      highlight_available: false,
      regions: [],
      snippet: "High score, no boxes.",
    });
    expect(canDrawHighlights(packed)).toBe(false);
    const view = resolveEvidenceView({ citationPage: 3, evidence: packed });
    expect(view.canHighlight).toBe(false);
    expect(view.snippet).toBe("High score, no boxes.");
  });

  it("keeps two quote highlights distinct", () => {
    const first = evidence({
      quote: "Supervised learning uses labeled examples.",
      quote_highlight_available: true,
      quote_regions: [region({ y0: 50, y1: 70 })],
    });
    const second = evidence({
      quote: "classification and regression",
      quote_highlight_available: true,
      quote_regions: [region({ y0: 210, y1: 230 })],
    });
    expect(overlayRectsForPage(first, 1, PAGE_VIEW, viewportAt(1))).toEqual([
      { left: 100, top: 50, width: 100, height: 20 },
    ]);
    expect(overlayRectsForPage(second, 1, PAGE_VIEW, viewportAt(1))).toEqual([
      { left: 100, top: 210, width: 100, height: 20 },
    ]);
  });

  it("focuses regions in top-to-bottom order", () => {
    const packed = evidence({
      regions: [region({ y0: 80, y1: 96 }), region({ y0: 50, y1: 70 })],
    });
    const rects = overlayRectsForPage(packed, 1, PAGE_VIEW, viewportAt(1));
    expect(rects[0]).toEqual({ left: 100, top: 50, width: 100, height: 20 });
    expect(rects[1]).toEqual({ left: 100, top: 80, width: 100, height: 16 });
  });

  it("never guesses highlights from leftover or invalid boxes", () => {
    expect(
      canDrawHighlights(
        evidence({
          highlight_available: false,
          regions: [region()],
        })
      )
    ).toBe(false);

    expect(
      overlayRectsForPage(
        evidence({
          highlight_available: true,
          regions: [
            region({ coord_space: "guess" }),
            region({ x1: 10, x0: 80 }),
            region({ page: 0 }),
          ],
        }),
        1,
        PAGE_VIEW,
        viewportAt(1)
      )
    ).toEqual([]);

    expect(
      overlayRectsForPage(evidence({ regions: [] }), 1, PAGE_VIEW, viewportAt(1))
    ).toEqual([]);
  });
});

describe("coordinate conversion", () => {
  it("converts PyMuPDF top-left boxes into PDF user space", () => {
    const pdfRect = pymupdfRegionToPdfUserRect(region(), PAGE_VIEW);
    expect(pdfRect).toEqual([100, 722, 200, 742]);
  });

  it("accounts for a non-zero page.view origin", () => {
    const pdfRect = pymupdfRegionToPdfUserRect(region(), [10, 20, 622, 812]);
    expect(pdfRect).toEqual([110, 742, 210, 762]);
  });

  it("maps PDF user space through the viewport to CSS overlay pixels", () => {
    const overlay = regionToOverlayRect(region(), PAGE_VIEW, viewportAt(1));
    expect(overlay).toEqual({ left: 100, top: 50, width: 100, height: 20 });
  });

  it("matches PDF.js PageViewport rotation-0 transform so CSS top equals PyMuPDF y0", () => {
    const overlay = regionToOverlayRect(region(), PAGE_VIEW, pdfJsRotation0Viewport(1, PAGE_VIEW));
    expect(overlay).toEqual({ left: 100, top: 50, width: 100, height: 20 });
  });
});

describe("zoom/resize repositioning", () => {
  it("recomputes overlay pixels when the viewport scale changes", () => {
    const packed = evidence();
    const atOne = overlayRectsForPage(packed, 1, PAGE_VIEW, viewportAt(1));
    const atTwo = overlayRectsForPage(packed, 1, PAGE_VIEW, viewportAt(2));
    expect(atOne[0]).toEqual({ left: 100, top: 50, width: 100, height: 20 });
    expect(atTwo[0]).toEqual({ left: 200, top: 100, width: 200, height: 40 });
    const jsAtTwo = overlayRectsForPage(
      packed,
      1,
      PAGE_VIEW,
      pdfJsRotation0Viewport(2, PAGE_VIEW)
    );
    expect(jsAtTwo[0]).toEqual({ left: 200, top: 100, width: 200, height: 40 });
  });
});

describe("visual evidence overlay policy", () => {
  it("does not paint chunk-wide boxes for figures or tables", () => {
    const figure = evidence({
      content_type: "figure_caption",
      highlight_available: true,
      regions: [region({ y0: 80, y1: 700 })],
    });
    expect(canDrawHighlights(figure)).toBe(false);
    expect(overlayRectsForPage(figure, 1, PAGE_VIEW, viewportAt(1))).toEqual([]);

    const table = evidence({
      content_type: "table",
      highlight_available: true,
      regions: [region({ y0: 80, y1: 700 })],
    });
    expect(canDrawHighlights(table)).toBe(false);
  });

  it("paints a tight caption quote when mapping succeeded", () => {
    const packed = evidence({
      content_type: "figure_caption",
      highlight_available: false,
      regions: [region({ y0: 80, y1: 700 })],
      quote: "Figure 2. Overview of the training pipeline.",
      quote_highlight_available: true,
      quote_regions: [region({ y0: 640, y1: 656 })],
    });
    expect(canDrawHighlights(packed)).toBe(true);
    expect(overlayRectsForPage(packed, 1, PAGE_VIEW, viewportAt(1))).toEqual([
      { left: 100, top: 640, width: 100, height: 16 },
    ]);
  });

  it("shows the page without overlays for scans", () => {
    const packed = evidence({
      content_type: "scanned_or_image",
      highlight_available: true,
      regions: [region({ page: 4 })],
      page_start: 4,
      page_end: 4,
    });
    const view = resolveEvidenceView({ citationPage: 4, evidence: packed });
    expect(view.canHighlight).toBe(false);
    expect(view.page).toBe(4);
    expect(overlayRectsForPage(packed, 4, PAGE_VIEW, viewportAt(1))).toEqual([]);
  });
});

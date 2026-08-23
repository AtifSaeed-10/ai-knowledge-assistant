export type EvidenceRegion = {
  page: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  coord_space: string;
};

export type ChunkEvidence = {
  chunk_id: string;
  document_id: string;
  page_start: number;
  page_end: number;
  snippet: string;
  highlight_available: boolean;
  regions: EvidenceRegion[];
  quote?: string | null;
  quote_highlight_available?: boolean;
  quote_regions?: EvidenceRegion[];
  quote_mapping_status?: string | null;
  content_type?: string | null;
};

export type OverlayRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

export type PdfUserRect = [number, number, number, number];

export type PageViewBox = readonly [number, number, number, number];

export type ViewportLike = {
  convertToViewportRectangle: (rect: PdfUserRect) => number[];
};

const PDF_COORD_SPACE = "pdf";

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isValidPage(value: unknown): value is number {
  return isFiniteNumber(value) && value >= 1 && Number.isInteger(value);
}

export function isUsableRegion(region: unknown): region is EvidenceRegion {
  if (!region || typeof region !== "object") return false;
  const item = region as EvidenceRegion;
  if (item.coord_space !== PDF_COORD_SPACE) return false;
  if (!isValidPage(item.page)) return false;
  if (
    !isFiniteNumber(item.x0) ||
    !isFiniteNumber(item.y0) ||
    !isFiniteNumber(item.x1) ||
    !isFiniteNumber(item.y1)
  ) {
    return false;
  }
  return item.x1 > item.x0 && item.y1 > item.y0;
}

function compareRegions(a: EvidenceRegion, b: EvidenceRegion): number {
  return a.page - b.page || a.y0 - b.y0 || a.x0 - b.x0;
}

function requestedQuote(evidence: ChunkEvidence | null | undefined): boolean {
  return Boolean(evidence?.quote && evidence.quote.trim());
}

function usableQuoteRegions(evidence: ChunkEvidence): EvidenceRegion[] {
  if (evidence.quote_highlight_available !== true) return [];
  return (evidence.quote_regions || []).filter(isUsableRegion).sort(compareRegions);
}

const VISUAL_CONTENT_TYPES = new Set([
  "figure_caption",
  "table",
  "scanned_or_image",
  "scanned_ocr",
  "low_text_layout",
]);

function usableChunkRegions(evidence: ChunkEvidence): EvidenceRegion[] {
  if (evidence.highlight_available !== true) return [];
  const kind = (evidence.content_type || "").toLowerCase();
  if (VISUAL_CONTENT_TYPES.has(kind)) return [];
  return (evidence.regions || []).filter(isUsableRegion).sort(compareRegions);
}

function usableRegions(evidence: ChunkEvidence | null): EvidenceRegion[] {
  if (!evidence) return [];
  const quoteRegions = usableQuoteRegions(evidence);
  if (quoteRegions.length > 0) return quoteRegions;
  // A verbatim quote was requested but could not be mapped. Do not paint the
  // whole chunk — that would look like the quote succeeded.
  if (requestedQuote(evidence)) return [];
  return usableChunkRegions(evidence);
}

export function canDrawHighlights(evidence: ChunkEvidence | null): boolean {
  return usableRegions(evidence).length > 0;
}

/**
 * PyMuPDF page space is top-left origin, y down, PDF points.
 * PDF.js page.view / convertToViewportRectangle use PDF user space
 * (origin bottom-left, y up).
 */
export function pymupdfRegionToPdfUserRect(
  region: EvidenceRegion,
  pageView: PageViewBox
): PdfUserRect | null {
  if (!isUsableRegion(region)) return null;
  if (pageView.length < 4) return null;
  const viewX0 = pageView[0];
  const viewY0 = pageView[1];
  const viewX1 = pageView[2];
  const viewY1 = pageView[3];
  if (
    !isFiniteNumber(viewX0) ||
    !isFiniteNumber(viewY0) ||
    !isFiniteNumber(viewX1) ||
    !isFiniteNumber(viewY1)
  ) {
    return null;
  }
  const pageHeight = viewY1 - viewY0;
  const pageWidth = viewX1 - viewX0;
  if (!(pageHeight > 0) || !(pageWidth > 0)) return null;

  const pdfX0 = viewX0 + region.x0;
  const pdfX1 = viewX0 + region.x1;
  const pdfY0 = viewY1 - region.y1;
  const pdfY1 = viewY1 - region.y0;
  return [pdfX0, pdfY0, pdfX1, pdfY1];
}

export function normalizeViewportRect(raw: number[] | null | undefined): OverlayRect | null {
  if (!raw || raw.length < 4) return null;
  const left = Math.min(raw[0], raw[2]);
  const right = Math.max(raw[0], raw[2]);
  const top = Math.min(raw[1], raw[3]);
  const bottom = Math.max(raw[1], raw[3]);
  const width = right - left;
  const height = bottom - top;
  if (
    !Number.isFinite(left) ||
    !Number.isFinite(top) ||
    !Number.isFinite(width) ||
    !Number.isFinite(height) ||
    width <= 0 ||
    height <= 0
  ) {
    return null;
  }
  return { left, top, width, height };
}

export function regionToOverlayRect(
  region: EvidenceRegion,
  pageView: PageViewBox,
  viewport: ViewportLike
): OverlayRect | null {
  const pdfRect = pymupdfRegionToPdfUserRect(region, pageView);
  if (!pdfRect) return null;
  try {
    return normalizeViewportRect(viewport.convertToViewportRectangle(pdfRect));
  } catch {
    return null;
  }
}

export function overlayRectsForPage(
  evidence: ChunkEvidence | null,
  pageNumber: number,
  pageView: PageViewBox,
  viewport: ViewportLike
): OverlayRect[] {
  if (!canDrawHighlights(evidence)) return [];
  const rects: OverlayRect[] = [];
  for (const region of usableRegions(evidence)) {
    if (region.page !== pageNumber) continue;
    const rect = regionToOverlayRect(region, pageView, viewport);
    if (rect) rects.push(rect);
  }
  return rects;
}

export type EvidenceView = {
  page: number | null;
  pages: number[];
  canHighlight: boolean;
  regionsByPage: Record<number, EvidenceRegion[]>;
  snippet: string;
};

/** Every 1-based page in the PDF. Citation focus is not a render cap. */
export function pagesForPdfViewer(numPages: number): number[] {
  if (!Number.isInteger(numPages) || numPages < 1) return [];
  return Array.from({ length: numPages }, (_, index) => index + 1);
}

function firstValidPage(...values: Array<number | null | undefined>): number | null {
  for (const value of values) {
    if (isValidPage(value)) return value;
  }
  return null;
}

export function resolveEvidenceView(input: {
  citationPage: number | null | undefined;
  evidence: ChunkEvidence | null;
  citationSnippet?: string | null;
  citationQuote?: string | null;
}): EvidenceView {
  const { citationPage, evidence } = input;
  const highlightRegions = usableRegions(evidence);
  const canHighlight = highlightRegions.length > 0;
  const quoteFailed = requestedQuote(evidence) && !canHighlight;
  const preferQuote =
    quoteFailed ||
    (!evidence && Boolean(input.citationQuote && input.citationQuote.trim()));
  const snippet = (
    preferQuote
      ? evidence?.quote ||
        input.citationQuote ||
        evidence?.snippet ||
        input.citationSnippet ||
        ""
      : evidence?.snippet || input.citationSnippet || ""
  ).trim();

  const regionsByPage: Record<number, EvidenceRegion[]> = {};
  if (canHighlight) {
    for (const region of highlightRegions) {
      const list = regionsByPage[region.page] || [];
      list.push(region);
      regionsByPage[region.page] = list;
    }
  }

  const pages = canHighlight
    ? Object.keys(regionsByPage)
        .map(Number)
        .sort((a, b) => a - b)
    : (() => {
        const fallback = firstValidPage(evidence?.page_start, citationPage);
        return fallback ? [fallback] : [];
      })();

  return {
    page: pages[0] ?? firstValidPage(evidence?.page_start, citationPage),
    pages,
    canHighlight,
    regionsByPage,
    snippet,
  };
}

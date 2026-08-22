import type { Citation } from "@/types/citation";

export type EvidencePresentationStatus =
  | "precise"
  | "page_only"
  | "passage_only"
  | "unavailable"
  | "invalid_quote"
  | "missing_metadata";

export function evidencePresentationStatus(
  citation: Pick<
    Citation,
    | "quoteHighlightAvailable"
    | "quoteMappingStatus"
    | "uiStatus"
    | "pageNumber"
    | "contentType"
  >
): EvidencePresentationStatus {
  const ui = citation.uiStatus?.toLowerCase();
  if (ui === "citation_dropped" || ui === "missing_metadata") {
    return "missing_metadata";
  }
  if (ui?.startsWith("invalid_")) {
    return "invalid_quote";
  }
  const status = (citation.quoteMappingStatus || "").toLowerCase();
  if (citation.quoteHighlightAvailable) {
    return "precise";
  }
  if (status === "not_in_chunk" || status === "rejected") {
    return "invalid_quote";
  }
  if (
    status === "fallback_chunk" ||
    status === "unresolved" ||
    status === "no_layout" ||
    status === "not_on_page"
  ) {
    return citation.pageNumber ? "page_only" : "passage_only";
  }
  if (status === "no_evidence_data") {
    return citation.pageNumber ? "page_only" : "unavailable";
  }
  const contentType = (citation.contentType || "").toLowerCase();
  if (contentType === "figure_caption") {
    return "passage_only";
  }
  if (contentType === "scanned_or_image" || contentType === "scanned_ocr") {
    return citation.pageNumber ? "page_only" : "unavailable";
  }
  if (citation.pageNumber) {
    return "page_only";
  }
  if (status && status !== "none") {
    return "passage_only";
  }
  return "unavailable";
}

export function evidenceStatusLabel(status: EvidencePresentationStatus): string {
  switch (status) {
    case "precise":
      return "Precise highlight";
    case "page_only":
      return "Page shown — exact text not located";
    case "passage_only":
      return "Passage only — no PDF highlight";
    case "invalid_quote":
      return "Quote could not be verified";
    case "missing_metadata":
      return "Citation metadata incomplete";
    default:
      return "Highlight unavailable";
  }
}

export function contentTypeDetail(contentType: string | null | undefined): string | null {
  const kind = (contentType || "").toLowerCase();
  if (kind === "figure_caption") {
    return "This evidence refers to a figure. Text highlighting may be limited to the caption.";
  }
  if (kind === "table") {
    return "Table content may not map to a single continuous text highlight.";
  }
  if (kind === "scanned_or_image" || kind === "scanned_ocr") {
    return "This page has little or no native text layer. Precise text highlighting is not available.";
  }
  if (kind === "low_text_layout") {
    return "PDF layout data is incomplete for this passage.";
  }
  return null;
}

export function evidenceStatusDetail(
  citation: Pick<Citation, "quoteMappingStatus" | "uiStatus">
): string | null {
  const status = (citation.quoteMappingStatus || "").toLowerCase();
  if (status === "fallback_chunk") {
    return "We found supporting text but could not draw a precise box on the PDF.";
  }
  if (status === "unresolved") {
    return "The claim could not be mapped to a reliable PDF text region.";
  }
  if (status === "not_in_chunk") {
    return "The quoted text does not appear in the retrieved passage.";
  }
  if (status === "no_evidence_data") {
    return "This document lacks stored layout data for precise highlights.";
  }
  if (citation.uiStatus === "citation_dropped") {
    return "The answer references this source but citation details were not attached.";
  }
  return null;
}

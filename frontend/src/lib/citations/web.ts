import type { Citation } from "@/types/citation";
import { usedCitationsWithFallback } from "./markers";

export function isWebCitation(
  citation: Pick<Citation, "kind" | "url" | "contentType"> | null | undefined
): boolean {
  if (!citation) return false;
  if (citation.kind === "web") return true;
  if ((citation.contentType || "").toLowerCase() === "web") return true;
  return Boolean(citation.url);
}

export function isPreviewWebCitation(
  citation: Pick<Citation, "preview" | "provider"> | null | undefined
): boolean {
  if (!citation) return false;
  if (citation.preview === true) return true;
  return (citation.provider || "").toLowerCase() === "mock";
}

export function displayNumberFromWebId(
  evidenceId: string | null | undefined
): number | null {
  if (!evidenceId) return null;
  const match = /^W([1-9]\d*)$/i.exec(evidenceId.trim());
  if (!match) return null;
  return Number.parseInt(match[1], 10);
}

export function stripWebMarkers(content: string | null | undefined): string {
  return (content || "")
    .replace(/\s*\[W[1-9]\d*\]/gi, "")
    .replace(/ {2,}/g, " ")
    .trim();
}

export function hostnameFromUrl(url: string | null | undefined): string {
  if (!url) return "";
  try {
    const host = new URL(url).hostname.toLowerCase();
    return host.startsWith("www.") ? host.slice(4) : host;
  } catch {
    return "";
  }
}

export function webSourceBadge(
  citation: Pick<Citation, "preview" | "provider" | "tier" | "domain" | "url">
): string {
  if (isPreviewWebCitation(citation)) return "Preview source";
  const domain = citation.domain || hostnameFromUrl(citation.url) || "web source";
  const tier = (citation.tier || "").toLowerCase();
  if (tier === "t1") return `${domain} · Official`;
  if (tier === "t2") return `${domain} · Reference`;
  return domain;
}

const DOCUMENT_REFUSAL_RE =
  /no relevant information found in the document|couldn['’]t find.{0,80}(provided )?(document|context)|could not find.{0,80}(provided )?(document|context)|not in the provided document|not enough information|does not extend|do not extend|does not cover this|do not cover this|not covered in the (provided )?document/i;

export function isDocumentRefusal(content: string | null | undefined): boolean {
  return DOCUMENT_REFUSAL_RE.test((content || "").trim());
}

export function mergeAnswerCitations(
  existing: Citation[] | undefined,
  incoming: Citation[] | undefined
): Citation[] {
  const out: Citation[] = [];
  const seen = new Set<string>();
  const push = (item: Citation) => {
    const key = isWebCitation(item)
      ? `web:${item.url || item.evidenceId || item.id}`
      : `pdf:${item.chunk_id || item.evidenceId || item.id}`;
    if (seen.has(key)) return;
    seen.add(key);
    out.push(item);
  };
  for (const item of existing || []) push(item);
  for (const item of incoming || []) push(item);
  return out;
}

/** PDF citations the answer used, plus every web card for this turn. */
export function listedAnswerSources(
  citations: Citation[] | undefined,
  content: string
): Citation[] {
  const items = citations || [];
  const web = items.filter(isWebCitation);
  const pdf = items.filter((item) => !isWebCitation(item));
  return [...usedCitationsWithFallback(pdf, content), ...web];
}

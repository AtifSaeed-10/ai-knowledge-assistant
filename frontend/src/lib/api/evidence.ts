import { API_CONFIG } from "./client";
import type { ChunkEvidence, EvidenceRegion } from "@/lib/pdf/coords";

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function parseRegion(value: unknown): EvidenceRegion | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  const page = asNumber(item.page);
  const x0 = asNumber(item.x0);
  const y0 = asNumber(item.y0);
  const x1 = asNumber(item.x1);
  const y1 = asNumber(item.y1);
  if (
    page === null ||
    x0 === null ||
    y0 === null ||
    x1 === null ||
    y1 === null ||
    typeof item.coord_space !== "string"
  ) {
    return null;
  }
  return { page, x0, y0, x1, y1, coord_space: item.coord_space };
}

function parseEvidence(payload: unknown): ChunkEvidence | null {
  if (!payload || typeof payload !== "object") return null;
  const item = payload as Record<string, unknown>;
  if (typeof item.chunk_id !== "string" || typeof item.document_id !== "string") {
    return null;
  }
  const pageStart = asNumber(item.page_start);
  const pageEnd = asNumber(item.page_end);
  if (pageStart === null || pageEnd === null) return null;
  const regions = Array.isArray(item.regions)
    ? item.regions.map(parseRegion).filter((region): region is EvidenceRegion => region !== null)
    : [];
  const quoteRegions = Array.isArray(item.quote_regions)
    ? item.quote_regions
        .map(parseRegion)
        .filter((region): region is EvidenceRegion => region !== null)
    : [];
  return {
    chunk_id: item.chunk_id,
    document_id: item.document_id,
    page_start: pageStart,
    page_end: pageEnd,
    snippet: typeof item.snippet === "string" ? item.snippet : "",
    highlight_available: item.highlight_available === true,
    regions,
    quote: typeof item.quote === "string" ? item.quote : null,
    quote_highlight_available: item.quote_highlight_available === true,
    quote_regions: quoteRegions,
    quote_mapping_status:
      typeof item.quote_mapping_status === "string" ? item.quote_mapping_status : null,
  };
}

export async function fetchChunkEvidence(
  documentId: string,
  chunkId: string,
  options?: { quote?: string | null; claim?: string | null; signal?: AbortSignal }
): Promise<ChunkEvidence | null> {
  if (API_CONFIG.useMock) return null;

  const params = new URLSearchParams();
  const quote = options?.quote?.trim();
  const claim = options?.claim?.trim();
  if (quote) params.set("quote", quote);
  if (claim) params.set("claim", claim);
  const query = params.toString();
  const response = await fetch(
    `${API_CONFIG.baseUrl}/documents/${encodeURIComponent(documentId)}/chunks/${encodeURIComponent(chunkId)}/evidence${query ? `?${query}` : ""}`,
    { signal: options?.signal }
  );

  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Could not load evidence (${response.status}).`);
  }

  return parseEvidence(await response.json());
}

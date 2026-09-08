/**
 * Decide which PDF a question should search — frontend only.
 *
 * Retrieval and the API stay unchanged. This only picks document_ids
 * (or asks the reader to pick) so "summary of this outline" does not
 * silently answer from the wrong file in All documents mode.
 */

export const SEARCH_ALL_SCOPE_ID = "__all__";

export type ScopeDocument = {
  id: string;
  name: string;
  status?: string;
};

export type ScopeChoice = {
  id: string;
  name: string;
};

export type ScopeDecision =
  | { kind: "ready"; documentIds: string[]; reason: string }
  | { kind: "clarify"; candidates: ScopeChoice[]; reason: string };

const STOP_WORDS = new Set([
  "a",
  "an",
  "and",
  "are",
  "about",
  "can",
  "content",
  "describe",
  "do",
  "explain",
  "findings",
  "for",
  "from",
  "give",
  "hai",
  "how",
  "in",
  "is",
  "just",
  "ka",
  "ke",
  "key",
  "ki",
  "kya",
  "list",
  "me",
  "mentioned",
  "my",
  "of",
  "on",
  "or",
  "overview",
  "please",
  "points",
  "samjhao",
  "summarise",
  "summarize",
  "summary",
  "tell",
  "the",
  "these",
  "this",
  "those",
  "to",
  "what",
  "when",
  "where",
  "which",
  "who",
  "why",
  "ye",
  "yeh",
  "you",
  "your",
]);

const DOC_TYPE_WORDS = new Set([
  "assignment",
  "book",
  "course",
  "document",
  "documents",
  "file",
  "files",
  "handbook",
  "lecture",
  "notes",
  "outline",
  "paper",
  "pdf",
  "pdfs",
  "syllabus",
]);

const MULTI_DOC_RE =
  /\b(compar(?:e|ison|ing)|versus|\bvs\.?\b|both|all (?:the )?(?:documents|pdfs|files)|every (?:document|pdf|file)|across (?:the )?(?:documents|pdfs|files)|search (?:all|everything)|entire (?:library|workspace))\b/i;

const DEICTIC_RE =
  /\b(?:this|that)\s+(?:pdf|document|file|one|outline|syllabus|handbook|course|paper|book)\b|\bthe\s+(?:pdf|document|file|outline|syllabus|handbook)(?!\s+of\b)\b|\b(?:summar(?:y|ize|ise)|explain|describe|overview).{0,24}\bthis\b|\b(?:is|ye|yeh)\s+(?:(?:wale?|wali)\s+)?(?:pdf|outline|document|file|course)\b|\b(?:iska|is ka)\b/i;

function readyDocuments(documents: ScopeDocument[]): ScopeDocument[] {
  return documents.filter((doc) => !doc.status || doc.status === "ready");
}

function findReady(
  documents: ScopeDocument[],
  id: string | null | undefined
): ScopeDocument | null {
  if (!id) return null;
  return documents.find((doc) => doc.id === id) ?? null;
}

export function normalizeDocumentName(name: string): string {
  return (name || "")
    .toLowerCase()
    .replace(/\.[a-z0-9]+$/, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

export function questionTokens(question: string): string[] {
  return ((question || "").toLowerCase().match(/[a-z0-9]+/g) ?? []).filter(Boolean);
}

export function distinctiveQuestionTokens(question: string): string[] {
  return questionTokens(question).filter(
    (token) => !STOP_WORDS.has(token) && !DOC_TYPE_WORDS.has(token) && token.length > 1
  );
}

export function isMultiDocumentQuestion(question: string): boolean {
  return MULTI_DOC_RE.test(question || "");
}

export function isDeicticDocumentQuestion(question: string): boolean {
  return DEICTIC_RE.test(question || "");
}

export function isGenericWholeDocumentQuestion(question: string): boolean {
  const text = (question || "").trim();
  if (!text) return false;
  return distinctiveQuestionTokens(text).length === 0;
}

export function matchDocumentByName(
  question: string,
  documents: ScopeDocument[],
  tokens = distinctiveQuestionTokens(question)
): ScopeDocument | null {
  const needles = tokens.length
    ? tokens
    : questionTokens(question).filter((token) => !STOP_WORDS.has(token));
  if (needles.length === 0) return null;

  let best: ScopeDocument | null = null;
  let bestScore = 0;
  let tied = false;

  for (const doc of documents) {
    const name = normalizeDocumentName(doc.name);
    if (!name) continue;
    const score = needles.reduce((sum, token) => (name.includes(token) ? sum + 1 : sum), 0);
    if (score > bestScore) {
      best = doc;
      bestScore = score;
      tied = false;
    } else if (score > 0 && score === bestScore) {
      tied = true;
    }
  }

  if (!best || bestScore === 0 || tied) return null;
  return best;
}

export function lastCitedDocumentId(
  messages: Array<{ citations?: Array<{ documentId?: string | null }> | undefined }>
): string | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const citations = messages[index]?.citations;
    if (!citations?.length) continue;
    const ids = [
      ...new Set(
        citations
          .map((item) => item.documentId)
          .filter((id): id is string => Boolean(id))
      ),
    ];
    if (ids.length === 1) return ids[0];
    if (ids.length > 1) return null;
  }
  return null;
}

function asReady(documentIds: string[], reason: string): ScopeDecision {
  return { kind: "ready", documentIds, reason };
}

export function resolveDocumentScope(options: {
  question: string;
  mode: "normal" | "super_focused";
  documents: ScopeDocument[];
  selectedDocumentId?: string | null;
  previewDocumentId?: string | null;
  lastCitedDocumentId?: string | null;
  pinnedDocumentId?: string | null;
}): ScopeDecision {
  const question = (options.question || "").trim();
  const ready = readyDocuments(options.documents);
  const readyIds = ready.map((doc) => doc.id);
  const selected = findReady(ready, options.selectedDocumentId);
  const preview = findReady(ready, options.previewDocumentId);
  const pinned = findReady(ready, options.pinnedDocumentId);
  const lastCited = findReady(ready, options.lastCitedDocumentId);
  const deictic = isDeicticDocumentQuestion(question);
  const generic = isGenericWholeDocumentQuestion(question);
  const pointing = deictic || generic;

  if (ready.length === 0) {
    return asReady([], "none-ready");
  }

  if (options.mode === "super_focused") {
    return selected
      ? asReady([selected.id], "focused")
      : asReady([], "focused-missing");
  }

  if (ready.length === 1) {
    return asReady([ready[0].id], "single");
  }

  if (isMultiDocumentQuestion(question)) {
    return asReady(readyIds, "multi");
  }

  const distinctive = distinctiveQuestionTokens(question);
  const named = matchDocumentByName(
    question,
    ready,
    distinctive.length > 0 ? distinctive : pointing ? questionTokens(question).filter((token) => !STOP_WORDS.has(token)) : []
  );
  if (named) {
    return asReady([named.id], "filename");
  }

  if (pointing && selected) {
    return asReady([selected.id], "selected");
  }

  if (pinned) {
    return asReady([pinned.id], "pinned");
  }

  if (pointing && preview) {
    return asReady([preview.id], "preview");
  }

  if (pointing && lastCited) {
    return asReady([lastCited.id], "last-cited");
  }

  if (pointing) {
    return {
      kind: "clarify",
      candidates: ready.map((doc) => ({ id: doc.id, name: doc.name })),
      reason: "ambiguous",
    };
  }

  return asReady(readyIds, "all");
}

export function shouldRememberScopePin(decision: ScopeDecision): boolean {
  return (
    decision.kind === "ready" &&
    decision.documentIds.length === 1 &&
    decision.reason !== "multi" &&
    decision.reason !== "all"
  );
}

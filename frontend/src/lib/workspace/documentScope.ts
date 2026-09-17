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
  /\b(compar(?:e|ison|ing)|versus|\bvs\.?\b|both|all (?:the )?(?:documents|pdfs|files)|every (?:document|pdf|file)|across (?:the )?(?:documents|pdfs|files)|search (?:all|everything)|entire (?:library|workspace)|and also|as well as)\b/i;

const QUESTION_JOIN_RE =
  /\s*(?:,|;|\band)\s+(?=(?:what|who|how|why|when|where|which)\b)/i;

const DEICTIC_RE =
  /\b(?:this|that)\s+(?:pdf|document|file|one|outline|syllabus|handbook|course|paper|book)\b|\bthe\s+(?:pdf|document|file|outline|syllabus|handbook)(?!\s+of\b)\b|\b(?:summar(?:y|ize|ise)|explain|describe|overview).{0,24}\bthis\b|\b(?:is|ye|yeh)\s+(?:(?:wale?|wali)\s+)?(?:pdf|outline|document|file|course)\b|\b(?:iska|is ka)\b/i;

/**
 * "Make it easier", "why?", "give an example" carry no topic of their own —
 * they continue whatever the last answer was about, so they must stay on the
 * PDF that answer came from instead of re-searching the whole library.
 */
const FOLLOW_UP_RE =
  /^\s*(?:and\s+|so\s+|but\s+|ok(?:ay)?[, ]+|please\s+)?(?:can you|could you|now)?\s*(?:make|explain|say|put|write|break)?\s*(?:it|this|that|them)?\s*(?:a bit|a little|bit)?\s*(?:more\s+)?(?:easier|easy|simpler|simple|simply|shorter|briefer|clearer|clear|detailed)\b|^\s*(?:why|how|and then|what about|another one|more)\s*\??\s*$|\b(?:previous|last|above|earlier)\s+(?:answer|response|reply|explanation)\b|^\s*(?:eli5|tldr|in short|elaborate|go deeper|expand(?:\s+on\s+(?:it|this|that))?|continue|more detail(?:s)?|examples?)\s*\.?\s*$/i;

/**
 * Questions about the document itself rather than its subject matter.
 * "Who is the author" names no topic, so it cannot be answered until the
 * reader says which PDF they mean.
 */
const DOCUMENT_ATTRIBUTE_RE =
  /\b(?:auth(?:or|ors)|writer|written by|wrote (?:this|it)|publisher|published by|isbn|edition|copyright|title of (?:this|the)|what(?:'s| is) (?:this|it) about)\b/i;

const ATTRIBUTE_ONLY_TOKENS = new Set([
  "about",
  "author",
  "authors",
  "copyright",
  "edition",
  "isbn",
  "name",
  "publisher",
  "published",
  "title",
  "wrote",
  "writer",
  "written",
]);

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
  const text = question || "";
  if (MULTI_DOC_RE.test(text)) return true;

  const stripped = text
    .replace(/^\s*search\s+all(?:\s+(?:the\s+)?(?:documents?|pdfs?|files?))?\s*[:\-–]?\s*/i, "")
    .trim();
  const strong = stripped.split(
    /\s+(?:and\s+also|and\s+tell\s+me(?:\s+about)?|as\s+well\s+as)\s+/i
  );
  if (strong.length >= 2) return true;

  const questionParts = stripped
    .split(QUESTION_JOIN_RE)
    .map((part) => part.trim())
    .filter(Boolean);
  if (
    questionParts.length >= 2 &&
    questionParts.every((part) => distinctiveQuestionTokens(part).length >= 1)
  ) {
    return true;
  }

  const weak = stripped.split(/\s+and\s+/i);
  if (weak.length === 2) {
    return (
      distinctiveQuestionTokens(weak[0]).length >= 2 &&
      distinctiveQuestionTokens(weak[1]).length >= 2
    );
  }
  return false;
}

export function isDeicticDocumentQuestion(question: string): boolean {
  return DEICTIC_RE.test(question || "");
}

export function isGenericWholeDocumentQuestion(question: string): boolean {
  const text = (question || "").trim();
  if (!text) return false;

  const distinctive = distinctiveQuestionTokens(text);
  if (distinctive.length === 0) return true;

  // "Who is the author" is about the file, not about a topic inside it.
  return (
    DOCUMENT_ATTRIBUTE_RE.test(text) &&
    distinctive.every((token) => ATTRIBUTE_ONLY_TOKENS.has(token))
  );
}

export function isConversationalFollowUp(question: string): boolean {
  const text = (question || "").trim();
  if (!text) return false;
  return FOLLOW_UP_RE.test(text);
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
  const followUp = isConversationalFollowUp(question);
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

  // A follow-up has no topic of its own, so it belongs to the PDF that the
  // previous answer cited — before any filename guessing.
  if (followUp && lastCited) {
    return asReady([lastCited.id], "last-cited");
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
    decision.reason !== "all" &&
    decision.reason !== "cited"
  );
}

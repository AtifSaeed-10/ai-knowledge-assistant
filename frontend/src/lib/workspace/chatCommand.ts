/**
 * Decide whether a chat turn is a PDF control, not a question.
 *
 * Questions still go to the existing RAG path unchanged. This only
 * recognizes high-confidence navigation so "open page 50" does not
 * search the document for the number 50.
 */

export type ChatCommand =
  | { kind: "question" }
  | { kind: "social"; reply: SocialReply }
  | { kind: "open_panel" }
  | { kind: "close_panel" }
  | { kind: "goto_page"; page: number }
  | { kind: "goto_first" }
  | { kind: "goto_last" }
  | { kind: "goto_next" }
  | { kind: "goto_prev" }
  | { kind: "goto_heading"; query: string };

const QUESTION_RE =
  /\b(what|what's|whats|why|how|explain|summar(?:y|ize|ise)|tell me|describe|list|compare|difference|meaning|content of|said|says|about)\b/i;

/**
 * Pleasantries are not questions about a PDF. Answering them locally keeps
 * "hi" from spending a quota credit on a retrieval that has nothing to find.
 */
export type SocialReply = "greeting" | "thanks" | "farewell";

const SOCIAL_PATTERNS: Array<[SocialReply, RegExp]> = [
  [
    "greeting",
    /^(?:hi+|hey+|hello+|heyy+|yo|hii+|helo+|hallo|salam|as-?salam(?:u|o)?\s*alaikum|assalamualaikum|namaste|good\s+(?:morning|afternoon|evening|day))(?:\s+(?:there|docusage|bro|dude|friend))?[\s!.,?]*$/i,
  ],
  [
    "thanks",
    /^(?:thanks?|thank\s*(?:you|u)|thx|tysm|ty|shukriya|appreciate\s+it|got\s+it|nice|great|perfect|awesome|cool)(?:\s+(?:a\s+lot|so\s+much|man|bro|docusage))?[\s!.,?]*$/i,
  ],
  [
    "farewell",
    /^(?:bye+|goodbye|good\s*night|see\s*(?:you|ya)(?:\s+later)?|take\s+care|khuda\s*hafiz|allah\s*hafiz)[\s!.,?]*$/i,
  ],
];

const NAV_RE =
  /\b(open|show|display|go\s+to|goto|jump(?:\s+to)?|take me(?:\s+to)?|scroll(?:\s+to)?|bring up|navigate(?:\s+to)?)\b/i;

const SOFT_NAV_RE = /\b(view|turn(?:\s+to)?|flip(?:\s+to)?)\b/i;

const PAGE_RE =
  /\b(?:the\s+)?(?:pages?|pp?\.?|pg\.?)\s*(?:number|no\.?|#)?\s*([0-9]{1,4}|[a-z][a-z- ]{0,24})\b/i;

const HEADING_RE =
  /\b((?:week|lecture|session|module|unit|chapter|lesson|section|topic)s?)\s*(?:number|no\.?|#)?\s*([0-9]{1,3}|[ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b/i;

const CLOSE_PANEL_RE =
  /^(please\s+)?(hide|close)\s+(the\s+)?(pdf|preview|document|file)(\s+preview)?\s*[.!]?\s*$/i;

const OPEN_PANEL_RE =
  /^(please\s+)?(show|open|display)\s+(the\s+)?(pdf|preview|document|file)(\s+preview)?\s*[.!]?\s*$/i;

const FIRST_PAGE_RE =
  /\b(first page|beginning|start of (?:the )?(?:pdf|document|file)|page one)\b/i;

const LAST_PAGE_RE =
  /\b(last page|final page|end of (?:the )?(?:pdf|document|file))\b/i;

const NEXT_PAGE_RE =
  /^(please\s+)?((?:the\s+)?(?:next|following) page|go forward(?: a page)?)\s*[.!]?\s*$/i;

const PREV_PAGE_RE =
  /^(please\s+)?((?:the\s+)?(?:previous|prev|prior) page|go back(?: a page)?|page before)\s*[.!]?\s*$/i;

const REL_NEXT_RE = /\b(?:the\s+)?(?:next|following)\s+page\b/i;
const REL_PREV_RE = /\b(?:the\s+)?(?:previous|prev|prior)\s+page\b/i;
const LOOSE_END_RE = /\b(?:the\s+)?end\b/i;

const FILLER_RE =
  /\b(please|kindly|just|can you|could you|would you|can|could|would|you|the|a|an|to|me|my|this|that|of|in|on|for)\b/gi;

const WORD_NUMBERS: Record<string, number> = {
  zero: 0,
  one: 1,
  two: 2,
  three: 3,
  four: 4,
  five: 5,
  six: 6,
  seven: 7,
  eight: 8,
  nine: 9,
  ten: 10,
  eleven: 11,
  twelve: 12,
  thirteen: 13,
  fourteen: 14,
  fifteen: 15,
  sixteen: 16,
  seventeen: 17,
  eighteen: 18,
  nineteen: 19,
  twenty: 20,
  thirty: 30,
  forty: 40,
  fifty: 50,
  sixty: 60,
  seventy: 70,
  eighty: 80,
  ninety: 90,
};

const ROMAN_NUMBERS: Record<string, number> = {
  i: 1,
  ii: 2,
  iii: 3,
  iv: 4,
  v: 5,
  vi: 6,
  vii: 7,
  viii: 8,
  ix: 9,
  x: 10,
  xi: 11,
  xii: 12,
};

function parseNumberToken(raw: string): number | null {
  const text = raw.trim().toLowerCase().replace(/-/g, " ");
  if (/^\d{1,4}$/.test(text)) {
    const value = Number(text);
    return value >= 0 ? value : null;
  }
  if (WORD_NUMBERS[text] !== undefined) return WORD_NUMBERS[text];
  if (ROMAN_NUMBERS[text] !== undefined) return ROMAN_NUMBERS[text];
  const parts = text.split(/\s+/).filter(Boolean);
  if (parts.length === 2 && WORD_NUMBERS[parts[0]] && WORD_NUMBERS[parts[1]] !== undefined) {
    const tens = WORD_NUMBERS[parts[0]];
    const ones = WORD_NUMBERS[parts[1]];
    if (tens >= 20 && tens % 10 === 0 && ones < 10) return tens + ones;
  }
  return null;
}

function extractPage(text: string): number | null {
  const match = PAGE_RE.exec(text);
  if (!match) return null;
  return parseNumberToken(match[1]);
}

function extractHeading(text: string): string | null {
  const match = HEADING_RE.exec(text);
  if (!match) return null;
  const label = match[1].toLowerCase().replace(/s$/, "");
  const number = parseNumberToken(match[2]) ?? match[2].toLowerCase();
  return `${label} ${number}`;
}

function leftoverAfter(text: string, extra: RegExp[]): string {
  let next = text;
  for (const pattern of extra) {
    next = next.replace(pattern, " ");
  }
  return next
    .replace(NAV_RE, " ")
    .replace(SOFT_NAV_RE, " ")
    .replace(FILLER_RE, " ")
    .replace(/[^a-z0-9]+/gi, "")
    .toLowerCase();
}

function isBarePage(text: string, page: number): boolean {
  return page >= 0 && leftoverAfter(text, [PAGE_RE]).length === 0;
}

function isSoftPageNav(text: string): boolean {
  return leftoverAfter(text, [PAGE_RE]).length === 0;
}

function isSoftHeadingNav(text: string): boolean {
  return SOFT_NAV_RE.test(text) && leftoverAfter(text, [HEADING_RE]).length === 0;
}

export function detectSocialReply(raw: string): SocialReply | null {
  const text = (raw || "").trim();
  // Anything long enough to carry a real request is not small talk.
  if (!text || text.length > 40) return null;

  for (const [reply, pattern] of SOCIAL_PATTERNS) {
    if (pattern.test(text)) return reply;
  }
  return null;
}

export function classifyChatCommand(raw: string): ChatCommand {
  const text = (raw || "").trim();
  if (!text) return { kind: "question" };

  const social = detectSocialReply(text);
  if (social) return { kind: "social", reply: social };

  if (CLOSE_PANEL_RE.test(text)) return { kind: "close_panel" };
  if (OPEN_PANEL_RE.test(text)) return { kind: "open_panel" };
  if (NEXT_PAGE_RE.test(text)) return { kind: "goto_next" };
  if (PREV_PAGE_RE.test(text)) return { kind: "goto_prev" };

  if (QUESTION_RE.test(text)) return { kind: "question" };

  const navigating = NAV_RE.test(text);
  const page = extractPage(text);
  const heading = extractHeading(text);

  if ((navigating || SOFT_NAV_RE.test(text)) && REL_NEXT_RE.test(text) && page === null) {
    return { kind: "goto_next" };
  }
  if ((navigating || SOFT_NAV_RE.test(text)) && REL_PREV_RE.test(text) && page === null) {
    return { kind: "goto_prev" };
  }

  if (navigating && FIRST_PAGE_RE.test(text) && page === null) {
    return { kind: "goto_first" };
  }
  if (navigating && LAST_PAGE_RE.test(text) && page === null) {
    return { kind: "goto_last" };
  }
  if (FIRST_PAGE_RE.test(text) && isBarePage(text.replace(FIRST_PAGE_RE, "page 1"), 1) && !heading) {
    return { kind: "goto_first" };
  }
  if (LAST_PAGE_RE.test(text) && page === null && !heading && leftoverAfter(text, [LAST_PAGE_RE]).length === 0) {
    return { kind: "goto_last" };
  }
  if (navigating && page === null && !heading && LOOSE_END_RE.test(text) && leftoverAfter(text, [LOOSE_END_RE]).length === 0) {
    return { kind: "goto_last" };
  }

  if (page !== null && (navigating || isBarePage(text, page) || isSoftPageNav(text))) {
    return { kind: "goto_page", page };
  }

  if (heading && (navigating || isSoftHeadingNav(text))) {
    return { kind: "goto_heading", query: heading };
  }

  return { kind: "question" };
}

export function isWorkspaceCommand(text: string): boolean {
  const kind = classifyChatCommand(text).kind;
  return kind !== "question" && kind !== "social";
}

/** Sendable without a ready document, but not a PDF control either. */
export function isSocialMessage(text: string): boolean {
  return classifyChatCommand(text).kind === "social";
}

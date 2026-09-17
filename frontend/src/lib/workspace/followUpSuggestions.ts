/**
 * Follow-up chips from the answer that was just shown — not a fixed script.
 * Questions stay specific so a click can retrieve the same documents.
 */

const STOP = new Set([
  "a",
  "an",
  "and",
  "as",
  "at",
  "by",
  "for",
  "from",
  "in",
  "into",
  "is",
  "it",
  "its",
  "of",
  "on",
  "or",
  "the",
  "this",
  "that",
  "to",
  "with",
  "was",
  "were",
  "who",
  "what",
  "how",
  "why",
]);

const GENERIC_QUESTION_RE =
  /^(what happens after that|explain that in simpler words|what are the key points)\??$/i;

type Section = { heading: string | null; body: string };

function stripCitations(text: string): string {
  return (text || "")
    .replace(/\[E[1-9]\d*(?::[^\]]*)?\]/gi, " ")
    .replace(/\[(\d+)\]/g, " ")
    .replace(/(?<=\w)\s+\d{1,2}(?=[.?!](?:\s|$))/g, "")
    .replace(/[“”]/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

function titleCase(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => {
      if (/^[A-Z0-9]{2,}$/.test(word)) return word;
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(" ");
}

function normalizeQuestion(value: string): string {
  return value.toLowerCase().replace(/[?!.'’]+/g, "").replace(/\s+/g, " ").trim();
}

function splitSections(answer: string): Section[] {
  const lines = (answer || "").split(/\n+/);
  const sections: Section[] = [];
  let heading: string | null = null;
  let body: string[] = [];

  const flush = () => {
    const text = body.join("\n").trim();
    if (!heading && !text) return;
    sections.push({ heading, body: text });
    heading = null;
    body = [];
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    const marked = line.match(/^#{1,3}\s+(.+)$/);
    const shortTitle =
      !marked &&
      line.length <= 48 &&
      !/[.?!]$/.test(line) &&
      line.split(/\s+/).length <= 6 &&
      /^[A-Z0-9]/.test(line);

    if (marked || shortTitle) {
      flush();
      heading = (marked ? marked[1] : line).replace(/[*_]/g, "").trim();
      continue;
    }
    body.push(line);
  }
  flush();
  return sections.length > 0 ? sections : [{ heading: null, body: answer || "" }];
}

function contrastPairs(text: string): Array<[string, string]> {
  const pairs: Array<[string, string]> = [];
  const clean = stripCitations(text);
  const andPair =
    /\b([A-Za-z][A-Za-z-]{2,}(?:\s+[A-Za-z][A-Za-z-]{2,})?)\s+and\s+([A-Za-z][A-Za-z-]{2,}(?:\s+[A-Za-z][A-Za-z-]{2,})?)\b/g;
  let match: RegExpExecArray | null;
  while ((match = andPair.exec(clean))) {
    const left = match[1];
    const right = match[2];
    const leftTok = left.toLowerCase();
    const rightTok = right.toLowerCase();
    if (STOP.has(leftTok.split(" ")[0] || "") || STOP.has(rightTok.split(" ")[0] || "")) {
      continue;
    }
    if (leftTok === rightTok) continue;
    const around = clean.slice(
      Math.max(0, match.index - 48),
      match.index + match[0].length + 48
    );
    const pairLooksTechnical =
      /\b(classification|regression|supervised|unsupervised)\b/i.test(`${left} ${right}`);
    const nearbyCue =
      /\b(tasks?|types?|methods?|approaches?|unlike|versus|compared)\b/i.test(around);
    if (!pairLooksTechnical && !nearbyCue) continue;
    pairs.push([left, right]);
  }
  return pairs;
}

function unlikeTerms(text: string): string[] {
  const found: string[] = [];
  const re = /\bunlike\s+([a-z][a-z]+(?:\s+[a-z][a-z]+){0,2})/gi;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text))) {
    found.push(match[1].trim());
  }
  return found;
}

function orgs(text: string): string[] {
  const found = text.match(/\b[A-Z]{2,6}\b/g) || [];
  return [...new Set(found.filter((item) => item !== "PDF" && item !== "AI"))];
}

function isDefinition(text: string): boolean {
  return /\b(is a|is an|is the|paradigm|algorithm|method|defined as)\b/i.test(text);
}

function looksLikePerson(heading: string): boolean {
  const words = heading.trim().split(/\s+/);
  return (
    words.length >= 2 &&
    words.length <= 4 &&
    words.every((word) => /^[A-Z][a-z]+$/.test(word) || /^[A-Z]{2,}$/.test(word))
  );
}

function questionsForSection(section: Section, original: string): string[] {
  const heading = section.heading?.replace(/[*_]/g, "").trim() || "";
  const body = section.body;
  const combined = `${heading}\n${body}`;
  const questions: string[] = [];
  const originalKey = normalizeQuestion(original);

  for (const [left, right] of contrastPairs(combined)) {
    questions.push(
      `What is the difference between ${titleCase(left)} and ${titleCase(right)}?`
    );
  }

  if (heading && isDefinition(body)) {
    const unlike = unlikeTerms(body);
    if (unlike[0]) {
      questions.push(
        `How does ${titleCase(heading)} differ from ${titleCase(unlike[0])}?`
      );
    }
    questions.push(`How does ${titleCase(heading)} work?`);
  }

  if (heading && looksLikePerson(heading)) {
    const org = orgs(body)[0];
    if (org) {
      questions.push(`What was ${heading}'s role in the ${org}?`);
    } else {
      questions.push(`What else does the document say about ${heading}?`);
    }
  } else if (heading && !isDefinition(body)) {
    questions.push(`What else does the document say about ${titleCase(heading)}?`);
  }

  return questions.filter((item) => {
    const key = normalizeQuestion(item);
    if (!key || key === originalKey) return false;
    if (GENERIC_QUESTION_RE.test(item)) return false;
    if (item.length < 18 || item.length > 90) return false;
    return true;
  });
}

export function suggestFollowUps(question: string, answer: string): string[] {
  const sections = splitSections(answer);
  const ranked: string[] = [];
  const seen = new Set<string>();

  const push = (item: string | undefined) => {
    const text = (item || "").trim();
    if (!text) return;
    const key = normalizeQuestion(text);
    if (!key || seen.has(key) || GENERIC_QUESTION_RE.test(text)) return;
    seen.add(key);
    ranked.push(text.endsWith("?") ? text : `${text}?`);
  };

  // Mixed answers: take the strongest question from each section first.
  for (const section of sections) {
    const local = questionsForSection(section, question);
    if (local[0]) push(local[0]);
  }
  for (const section of sections) {
    for (const item of questionsForSection(section, question).slice(1)) {
      push(item);
    }
  }

  if (ranked.length === 0) {
    const heading = sections.find((item) => item.heading)?.heading;
    if (heading) push(`What else does the document say about ${titleCase(heading)}?`);
  }

  return ranked.slice(0, 3);
}

export function citedDocumentIds(
  citations: Array<{ documentId?: string | null }> | undefined
): string[] {
  const ids: string[] = [];
  const seen = new Set<string>();
  for (const citation of citations || []) {
    const id = citation.documentId?.trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    ids.push(id);
  }
  return ids;
}

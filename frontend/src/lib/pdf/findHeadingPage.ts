import type { PDFDocumentProxy } from "pdfjs-dist";

import { loadPdfDocument } from "./pdfjs";

const MAX_PAGES_TO_SCAN = 200;

const HEADING_ONES = [
  "",
  "one",
  "two",
  "three",
  "four",
  "five",
  "six",
  "seven",
  "eight",
  "nine",
  "ten",
  "eleven",
  "twelve",
];

const HEADING_ROMAN = [
  "",
  "i",
  "ii",
  "iii",
  "iv",
  "v",
  "vi",
  "vii",
  "viii",
  "ix",
  "x",
  "xi",
  "xii",
];

const WORD_TO_NUMBER: Record<string, number> = Object.fromEntries(
  HEADING_ONES.map((word, index) => [word, index]).filter(([word]) => word)
);

const ROMAN_TO_NUMBER: Record<string, number> = Object.fromEntries(
  HEADING_ROMAN.map((word, index) => [word, index]).filter(([word]) => word)
);

export function normalizeHeadingNeedle(query: string): string {
  return (query || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

export function headingSearchNeedles(query: string): string[] {
  const needle = normalizeHeadingNeedle(query);
  if (!needle) return [];
  const needles = new Set<string>([needle]);
  const match = /^([a-z]+)\s+([a-z0-9]+)$/.exec(needle);
  if (!match) return [...needles];

  const label = match[1];
  const token = match[2];
  const number = /^\d+$/.test(token)
    ? Number(token)
    : WORD_TO_NUMBER[token] || ROMAN_TO_NUMBER[token];
  if (!number || number < 1) return [...needles];

  needles.add(`${label} ${number}`);
  if (HEADING_ONES[number]) needles.add(`${label} ${HEADING_ONES[number]}`);
  if (HEADING_ROMAN[number]) needles.add(`${label} ${HEADING_ROMAN[number]}`);
  return [...needles];
}

export function pageTextMatchesHeading(pageText: string, query: string): boolean {
  const hay = normalizeHeadingNeedle(pageText);
  if (!hay) return false;
  const compactHay = hay.replace(/ /g, "");
  return headingSearchNeedles(query).some((needle) => {
    if (hay.includes(needle)) return true;
    return compactHay.includes(needle.replace(/ /g, ""));
  });
}

async function pagePlainText(
  pdf: PDFDocumentProxy,
  pageNumber: number
): Promise<string> {
  const page = await pdf.getPage(pageNumber);
  const content = await page.getTextContent();
  return content.items
    .map((item) => ("str" in item ? item.str : ""))
    .join(" ");
}

export async function findHeadingPageInPdf(
  pdf: PDFDocumentProxy,
  query: string
): Promise<number | null> {
  const last = Math.min(pdf.numPages, MAX_PAGES_TO_SCAN);
  for (let page = 1; page <= last; page += 1) {
    const text = await pagePlainText(pdf, page);
    if (pageTextMatchesHeading(text, query)) return page;
  }
  return null;
}

export async function findHeadingPage(
  fileUrl: string,
  query: string
): Promise<{ page: number | null; pageCount: number }> {
  const pdf = await loadPdfDocument(fileUrl);
  try {
    const page = await findHeadingPageInPdf(pdf, query);
    return { page, pageCount: pdf.numPages };
  } finally {
    void pdf.destroy();
  }
}

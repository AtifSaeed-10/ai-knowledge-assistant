export function formatWhen(value: string | null | undefined): string {
  if (!value) return "—";
  const time = Date.parse(value);
  if (Number.isNaN(time)) return "—";

  const diff = Date.now() - time;
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (diff < 45_000) return "Just now";
  if (diff < hour) return `${Math.max(1, Math.round(diff / minute))}m ago`;
  if (diff < day) return `${Math.max(1, Math.round(diff / hour))}h ago`;
  if (diff < 7 * day) return `${Math.max(1, Math.round(diff / day))}d ago`;

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(time);
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}

export function formatMoney(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
}

export function statusLabel(status: string | null | undefined): string {
  const value = (status || "unknown").replace(/_/g, " ");
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function kindLabel(kind: string | null | undefined): string {
  switch (kind) {
    case "llm":
      return "Model";
    case "index":
      return "Indexing";
    case "quota":
      return "Quota";
    case "http":
      return "Request";
    case "unanswered":
      return "Couldn't answer";
    case "answer":
      return "Answered";
    default:
      return statusLabel(kind);
  }
}

export function providerLabel(provider: string | null | undefined): string {
  const key = (provider || "").trim().toLowerCase();
  switch (key) {
    case "groq":
      return "Groq";
    case "gemini":
      return "Gemini";
    case "cerebras":
      return "Cerebras";
    case "openrouter":
      return "OpenRouter";
    case "mistral":
      return "Mistral";
    case "ollama":
      return "Ollama";
    case "":
    case "unknown":
      return "Unknown";
    default:
      return statusLabel(provider);
  }
}

export function countryName(code: string | null | undefined): string {
  const value = (code || "").trim().toUpperCase();
  if (!value) return "Unknown";
  try {
    return new Intl.DisplayNames(["en"], { type: "region" }).of(value) || value;
  } catch {
    return value;
  }
}

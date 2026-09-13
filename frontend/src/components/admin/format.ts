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
    default:
      return statusLabel(kind);
  }
}

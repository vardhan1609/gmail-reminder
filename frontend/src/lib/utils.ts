import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface DualDate {
  local: string;        // e.g. "Oct 29, 2026, 11:41 PM IST"
  localDate: string;    // e.g. "Oct 29, 2026"
  localTime: string;    // e.g. "11:41 PM"
  tzName: string;       // e.g. "IST"
  utc: string;          // e.g. "Oct 29, 2026, 6:11 PM UTC"
  utcTime: string;      // e.g. "18:11 UTC"
  combined: string;     // e.g. "Oct 29, 2026, 11:41 PM IST (18:11 UTC)"
}

export function parseUtcDate(dateString: string | null | undefined): Date | null {
  if (!dateString) return null;
  let str = dateString.trim();
  // If the datetime string does not specify a timezone indicator ('Z' or '+/-offset'),
  // assume it was saved in UTC and format it in the user's local timezone.
  if (!str.endsWith("Z") && !str.includes("+") && !/-\d{2}:\d{2}$/.test(str)) {
    str = str.replace(" ", "T") + "Z";
  }
  const d = new Date(str);
  if (isNaN(d.getTime())) return null;
  return d;
}

export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return "N/A";
  try {
    const d = parseUtcDate(dateString);
    if (!d) return dateString;
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(d);
  } catch {
    return dateString;
  }
}

export function formatDateUtc(dateString: string | null | undefined): string {
  if (!dateString) return "N/A";
  try {
    const d = parseUtcDate(dateString);
    if (!d) return dateString;
    const formatted = new Intl.DateTimeFormat(undefined, {
      timeZone: "UTC",
      dateStyle: "medium",
      timeStyle: "short",
    }).format(d);
    return `${formatted} UTC`;
  } catch {
    return dateString;
  }
}

export function formatDualDate(dateString: string | null | undefined): DualDate | null {
  if (!dateString) return null;
  try {
    const d = parseUtcDate(dateString);
    if (!d) return null;

    const local = new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(d);

    const localDate = new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
    }).format(d);

    const localTime = new Intl.DateTimeFormat(undefined, {
      timeStyle: "short",
    }).format(d);

    const parts = new Intl.DateTimeFormat(undefined, { timeZoneName: "short" }).formatToParts(d);
    const tzName = parts.find((p) => p.type === "timeZoneName")?.value || "";

    const utc = new Intl.DateTimeFormat(undefined, {
      timeZone: "UTC",
      dateStyle: "medium",
      timeStyle: "short",
    }).format(d);

    const utcTime = new Intl.DateTimeFormat(undefined, {
      timeZone: "UTC",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(d);

    const tzLabel = tzName ? ` ${tzName}` : "";
    const combined = `${local}${tzLabel} (${utcTime} UTC)`;

    return {
      local: tzName ? `${local} ${tzName}` : local,
      localDate,
      localTime,
      tzName,
      utc: `${utc} UTC`,
      utcTime: `${utcTime} UTC`,
      combined,
    };
  } catch {
    return null;
  }
}


// Zahlen und Daten im Format der HASS-Sprache.

export function formatNumber(language: string, value: number | null, digits = 1): string {
  if (value === null) return "–";
  return new Intl.NumberFormat(language, { maximumFractionDigits: digits }).format(value);
}

export function formatDateTime(language: string, unixSeconds: number): string {
  return new Intl.DateTimeFormat(language, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(unixSeconds * 1000),
  );
}

/** Datum aus <input type="date"> als Unix-Sekunden, Tagesanfang oder -ende in Ortszeit. */
export function dateInputToUnix(value: string, endOfDay: boolean): number | undefined {
  if (!value) return undefined;
  const [year, month, day] = value.split("-").map(Number);
  const date = endOfDay
    ? new Date(year, month - 1, day, 23, 59, 59)
    : new Date(year, month - 1, day, 0, 0, 0);
  return Math.floor(date.getTime() / 1000);
}

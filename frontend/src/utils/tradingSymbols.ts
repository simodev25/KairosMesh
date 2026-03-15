const FOREX_PAIR_PATTERN = /[A-Z]{6}/;

export function resolveTicket(value: Record<string, unknown>): string {
  const raw = value.ticket ?? value.orderId ?? value.id ?? value.positionId ?? null;
  if (raw == null) return '-';
  const text = String(raw).trim();
  return text || '-';
}

export function normalizeSymbol(value: unknown): string {
  return String(value ?? '').trim().toUpperCase();
}

export function symbolBase(value: unknown): string {
  const normalized = normalizeSymbol(value);
  if (!normalized) return '';
  const forexMatch = normalized.match(FOREX_PAIR_PATTERN);
  if (forexMatch) return forexMatch[0];
  const withoutPrefix = normalized.replace(/^[^A-Z0-9]+/, '');
  const withoutSuffix = withoutPrefix.replace(/[^A-Z0-9]+$/, '');
  return withoutSuffix || normalized;
}

export function symbolsLikelyMatch(left: unknown, right: unknown): boolean {
  const leftNorm = normalizeSymbol(left);
  const rightNorm = normalizeSymbol(right);
  if (!leftNorm || !rightNorm) return false;
  if (leftNorm === rightNorm) return true;
  return symbolBase(leftNorm) === symbolBase(rightNorm);
}

import type { ExecutionOrder } from '../../types';
import { symbolBase } from '../../utils/tradingSymbols';

export function displaySymbol(value: unknown): string {
  const base = symbolBase(value);
  return base || '-';
}

function asText(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

export function failureReason(order: ExecutionOrder): string {
  const payload = asRecord(order.response_payload);
  const result = asRecord(payload?.result);
  return (
    asText(order.error) ??
    asText(payload?.reason) ??
    asText(payload?.message) ??
    asText(payload?.error) ??
    asText(result?.reason) ??
    asText(result?.message) ??
    asText(result?.error) ??
    'Aucune raison explicite fournie'
  );
}

export function failureCode(order: ExecutionOrder): string {
  const payload = asRecord(order.response_payload);
  const result = asRecord(payload?.result);
  const stringCode = asText(result?.stringCode) ?? asText(payload?.stringCode);
  const numericCode = typeof result?.numericCode === 'number'
    ? String(result.numericCode)
    : (typeof payload?.numericCode === 'number' ? String(payload.numericCode) : null);
  if (stringCode && numericCode) return `${stringCode} (${numericCode})`;
  return stringCode ?? numericCode ?? '-';
}

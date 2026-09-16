import { EVENT_TYPE_LABELS, TAX_TREATMENT_LABELS } from '../constants'
import type { RatioValue } from '../types'

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  return `${(bytes / 1024).toFixed(bytes < 1024 * 10 ? 1 : 0)} KB`
}

export function formatValue(value: string | RatioValue | null, label: string): string {
  if (value == null) return '—'
  if (typeof value === 'object') return `${value.numerator}:${value.denominator}`
  if (label === 'Alíquota') return `${value}%`
  if (label === 'Tipo de evento') return EVENT_TYPE_LABELS[value] || value
  if (label === 'Tratamento tributário') return TAX_TREATMENT_LABELS[value] || value
  if (/^\d{4}-\d{2}-\d{2}$/.test(String(value))) {
    const [year, month, day] = String(value).split('-')
    return `${day}/${month}/${year}`
  }
  return String(value)
}

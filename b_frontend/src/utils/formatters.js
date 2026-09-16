import { EVENT_TYPE_LABELS, TAX_TREATMENT_LABELS } from '../constants'

export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  return `${(bytes / 1024).toFixed(bytes < 1024 * 10 ? 1 : 0)} KB`
}

export function formatValue(value, label) {
  if (value == null) return '—'
  if (typeof value === 'object') {
    if (value.numerator && value.denominator) return `${value.numerator}:${value.denominator}`
    return JSON.stringify(value)
  }
  if (label === 'Alíquota') return `${value}%`
  if (label === 'Tipo de evento') return EVENT_TYPE_LABELS[value] || value
  if (label === 'Tratamento tributário') return TAX_TREATMENT_LABELS[value] || value
  if (/^\d{4}-\d{2}-\d{2}$/.test(String(value))) {
    const [year, month, day] = String(value).split('-')
    return `${day}/${month}/${year}`
  }
  return String(value)
}

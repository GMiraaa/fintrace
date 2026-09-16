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
  return String(value)
}

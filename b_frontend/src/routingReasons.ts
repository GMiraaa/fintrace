import { REASON_LABELS } from './constants'
import type { RoutingReason } from './types'

const CRITICAL_CONFIDENCE_CODE = 'CRITICAL_FIELD_CONFIDENCE_BELOW_THRESHOLD'

export function summarizeRoutingReasons(reasons: RoutingReason[]): string[] {
  const messages: string[] = []
  const seenMessages = new Set<string>()
  const criticalFieldCount = reasons.filter(
    (reason) => reason.code === CRITICAL_CONFIDENCE_CODE,
  ).length
  let criticalConfidenceAdded = false

  for (const reason of reasons) {
    if (reason.code === CRITICAL_CONFIDENCE_CODE) {
      if (!criticalConfidenceAdded) {
        messages.push(criticalConfidenceMessage(criticalFieldCount))
        criticalConfidenceAdded = true
      }
      continue
    }

    const message = REASON_LABELS[reason.code]
      || reason.message
      || 'O documento precisa de atenção.'
    if (!seenMessages.has(message)) {
      seenMessages.add(message)
      messages.push(message)
    }
  }

  return messages
}

function criticalConfidenceMessage(count: number): string {
  if (count === 1) return 'Um campo crítico ficou abaixo de 75% de confiança.'
  return `${count} campos críticos ficaram abaixo de 75% de confiança.`
}

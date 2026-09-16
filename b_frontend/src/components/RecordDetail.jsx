import { useEffect, useState } from 'react'

import { getDocumentFileUrl } from '../api'
import {
  CONFIDENCE_LABELS,
  DATE_LABELS,
  EXTRACTION_METHOD_LABELS,
  EXTRACTION_OUTCOME_LABELS,
  EXTRACTION_STRATEGY_LABELS,
  FIELD_STATUS_LABELS,
  FINANCIAL_LABELS,
  ORIGIN_LABELS,
  STATUS_LABELS,
} from '../constants'
import { formatValue } from '../utils/formatters'
import { Icon } from './Icon'

export function RecordDetail({ record }) {
  const [showDocument, setShowDocument] = useState(false)
  const action = record.corporate_action
  const reference = record.reference_validation
  const failedRules = record.validations.filter((item) => item.status === 'FAIL')
  const eventType = action.event_type.value || 'UNKNOWN'
  const attempts = record.extraction_attempts || []
  const documentUrl = getDocumentFileUrl(record.document_id)

  useEffect(() => setShowDocument(false), [record.document_id])

  return (
    <article className="audit-record">
      <header className="record-header">
        <div>
          <StatusPill status={record.processing_status} />
          <h3>{record.issuer.name.value || 'Emissor não identificado'}</h3>
          <p>
            {eventType} · {record.security.ticker.value || 'ticker desconhecido'} ·{' '}
            {record.security.isin.value || 'ISIN desconhecido'}
          </p>
        </div>
        <div className="record-actions">
          <button className="secondary-action" onClick={() => setShowDocument((current) => !current)} type="button">
            <Icon name="eye" size={17} />
            {showDocument ? 'Ocultar documento' : 'Ver documento'}
          </button>
          <button className="secondary-action" onClick={() => downloadRecord(record)} type="button">
            <Icon name="download" size={17} />
            Baixar JSON
          </button>
        </div>
      </header>

      {showDocument && (
        <section className="document-viewer" aria-label="Documento original">
          <div className="document-viewer__heading">
            <div><Icon name="file" /><span><strong>Documento original</strong><small>{record.source_document.file_name}</small></span></div>
            <a href={documentUrl} rel="noreferrer" target="_blank">Abrir em nova guia</a>
          </div>
          <iframe src={documentUrl} title={`Documento ${record.source_document.file_name}`} />
        </section>
      )}

      <div className="record-trace" aria-label="Controles aplicados">
        <TraceCheck
          label="Extração"
          detail={attempts.length
            ? attempts.map((attempt) => EXTRACTION_STRATEGY_LABELS[attempt.strategy] || attempt.strategy).join(' → ')
            : record.source_document.extraction_methods.join(' + ')}
          ok={attempts.length ? attempts.at(-1).outcome === 'SUFFICIENT' : true}
        />
        <TraceCheck
          label="Referência"
          detail={reference.exact_match ? `Confirmado por ${reference.matched_by.join(', ')}` : 'Sem confirmação exata'}
          ok={reference.exact_match}
        />
        <TraceCheck label="Regras" detail={failedRules.length ? `${failedRules.length} falha(s)` : 'Sem falhas'} ok={!failedRules.length} />
        <TraceCheck
          label="Decisão"
          detail={STATUS_LABELS[record.processing_status]}
          ok={record.processing_status === 'ACCEPTED'}
          neutral={record.processing_status === 'PENDING_INFORMATION'}
        />
      </div>

      <AuditSummary record={record} />
      <ReferenceValidation reference={reference} />

      <FieldSection title="Classificação do evento" fields={[
        ['Tipo de evento', action.event_type],
      ]} />
      <ClassificationAudit
        conflicts={action.classification_conflicts || []}
        evidence={action.classification_evidence || []}
      />
      <FieldSection title="Identificação" fields={[
        ['Emissor', record.issuer.name],
        ['CNPJ', record.issuer.cnpj],
        ['ISIN', record.security.isin],
        ['Ticker', record.security.ticker],
        ['Classe', record.security.share_class],
        ['Segmento', record.security.listing_segment],
        ['Status do ativo', record.security.asset_status],
      ]} />
      <FieldSection title="Datas" fields={Object.entries(action.dates).map(([name, field]) => [DATE_LABELS[name], field])} />
      <FieldSection title="Valores, tributos e proporções" fields={Object.entries(action.financials).map(([name, field]) => [FINANCIAL_LABELS[name], field])} />

      {attempts.length > 0 && (
        <details className="validation-log">
          <summary>Tentativas de extração <span>{attempts.length}</span></summary>
          <div>{attempts.map((attempt, index) => (
            <div className="validation-row" key={`${attempt.strategy}:${index}`}>
              <ValidationState status={attempt.outcome === 'SUFFICIENT' ? 'PASS' : attempt.outcome === 'ERROR' ? 'FAIL' : 'WARN'} label={EXTRACTION_OUTCOME_LABELS[attempt.outcome] || attempt.outcome} />
              <span>
                <strong>{EXTRACTION_STRATEGY_LABELS[attempt.strategy] || attempt.strategy}</strong>
                <small>
                  {attempt.model ? `${attempt.model} · ` : ''}
                  {attempt.error || (attempt.unresolved_fields.length
                    ? `Pendências: ${attempt.unresolved_fields.join(', ')}`
                    : 'Todos os campos críticos foram resolvidos.')}
                </small>
              </span>
            </div>
          ))}</div>
        </details>
      )}

      <details className="validation-log" open={failedRules.length > 0}>
        <summary>Log completo de validações <span>{record.validations.length}</span></summary>
        <div>{record.validations.map((validation, index) => (
          <ValidationRow key={`${validation.rule}:${index}`} validation={validation} />
        ))}</div>
      </details>
    </article>
  )
}

function ClassificationAudit({ evidence, conflicts }) {
  if (!evidence.length && !conflicts.length) return null

  return (
    <details className="classification-audit">
      <summary>
        Evidências da classificação
        <span>{evidence.length} sinal(is) · {conflicts.length} conflito(s)</span>
      </summary>
      <div>
        {evidence.map((item, index) => (
          <article key={`${item.supports}:${item.source?.page}:${index}`}>
            <strong>Sustenta {item.supports}</strong>
            <p>{item.rationale}</p>
            {item.source && (
              <blockquote>
                “{item.source.evidence}”
                <cite>Página {item.source.page} · {EXTRACTION_METHOD_LABELS[item.source.extraction_method] || item.source.extraction_method}</cite>
              </blockquote>
            )}
          </article>
        ))}
        {conflicts.map((conflict, index) => (
          <article className="classification-audit__conflict" key={`${conflict.code || conflict.message}:${index}`}>
            <strong>{conflict.code || 'Conflito de classificação'}</strong>
            <p>{conflict.message || formatPrimitive(conflict)}</p>
          </article>
        ))}
      </div>
    </details>
  )
}

function AuditSummary({ record }) {
  const reasons = [
    ...(record.review?.reasons || []),
    ...(record.follow_up?.reasons || []),
  ]
  return (
    <section className={`decision-card decision-card--${record.processing_status.toLowerCase()}`}>
      <div className="decision-card__icon"><Icon name="shield" size={21} /></div>
      <div>
        <p className="audit-eyebrow">Decisão operacional</p>
        <h4>{STATUS_LABELS[record.processing_status] || record.processing_status}</h4>
        {reasons.length ? (
          <ul>{reasons.map((reason) => <li key={`${reason.code}:${reason.message}`}><strong>{reason.code}</strong><span>{reason.message}</span></li>)}</ul>
        ) : <p>O registro passou pelos controles de extração, referência e coerência sem bloqueios materiais.</p>}
      </div>
      <dl className="document-metadata">
        <div><dt>Páginas</dt><dd>{record.source_document.page_count}</dd></div>
        <div><dt>Leitura</dt><dd>{record.source_document.extraction_methods.map((method) => EXTRACTION_METHOD_LABELS[method] || method).join(' + ')}</dd></div>
        <div><dt>Hash</dt><dd title={record.source_document.sha256}>{record.source_document.sha256.slice(0, 12)}…</dd></div>
      </dl>
    </section>
  )
}

function ReferenceValidation({ reference }) {
  const canonical = reference.reference_record
  return (
    <details className="reference-card" open={!reference.exact_match}>
      <summary>
        <span className="reference-icon"><Icon name="database" size={18} /></span>
        <span><strong>Validação contra a base de referência</strong><small>{reference.exact_match ? `Correspondência exata por ${reference.matched_by.join(', ')}` : 'Correspondência exata não confirmada'}</small></span>
        <span className={`reference-result reference-result--${reference.exact_match ? 'ok' : 'attention'}`}>{reference.exact_match ? 'CONFIRMADO' : 'ATENÇÃO'}</span>
      </summary>
      <div className="reference-card__body">
        {canonical ? (
          <dl className="canonical-grid">
            <ReferenceValue label="Emissor" value={canonical.issuer} />
            <ReferenceValue label="CNPJ" value={canonical.cnpj} />
            <ReferenceValue label="ISIN" value={canonical.isin} />
            <ReferenceValue label="Ticker" value={canonical.ticker} />
            <ReferenceValue label="Classe" value={canonical.share_class} />
            <ReferenceValue label="Segmento" value={canonical.listing_segment} />
            <ReferenceValue label="Status do ativo" value={canonical.status} />
          </dl>
        ) : <p>Nenhum registro canônico foi confirmado com os identificadores extraídos.</p>}
        {reference.conflicts.length > 0 && <div className="reference-conflicts"><h5>Conflitos encontrados</h5>{reference.conflicts.map((conflict) => <div key={`${conflict.code}:${conflict.field}`}><strong>{conflict.field}</strong><span>Esperado: {formatPrimitive(conflict.expected)}</span><span>Observado: {formatPrimitive(conflict.observed)}</span></div>)}</div>}
        {reference.possible_matches.length > 0 && <div className="possible-matches"><h5>Possíveis correspondências — somente sugestão</h5>{reference.possible_matches.map((match) => <p key={match.isin}>{match.issuer} · {match.ticker} · {match.isin}</p>)}</div>}
      </div>
    </details>
  )
}

function ReferenceValue({ label, value }) {
  return <div><dt>{label}</dt><dd>{value || '—'}</dd></div>
}

function FieldSection({ title, fields }) {
  const visible = fields.filter(([, field]) => field)
  return (
    <section className="field-section">
      <div className="field-section__heading"><h4>{title}</h4><span>{visible.length} campos auditáveis</span></div>
      <div className="field-table">{visible.map(([label, field]) => <FieldRow field={field} key={label} label={label} />)}</div>
    </section>
  )
}

function FieldRow({ label, field }) {
  return (
    <details className="field-row">
      <summary>
        <span className="field-name">{label}</span>
        <span className={field.value == null ? 'field-value field-value--empty' : 'field-value'}>{formatValue(field.value, label)}</span>
        <span className={`confidence confidence--${field.confidence.toLowerCase()}`}>{CONFIDENCE_LABELS[field.confidence] || field.confidence}</span>
        <span className="field-origin">{FIELD_STATUS_LABELS[field.status] || field.status}</span>
      </summary>
      <div className="field-evidence">
        <div className="confidence-reason"><strong>Por que essa confiança?</strong><span>{confidenceReason(field)}</span></div>
        <p className="field-provenance">Origem: <strong>{ORIGIN_LABELS[field.origin] || field.origin}</strong></p>
        {field.sources.length ? field.sources.map((source, index) => (
          <blockquote key={`${source.page}:${index}`}>“{source.evidence}” <cite>Página {source.page} · {EXTRACTION_METHOD_LABELS[source.extraction_method] || source.extraction_method}</cite></blockquote>
        )) : <p>Nenhuma evidência documental associada.</p>}
        {field.validation.length > 0 && <div className="field-validations"><strong>Validações deste campo</strong>{field.validation.map((validation, index) => <ValidationRow compact key={`${validation.rule}:${index}`} validation={validation} />)}</div>}
      </div>
    </details>
  )
}

function ValidationRow({ validation, compact = false }) {
  return (
    <div className={compact ? 'validation-row validation-row--compact' : 'validation-row'}>
      <ValidationState status={validation.status} label={validation.status} />
      <span>
        <strong>{validation.rule}</strong>
        <small>{validation.message}</small>
        {(validation.expected != null || validation.observed != null) && (
          <span className="validation-comparison">
            {validation.expected != null && <span>Esperado: <strong>{formatPrimitive(validation.expected)}</strong></span>}
            {validation.observed != null && <span>Observado: <strong>{formatPrimitive(validation.observed)}</strong></span>}
          </span>
        )}
      </span>
    </div>
  )
}

function ValidationState({ status, label }) {
  return <span className={`validation-state validation-state--${status.toLowerCase()}`}>{label}</span>
}

function TraceCheck({ label, detail, ok, neutral = false }) {
  return <div className={`trace-check ${ok ? 'trace-check--ok' : neutral ? 'trace-check--neutral' : 'trace-check--attention'}`}><span>{ok ? <Icon name="check" size={14} /> : '!'}</span><div><strong>{label}</strong><small>{detail}</small></div></div>
}

function StatusPill({ status }) {
  return <span className={`status-pill status-pill--${status.toLowerCase()}`}>{STATUS_LABELS[status] || status}</span>
}

function confidenceReason(field) {
  if (field.validation.some((validation) => validation.status === 'FAIL')) return 'Uma regra associada ao campo falhou; o valor exige revisão.'
  if (['AMBIGUOUS', 'CONFLICT', 'UNREADABLE', 'UNKNOWN'].includes(field.status)) return `O status ${FIELD_STATUS_LABELS[field.status] || field.status} impede confiança automática.`
  if (field.status === 'NOT_DISCLOSED') return field.sources.length ? 'O documento declara explicitamente que a informação ainda não foi divulgada.' : 'A informação está pendente, mas sem evidência literal associada.'
  if (field.origin === 'REFERENCE') return 'Valor enriquecido pela base canônica após a validação dos identificadores.'
  if (field.origin === 'DERIVED') return 'Valor calculado por regra determinística e associado às validações do registro.'
  if (field.sources.some((source) => source.extraction_method === 'OCR')) return 'Valor sustentado por evidência literal obtida por OCR; por isso recebe confiança média.'
  if (field.origin === 'DOCUMENT' && field.sources.length) return 'Valor sustentado por evidência literal encontrada no texto nativo do documento.'
  return 'Não há evidência suficiente para elevar a confiança deste campo.'
}

function formatPrimitive(value) {
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}

function downloadRecord(record) {
  const blob = new Blob([`${JSON.stringify(record, null, 2)}\n`], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${record.source_document.file_name.replace(/\.pdf$/i, '')}.json`
  link.click()
  URL.revokeObjectURL(url)
}

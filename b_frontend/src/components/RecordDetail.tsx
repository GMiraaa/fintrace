import { useEffect, useState } from 'react'

import { getDocumentFileUrl } from '../api'
import {
  CONFIDENCE_LABELS,
  DATE_LABELS,
  EVENT_TYPE_LABELS,
  EXTRACTION_METHOD_LABELS,
  EXTRACTION_STRATEGY_LABELS,
  FIELD_HELP,
  FIELD_PATH_LABELS,
  FIELD_STATUS_LABELS,
  FINANCIAL_LABELS,
  MATCH_FIELD_LABELS,
  ORIGIN_LABELS,
  REASON_LABELS,
  STATUS_LABELS,
  VALIDATION_RULE_LABELS,
  VALIDATION_STATUS_LABELS,
} from '../constants'
import { formatValue } from '../utils/formatters'
import { DocumentThumbnail } from './DocumentThumbnail'
import { Icon } from './Icon'
import type {
  AuditableField,
  ClassificationConflict,
  ClassificationSignal,
  CorporateAction,
  DocumentRecord,
  ExtractionMethod,
  JsonValue,
  ProcessingStatus,
  RatioValue,
  ReferenceValidation as ReferenceValidationType,
  RoutingReason,
  ValidationResult,
  ValidationStatus,
} from '../types'

const DETAIL_TABS = [
  ['resumo', 'Visão geral'],
  ['dados', 'Dados extraídos'],
  ['historico', 'Histórico da análise'],
] as const

type DetailTab = (typeof DETAIL_TABS)[number][0]
type DisplayField = AuditableField<string | RatioValue>

interface RecordDetailProps {
  record: DocumentRecord
}

export function RecordDetail({ record }: RecordDetailProps) {
  const [activeTab, setActiveTab] = useState<DetailTab>('resumo')
  const [showDocument, setShowDocument] = useState(false)
  const action = record.corporate_action
  const eventType = action.event_type.value
    ? EVENT_TYPE_LABELS[action.event_type.value] || 'Evento não identificado'
    : 'Evento não identificado'
  const documentUrl = getDocumentFileUrl(record.document_id)

  useEffect(() => {
    setActiveTab('resumo')
    setShowDocument(false)
  }, [record.document_id])

  return (
    <article className="audit-record">
      <header className="record-header">
        <div className="record-header__main">
          <StatusPill status={record.processing_status} />
          <h3>{record.issuer.name.value || 'Emissor não identificado'}</h3>
          <p>{eventType}<span aria-hidden="true">•</span>{record.security.ticker.value || 'Código não identificado'}<span aria-hidden="true">•</span>{record.security.isin.value || 'ISIN não identificado'}</p>
          <div className="record-actions">
            <button className="secondary-action" onClick={() => setShowDocument((current) => !current)} type="button">
              <Icon name="eye" size={17} />
              {showDocument ? 'Fechar documento' : 'Abrir visualizador'}
            </button>
            <button className="secondary-action" onClick={() => downloadRecord(record)} type="button">
              <Icon name="download" size={17} />
              Baixar dados em JSON
            </button>
          </div>
        </div>
        <DocumentThumbnail fileName={record.source_document.file_name} onOpen={() => setShowDocument(true)} url={documentUrl} />
      </header>

      {showDocument && <DocumentViewer record={record} url={documentUrl} />}

      <DecisionPanel record={record} />

      <nav className="detail-tabs" aria-label="Seções do documento">
        {DETAIL_TABS.map(([id, label]) => (
          <button
            aria-current={activeTab === id ? 'page' : undefined}
            className={activeTab === id ? 'detail-tab detail-tab--active' : 'detail-tab'}
            key={id}
            onClick={() => setActiveTab(id)}
            type="button"
          >
            {label}
          </button>
        ))}
      </nav>

      {activeTab === 'resumo' && <Overview record={record} />}
      {activeTab === 'dados' && <ExtractedData action={action} record={record} />}
      {activeTab === 'historico' && <AnalysisHistory record={record} />}
    </article>
  )
}

function DocumentViewer({ record, url }: { record: DocumentRecord; url: string }) {
  return (
    <section className="document-viewer" aria-label="Documento original">
      <div className="document-viewer__heading">
        <div><Icon name="file" /><span><strong>Documento original</strong><small>{record.source_document.file_name}</small></span></div>
        <a href={url} rel="noreferrer" target="_blank">Abrir em outra guia</a>
      </div>
      <iframe src={url} title={`Documento ${record.source_document.file_name}`} />
    </section>
  )
}

function DecisionPanel({ record }: { record: DocumentRecord }) {
  const reasons = [...(record.review?.reasons || []), ...(record.follow_up?.reasons || [])]
  const documentConfidence = record.document_confidence || {
    score: 0,
    completion_percentage: 0,
    missing_fields: [],
  }
  const accepted = record.processing_status === 'ACCEPTED'
  const title = accepted ? 'Registro pronto para uso' : STATUS_LABELS[record.processing_status]
  const guidance = accepted
    ? 'Os identificadores, os campos críticos e as regras de coerência não apresentaram bloqueios.'
    : record.processing_status === 'PENDING_INFORMATION'
      ? 'Acompanhe a divulgação da informação pendente antes de concluir o evento.'
      : record.processing_status === 'FAILED'
        ? 'Corrija o arquivo ou a indisponibilidade indicada e processe o documento novamente.'
        : 'Confira os motivos abaixo e valide o registro antes de utilizá-lo.'

  return (
    <section className={`decision-panel decision-panel--${record.processing_status.toLowerCase()}`}>
      <div className="decision-panel__symbol"><Icon name={accepted ? 'check' : 'alert'} size={23} /></div>
      <div className="decision-panel__content">
        <span>Resultado deste documento</span>
        <h4>{title}</h4>
        <p>{guidance}</p>
        <div className="document-confidence">
          <div>
            <strong>{documentConfidence.score}%</strong>
            <span>Confiança do documento</span>
          </div>
          <progress aria-label="Confiança do documento" max="100" value={documentConfidence.score} />
          <small>{documentConfidence.completion_percentage}% dos campos materiais foram coletados.{documentConfidence.missing_fields.length > 0 ? ` Pendentes: ${documentConfidence.missing_fields.map(fieldPathLabel).join(', ')}.` : ''}</small>
        </div>
        {reasons.length > 0 && <ul>{reasons.map((reason) => <li key={`${reason.code}:${reason.message}`}>{reasonText(reason)}</li>)}</ul>}
      </div>
      <dl className="document-metadata">
        <div><dt>Páginas</dt><dd>{record.source_document.page_count}</dd></div>
        <div><dt>Forma de leitura</dt><dd>{record.source_document.extraction_methods.map(methodLabel).join(' e ')}</dd></div>
        <div><dt>Identificador do arquivo</dt><dd title={record.source_document.sha256}>{record.source_document.sha256.slice(0, 12)}…</dd></div>
      </dl>
    </section>
  )
}

function Overview({ record }: { record: DocumentRecord }) {
  const reference = record.reference_validation
  const attempts = record.extraction_attempts || []
  const failedRules = record.validations.filter((item) => item.status === 'FAIL')

  return (
    <div className="tab-content">
      <section className="overview-intro">
        <h4>Como interpretar este resultado</h4>
        <p>Os quatro controles abaixo mostram onde o documento passou e onde existe atenção. Abra “Dados extraídos” para conferir cada valor e sua evidência.</p>
      </section>
      <div className="control-grid" aria-label="Controles aplicados">
        <ControlItem
          detail={attempts.length ? attempts.map((attempt) => EXTRACTION_STRATEGY_LABELS[attempt.strategy] || attempt.strategy).join(' seguida de ') : 'Leitura concluída'}
          label="Leitura do documento"
          ok={attempts.length ? attempts.at(-1)!.outcome === 'SUFFICIENT' : true}
        />
        <ControlItem
          detail={reference.exact_match ? `Identidade confirmada por ${reference.matched_by.map(matchFieldLabel).join(', ')}` : 'Não houve confirmação exata do ativo'}
          label="Base oficial"
          ok={reference.exact_match}
        />
        <ControlItem detail={failedRules.length ? `${failedRules.length} regra(s) reprovaram o registro` : 'Todas as regras aplicáveis foram aprovadas'} label="Regras de coerência" ok={!failedRules.length} />
        <ControlItem
          detail={STATUS_LABELS[record.processing_status]}
          label="Encaminhamento"
          neutral={record.processing_status === 'PENDING_INFORMATION'}
          ok={record.processing_status === 'ACCEPTED'}
        />
      </div>
      <ReferenceValidation reference={reference} />
    </div>
  )
}

function ExtractedData({ action, record }: { action: CorporateAction; record: DocumentRecord }) {
  return (
    <div className="tab-content">
      <ConfidenceGuide />
      <section className="reading-guide">
        <div><strong>Valor</strong><span>Informação estruturada pelo sistema.</span></div>
        <div><strong>Confiança</strong><span>Qualidade da evidência: alta, média ou baixa.</span></div>
        <div><strong>Situação</strong><span>Como o valor foi obtido ou por que está ausente.</span></div>
      </section>

      <FieldSection title="Tipo de evento" fields={[["Tipo de evento", action.event_type]]} />
      <ClassificationAudit conflicts={action.classification_conflicts || []} evidence={action.classification_evidence || []} />
      <FieldSection title="Identificação do ativo" fields={[
        ['Emissor', record.issuer.name],
        ['CNPJ', record.issuer.cnpj],
        ['ISIN', record.security.isin],
        ['Código de negociação', record.security.ticker],
        ['Classe do ativo', record.security.share_class],
        ['Segmento de listagem', record.security.listing_segment],
        ['Status do ativo', record.security.asset_status],
      ]} />
      <FieldSection title="Datas do evento" fields={Object.entries(action.dates).map(([name, field]) => [DATE_LABELS[name], field])} />
      <FieldSection title="Valores e tributação" fields={Object.entries(action.financials).map(([name, field]) => [FINANCIAL_LABELS[name], field])} />
    </div>
  )
}

function ConfidenceGuide() {
  return (
    <section className="confidence-guide" aria-labelledby="confidence-guide-title">
      <div className="confidence-guide__intro">
        <h4 id="confidence-guide-title">Como a confiança é definida</h4>
        <p>Cada campo mantém uma classificação categórica baseada em origem, leitura e validação. A porcentagem do documento agrega somente os campos materiais esperados para seu tipo de evento.</p>
      </div>
      <div className="confidence-levels">
        <article className="confidence-level confidence-level--high">
          <strong>Confiança alta</strong>
          <ul><li>Texto nativo com evidência literal;</li><li>Base oficial com correspondência exata;</li><li>Cálculo aprovado por todas as regras;</li><li>Dado não aplicável ou ausência declarada com evidência.</li></ul>
        </article>
        <article className="confidence-level confidence-level--medium">
          <strong>Confiança média</strong>
          <ul><li>Evidência obtida por OCR;</li><li>Base oficial sem correspondência exata;</li><li>Valor calculado sem todas as regras aprovadas;</li><li>Ausência declarada sem trecho literal.</li></ul>
        </article>
        <article className="confidence-level confidence-level--low">
          <strong>Confiança baixa</strong>
          <ul><li>Campo ambíguo, conflitante ou ilegível;</li><li>Origem desconhecida ou ausência de evidência;</li><li>Pelo menos uma regra relacionada foi reprovada.</li></ul>
        </article>
      </div>
    </section>
  )
}

function AnalysisHistory({ record }: { record: DocumentRecord }) {
  const attempts = record.extraction_attempts || []
  return (
    <div className="tab-content history-content">
      <section className="overview-intro">
        <h4>Histórico técnico da análise</h4>
        <p>Use esta seção para investigar como o documento foi lido e quais regras sustentam a decisão. Ela não é necessária para a conferência cotidiana.</p>
      </section>

      {attempts.length > 0 && (
        <section className="history-section">
          <h4>Tentativas de leitura e extração</h4>
          <div>{attempts.map((attempt, index) => (
            <div className="validation-row" key={`${attempt.strategy}:${index}`}>
              <ValidationState status={attempt.outcome === 'SUFFICIENT' ? 'PASS' : attempt.outcome === 'ERROR' ? 'FAIL' : 'WARN'} />
              <span>
                <strong>{EXTRACTION_STRATEGY_LABELS[attempt.strategy] || attempt.strategy}</strong>
                <small>{attempt.model ? `Modelo utilizado: ${attempt.model}. ` : ''}{attempt.error || (attempt.unresolved_fields.length ? `Campos ainda pendentes: ${attempt.unresolved_fields.map(fieldPathLabel).join(', ')}.` : 'Todos os campos críticos foram resolvidos.')}</small>
              </span>
            </div>
          ))}</div>
        </section>
      )}

      <section className="history-section">
        <h4>Regras verificadas <span>{record.validations.length}</span></h4>
        <div>{record.validations.map((validation, index) => <ValidationRow key={`${validation.rule}:${index}`} validation={validation} />)}</div>
      </section>
    </div>
  )
}

function ClassificationAudit({ evidence, conflicts }: { evidence: ClassificationSignal[]; conflicts: ClassificationConflict[] }) {
  if (!evidence.length && !conflicts.length) return null
  return (
    <details className="classification-audit">
      <summary><span>Por que este tipo de evento foi escolhido?</span><small>{evidence.length} evidência(s){conflicts.length ? ` e ${conflicts.length} conflito(s)` : ''}</small></summary>
      <div>
        {evidence.map((item, index) => <ClassificationSignal item={item} key={`${item.supports}:${item.source?.page}:${index}`} />)}
        {conflicts.map((conflict, index) => (
          <article className="classification-audit__conflict" key={`${conflict.description}:${index}`}>
            <strong>Conflito encontrado</strong>
            <p>{conflict.description}</p>
            {(conflict.signals || []).map((item, signalIndex) => <ClassificationSignal item={item} key={`${item.supports}:${signalIndex}`} />)}
          </article>
        ))}
      </div>
    </details>
  )
}

function ClassificationSignal({ item }: { item: ClassificationSignal }) {
  return (
    <article>
      <strong>Indica: {EVENT_TYPE_LABELS[item.supports] || item.supports}</strong>
      <p>{item.rationale}</p>
      {item.source && <blockquote>“{item.source.evidence}”<cite>Página {item.source.page}, leitura por {methodLabel(item.source.extraction_method).toLowerCase()}</cite></blockquote>}
    </article>
  )
}

function ReferenceValidation({ reference }: { reference: ReferenceValidationType }) {
  const canonical = reference.reference_record
  return (
    <details className="reference-card" open={!reference.exact_match}>
      <summary>
        <span className="reference-icon"><Icon name="database" size={18} /></span>
        <span><strong>Conferência com a base oficial</strong><small>{reference.exact_match ? `Ativo confirmado por ${reference.matched_by.map(matchFieldLabel).join(', ')}` : 'A identidade do ativo precisa de atenção'}</small></span>
        <span className={`reference-result reference-result--${reference.exact_match ? 'ok' : 'attention'}`}>{reference.exact_match ? 'Confirmado' : 'Verificar'}</span>
      </summary>
      <div className="reference-card__body">
        {canonical ? <dl className="canonical-grid">
          <ReferenceValue label="Emissor" value={canonical.issuer} />
          <ReferenceValue label="CNPJ" value={canonical.cnpj} />
          <ReferenceValue label="ISIN" value={canonical.isin} />
          <ReferenceValue label="Código de negociação" value={canonical.ticker} />
          <ReferenceValue label="Classe do ativo" value={canonical.share_class} />
          <ReferenceValue label="Segmento de listagem" value={canonical.listing_segment} />
          <ReferenceValue label="Status do ativo" value={canonical.status} />
        </dl> : <p>Nenhum registro da base oficial foi confirmado com os identificadores extraídos.</p>}
        {reference.conflicts.length > 0 && <div className="reference-conflicts"><h5>Diferenças encontradas</h5>{reference.conflicts.map((conflict) => <div key={`${conflict.code}:${conflict.field}`}><strong>{matchFieldLabel(conflict.field)}</strong><span>Na base oficial: {formatPrimitive(conflict.expected)}</span><span>No documento: {formatPrimitive(conflict.observed)}</span></div>)}</div>}
        {reference.possible_matches.length > 0 && <div className="possible-matches"><h5>Registros parecidos, ainda não confirmados</h5>{reference.possible_matches.map((match) => <p key={match.isin}>{match.issuer}, {match.ticker}, {match.isin}</p>)}</div>}
      </div>
    </details>
  )
}

function ReferenceValue({ label, value }: { label: string; value: string | null | undefined }) {
  return <div><dt>{label}</dt><dd>{value || 'Não informado'}</dd></div>
}

function FieldSection({ title, fields }: { title: string; fields: Array<[string, DisplayField]> }) {
  const visible = fields.filter(([, field]) => field)
  return (
    <section className="field-section">
      <div className="field-section__heading"><h4>{title}</h4><span>{visible.length} {visible.length === 1 ? 'campo' : 'campos'}</span></div>
      <div className="field-table">
        <div className="field-table__head" aria-hidden="true"><span>Campo</span><span>Valor</span><span>Confiança</span><span>Situação</span></div>
        {visible.map(([label, field]) => <FieldRow field={field} key={label} label={label} />)}
      </div>
    </section>
  )
}

function FieldRow({ label, field }: { label: string; field: DisplayField }) {
  return (
    <details className="field-row">
      <summary>
        <span className="field-name"><strong>{label}</strong><small>{FIELD_HELP[label]}</small></span>
        <span className={field.value == null ? 'field-value field-value--empty' : 'field-value'}>{formatValue(field.value, label)}</span>
        <span className={`confidence confidence--${field.confidence.toLowerCase()}`}>{CONFIDENCE_LABELS[field.confidence] || field.confidence}</span>
        <span className="field-origin">{FIELD_STATUS_LABELS[field.status] || field.status}</span>
      </summary>
      <div className="field-evidence">
        <div className="confidence-reason"><strong>Como interpretar</strong><span>{confidenceReason(field)}</span></div>
        <p className="field-provenance">Origem do valor: <strong>{ORIGIN_LABELS[field.origin] || field.origin}</strong></p>
        {field.sources.length ? field.sources.map((source, index) => <blockquote key={`${source.page}:${index}`}>“{source.evidence}”<cite>Página {source.page}, leitura por {methodLabel(source.extraction_method).toLowerCase()}</cite></blockquote>) : <p>Não há trecho documental associado. Isso é esperado para valores trazidos da base oficial ou calculados por regra.</p>}
        {field.validation.length > 0 && <div className="field-validations"><strong>Regras relacionadas a este campo</strong>{field.validation.map((validation, index) => <ValidationRow compact key={`${validation.rule}:${index}`} validation={validation} />)}</div>}
      </div>
    </details>
  )
}

function ValidationRow({ validation, compact = false }: { validation: ValidationResult; compact?: boolean }) {
  return (
    <div className={compact ? 'validation-row validation-row--compact' : 'validation-row'}>
      <ValidationState status={validation.status} />
      <span>
        <strong>{VALIDATION_RULE_LABELS[validation.rule] || humanizeCode(validation.rule)}</strong>
        {(validation.expected != null || validation.observed != null) && <span className="validation-comparison">
          {validation.expected != null && <span>Esperado: <strong>{formatPrimitive(validation.expected)}</strong></span>}
          {validation.observed != null && <span>Encontrado: <strong>{formatPrimitive(validation.observed)}</strong></span>}
        </span>}
      </span>
    </div>
  )
}

function ValidationState({ status }: { status: ValidationStatus }) {
  return <span className={`validation-state validation-state--${status.toLowerCase()}`}>{VALIDATION_STATUS_LABELS[status] || status}</span>
}

function ControlItem({ label, detail, ok, neutral = false }: { label: string; detail: string; ok: boolean; neutral?: boolean }) {
  const state = ok ? 'ok' : neutral ? 'neutral' : 'attention'
  return <div className={`control-item control-item--${state}`}><span>{ok ? <Icon name="check" size={15} /> : '!'}</span><div><strong>{label}</strong><small>{detail}</small></div></div>
}

function StatusPill({ status }: { status: ProcessingStatus }) {
  return <span className={`status-pill status-pill--${status.toLowerCase()}`}>{STATUS_LABELS[status] || status}</span>
}

function confidenceReason(field: DisplayField): string {
  if (field.validation.some((validation) => validation.status === 'FAIL')) return 'Uma regra ligada a este campo foi reprovada. Confira o valor antes de utilizá-lo.'
  if (['AMBIGUOUS', 'CONFLICT', 'UNREADABLE', 'UNKNOWN'].includes(field.status)) return `A situação “${FIELD_STATUS_LABELS[field.status] || field.status}” impede o aceite automático.`
  if (field.status === 'NOT_DISCLOSED') return field.sources.length ? 'O próprio documento informa que o dado ainda não foi divulgado.' : 'O dado está pendente e não possui evidência literal associada.'
  if (field.origin === 'REFERENCE') return 'O valor veio da base oficial após a confirmação da identidade do ativo.'
  if (field.origin === 'DERIVED') return 'O valor foi calculado por uma regra determinística e passou pelas validações relacionadas.'
  if (field.sources.some((source) => source.extraction_method === 'OCR')) return 'O valor foi encontrado em uma página digitalizada por OCR, o que reduz a confiança para média.'
  if (field.origin === 'DOCUMENT' && field.sources.length) return 'O valor possui um trecho literal encontrado diretamente no texto do documento.'
  return 'Não há evidência suficiente para aumentar a confiança deste campo.'
}

function reasonText(reason: RoutingReason): string {
  return REASON_LABELS[reason.code] || reason.message || 'O registro precisa de conferência.'
}

function methodLabel(method: ExtractionMethod): string {
  return EXTRACTION_METHOD_LABELS[method] || method
}

function matchFieldLabel(field: string): string {
  return MATCH_FIELD_LABELS[field] || humanizeCode(field)
}

function fieldPathLabel(path: string): string {
  return FIELD_PATH_LABELS[path] || humanizeCode(path.split('.').at(-1))
}

function humanizeCode(value: unknown): string {
  return String(value || '').replaceAll('_', ' ').toLowerCase()
}

function formatPrimitive(value: JsonValue | undefined): string {
  if (value == null) return 'Não informado'
  if (typeof value === 'object') return JSON.stringify(value)
  if (typeof value === 'string' && EVENT_TYPE_LABELS[value]) return EVENT_TYPE_LABELS[value]
  if (/^\d{4}-\d{2}-\d{2}$/.test(String(value))) {
    const [year, month, day] = String(value).split('-')
    return `${day}/${month}/${year}`
  }
  return String(value)
    .replace('approval_date <= record_date', 'aprovação anterior ou igual à data com')
    .replace('record_date < ex_date', 'data com anterior à data ex')
    .replace('payment_date >= record_date', 'pagamento posterior ou igual à data com')
    .replace('ISO 4217 currency code', 'código de moeda no padrão ISO 4217')
}

function downloadRecord(record: DocumentRecord) {
  const blob = new Blob([`${JSON.stringify(record, null, 2)}\n`], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${record.source_document.file_name.replace(/\.pdf$/i, '')}.json`
  link.click()
  URL.revokeObjectURL(url)
}

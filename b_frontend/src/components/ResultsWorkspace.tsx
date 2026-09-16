import { useEffect, useRef, useState } from 'react'

import { getDocumentFileUrl } from '../api'
import { REASON_LABELS, STATUS_LABELS } from '../constants'
import { DocumentThumbnail } from './DocumentThumbnail'
import { Icon } from './Icon'
import { RecordDetail } from './RecordDetail'
import type { BatchUploadResponse, ExceptionReportDocument, ProcessingStatus, RoutingReason } from '../types'

interface ResultsWorkspaceProps {
  result: BatchUploadResponse
}

export function ResultsWorkspace({ result }: ResultsWorkspaceProps) {
  const [activeIndex, setActiveIndex] = useState(0)
  const resultGridRef = useRef<HTMLDivElement>(null)
  const summary = result.report.summary
  const activeDocument = result.report.documents[activeIndex]
  const activeRecord = result.records.find(
    (record) => record.document_id === activeDocument?.document_id,
  )
  const exceptions = result.report.documents.filter(
    (document) => document.processing_status !== 'ACCEPTED',
  )

  useEffect(() => {
    const firstException = result.report.documents.findIndex(
      (document) => document.processing_status !== 'ACCEPTED',
    )
    setActiveIndex(firstException >= 0 ? firstException : 0)
  }, [result])

  function openDocument(index: number) {
    setActiveIndex(index)
    window.requestAnimationFrame(() => {
      const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      resultGridRef.current?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
    })
  }

  return (
    <section className="results" aria-labelledby="results-title">
      <div className="results-heading">
        <div><p className="section-context">Análise concluída</p><h2 id="results-title">Confira o resultado</h2><p>Comece pelos documentos que precisam de atenção. Depois, abra os dados de cada registro para conferir as evidências.</p></div>
      </div>
      <div className="batch-overview">
        <div className="batch-total"><strong>{summary.processed}</strong><span>{summary.processed === 1 ? 'documento analisado' : 'documentos analisados'}</span></div>
        <div className="batch-counts" aria-label="Resumo do lote">
          <SummaryValue label="Aceitos" value={summary.accepted} tone="accepted" />
          <SummaryValue label="Para revisar" value={summary.human_review} tone="review" />
          <SummaryValue label="Aguardando informação" value={summary.pending_information} tone="pending" />
          <SummaryValue label="Com falha" value={summary.failed} tone="failed" />
        </div>
        <button className="report-action" onClick={() => downloadJson('relatorio_de_excecoes.json', result.report)} type="button"><Icon name="download" size={16} />Baixar relatório do lote</button>
      </div>

      {exceptions.length > 0 && <section className="attention-queue" aria-labelledby="attention-title">
        <header><div><Icon name="alert" size={19} /><span><strong id="attention-title">Comece por estes documentos</strong><small>{exceptions.length === 1 ? '1 documento precisa de uma ação' : `${exceptions.length} documentos precisam de uma ação`}</small></span></div></header>
        <div>{exceptions.map((document) => (
          <button key={document.document_id} onClick={() => openDocument(result.report.documents.indexOf(document))} type="button">
            <StatusDot status={document.processing_status} />
            <span><strong>{document.file_name}</strong><small>{document.exceptions.map(exceptionText).join(' ') || STATUS_LABELS[document.processing_status]}</small></span>
            <span>Abrir documento</span>
          </button>
        ))}</div>
      </section>}

      <div className="result-grid" ref={resultGridRef}>
        <nav className="document-nav" aria-label="Documentos processados">
          <div className="document-nav__heading"><strong>Escolha um documento</strong><span>O resultado aparece ao lado</span></div>
          {result.report.documents.map((document, index) => (
            <button
              className={index === activeIndex ? 'document-link document-link--active' : 'document-link'}
              key={document.document_id}
              onClick={() => setActiveIndex(index)}
              type="button"
            >
              <span className="document-number">{index + 1}</span>
              <span><strong>{document.file_name}</strong><small>{STATUS_LABELS[document.processing_status]}</small></span>
              <StatusDot status={document.processing_status} />
            </button>
          ))}
        </nav>
        <div className="record-detail">
          {activeRecord ? <RecordDetail record={activeRecord} /> : <FailureDetail document={activeDocument} />}
        </div>
      </div>
    </section>
  )
}

function FailureDetail({ document }: { document?: ExceptionReportDocument }) {
  const documentUrl = document?.document_id ? getDocumentFileUrl(document.document_id) : null
  return (
    <div className="failure-detail">
      {documentUrl && document && <DocumentThumbnail fileName={document.file_name} url={documentUrl} />}
      <Icon name="alert" size={28} />
      <h3>O documento não foi processado</h3>
      <p>{document?.exceptions?.[0] ? exceptionText(document.exceptions[0]) : 'Consulte o histórico técnico para identificar a causa.'}</p>
      {documentUrl && <a className="secondary-action" href={documentUrl} rel="noreferrer" target="_blank"><Icon name="eye" size={17} />Ver documento original</a>}
    </div>
  )
}

function SummaryValue({ label, value, tone }: { label: string; value: number; tone: 'accepted' | 'review' | 'pending' | 'failed' }) {
  return <div className={`summary-value summary-value--${tone}`}><span className={`status-dot status-dot--summary-${tone}`} /><strong>{value}</strong><span>{label}</span></div>
}

function StatusDot({ status }: { status: ProcessingStatus }) {
  return <span aria-label={STATUS_LABELS[status]} className={`status-dot status-dot--${status.toLowerCase()}`} />
}

function downloadJson(name: string, payload: unknown) {
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}

function exceptionText(exception: RoutingReason): string {
  return REASON_LABELS[exception.code] || exception.message || 'O documento precisa de atenção.'
}

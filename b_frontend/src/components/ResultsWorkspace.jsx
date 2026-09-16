import { useEffect, useState } from 'react'

import { getDocumentFileUrl } from '../api'
import { STATUS_LABELS } from '../constants'
import { Icon } from './Icon'
import { RecordDetail } from './RecordDetail'

export function ResultsWorkspace({ result }) {
  const [activeIndex, setActiveIndex] = useState(0)
  const summary = result.report.summary
  const activeDocument = result.report.documents[activeIndex]
  const activeRecord = result.records.find(
    (record) => record.document_id === activeDocument?.document_id,
  )
  const exceptions = result.report.documents.filter(
    (document) => document.processing_status !== 'ACCEPTED',
  )

  useEffect(() => setActiveIndex(0), [result])

  return (
    <section className="results" aria-labelledby="results-title">
      <div className="results-heading">
        <div><p className="section-context">Asset Servicing · lote processado</p><h2 id="results-title">Mesa de controle</h2></div>
        <button className="report-action" onClick={() => downloadJson('exception_report.json', result.report)} type="button"><Icon name="download" size={16} />Baixar relatório</button>
      </div>
      <div className="summary-strip">
        <SummaryValue label="Aceitos" value={summary.accepted} tone="accepted" />
        <SummaryValue label="Revisão humana" value={summary.human_review} tone="review" />
        <SummaryValue label="Informação pendente" value={summary.pending_information} tone="pending" />
        <SummaryValue label="Falhas" value={summary.failed} tone="failed" />
      </div>

      <details className="batch-report">
        <summary><span>Relatório curto de exceções</span><small>{summary.human_review + summary.pending_information + summary.failed} item(ns) requerem atenção</small></summary>
        <div>{exceptions.map((document) => (
          <button key={document.document_id} onClick={() => setActiveIndex(result.report.documents.indexOf(document))} type="button">
            <StatusDot status={document.processing_status} />
            <span><strong>{document.file_name}</strong><small>{document.exceptions.map((exception) => exception.message).join(' · ') || STATUS_LABELS[document.processing_status]}</small></span>
            <span>{STATUS_LABELS[document.processing_status]}</span>
          </button>
        ))}{exceptions.length === 0 && <p className="batch-report__empty">Nenhuma exceção registrada neste lote.</p>}</div>
      </details>

      <div className="result-grid">
        <nav className="document-nav" aria-label="Documentos processados">
          <div className="document-nav__heading"><strong>Documentos</strong><span>{summary.processed}</span></div>
          {result.report.documents.map((document, index) => (
            <button
              className={index === activeIndex ? 'document-link document-link--active' : 'document-link'}
              key={document.document_id}
              onClick={() => setActiveIndex(index)}
              type="button"
            >
              <Icon name="file" />
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

function FailureDetail({ document }) {
  return (
    <div className="failure-detail">
      <Icon name="alert" size={28} />
      <h3>O documento não foi processado</h3>
      <p>{document?.exceptions?.[0]?.message || 'Consulte os logs do backend.'}</p>
      {document?.document_id && <a className="secondary-action" href={getDocumentFileUrl(document.document_id)} rel="noreferrer" target="_blank"><Icon name="eye" size={17} />Ver documento original</a>}
    </div>
  )
}

function SummaryValue({ label, value, tone }) {
  return <div className={`summary-value summary-value--${tone}`}><strong>{value}</strong><span>{label}</span></div>
}

function StatusDot({ status }) {
  return <span aria-label={STATUS_LABELS[status]} className={`status-dot status-dot--${status.toLowerCase()}`} />
}

function downloadJson(name, payload) {
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}

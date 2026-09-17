import { useEffect, useRef, useState } from 'react'

import { getDocumentFileUrl } from '../api'
import { STATUS_LABELS } from '../constants'
import { summarizeRoutingReasons } from '../routingReasons'
import { DocumentThumbnail } from './DocumentThumbnail'
import { Icon } from './Icon'
import { RecordDetail } from './RecordDetail'
import type { BatchUploadResponse, ExceptionReportDocument, ProcessingStatus } from '../types'

interface ResultsWorkspaceProps {
  onReevaluate: (documentId: string) => void
  reevaluatingDocumentId: string | null
  result: BatchUploadResponse
}

export function ResultsWorkspace({ onReevaluate, reevaluatingDocumentId, result }: ResultsWorkspaceProps) {
  const [activeIndex, setActiveIndex] = useState(0)
  const resultGridRef = useRef<HTMLDivElement>(null)
  const summary = result.report.summary
  const hasAnalyzedDocuments = result.report.documents.length > 0
  const activeDocument = result.report.documents[activeIndex]
  const activeRecord = result.records.find(
    (record) => record.document_id === activeDocument?.document_id,
  )
  const exceptions = result.report.documents.filter(
    (document) => document.processing_status !== 'ACCEPTED',
  )
  const reusedUploads = result.uploads?.filter(
    (upload) => upload.disposition === 'REUSED',
  ) ?? []
  const otherUploadNotices = result.uploads?.filter(
    (upload) => !['PROCESSED', 'REUSED'].includes(upload.disposition),
  ) ?? []

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
      {reusedUploads.length > 0 && (
        <section
          aria-label="Documento analisado anteriormente"
          aria-live="polite"
          className="reuse-notice reuse-notice--prominent"
          role="status"
        >
          <span className="reuse-notice__icon"><Icon name="database" size={22} /></span>
          <div>
            <span className="reuse-notice__eyebrow">Resultado já existente</span>
            <strong>{reusedUploads.length === 1 ? 'Este documento já havia sido analisado' : 'Estes documentos já haviam sido analisados'}</strong>
            {reusedUploads.map((upload) => (
              <p key={`${upload.sha256}:${upload.file_name}`}>
                Você enviou <b>{upload.file_name}</b>.
                {upload.existing_file_name && upload.existing_file_name !== upload.file_name
                  ? <> O documento já está salvo como <b>{upload.existing_file_name}</b>.</>
                  : null}
                {' '}{upload.message}
              </p>
            ))}
          </div>
        </section>
      )}
      <div className="results-heading">
        <div><p className="section-context">{hasAnalyzedDocuments ? 'Análise concluída' : 'Envio recebido'}</p><h2 id="results-title">{hasAnalyzedDocuments ? 'Confira o resultado' : 'Nenhum processamento duplicado foi iniciado'}</h2><p>{hasAnalyzedDocuments ? 'Comece pelos documentos que precisam de atenção. Depois, abra os dados de cada registro para conferir as evidências.' : 'O conteúdo informado já está em processamento. Tente novamente após a conclusão para reutilizar o resultado.'}</p></div>
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

      {otherUploadNotices.length > 0 && (
        <section className="upload-notice" aria-label="Informações sobre o envio">
          <Icon name="database" size={18} />
          <div>
            <strong>Informações sobre o envio</strong>
            {otherUploadNotices.map((upload) => (
              <p key={`${upload.sha256}:${upload.file_name}`}>{upload.file_name}: {upload.message}</p>
            ))}
          </div>
        </section>
      )}

      {exceptions.length > 0 && <section className="attention-queue" aria-labelledby="attention-title">
        <header><div><Icon name="alert" size={19} /><span><strong id="attention-title">Comece por estes documentos</strong><small>{exceptions.length === 1 ? '1 documento precisa de uma ação' : `${exceptions.length} documentos precisam de uma ação`}</small></span></div></header>
        <div>{exceptions.map((document) => (
          <button key={document.document_id} onClick={() => openDocument(result.report.documents.indexOf(document))} type="button">
            <StatusDot status={document.processing_status} />
            <span><strong>{document.file_name}</strong><small>{summarizeRoutingReasons(document.exceptions).join(' ') || STATUS_LABELS[document.processing_status]}</small></span>
            <span>Abrir documento</span>
          </button>
        ))}</div>
      </section>}

      {hasAnalyzedDocuments && <div className="result-grid" ref={resultGridRef}>
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
          {activeRecord ? (
            <RecordDetail
              onReevaluate={onReevaluate}
              record={activeRecord}
              reevaluating={reevaluatingDocumentId === activeRecord.document_id}
            />
          ) : <FailureDetail document={activeDocument} />}
        </div>
      </div>}
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
      <p>{document?.exceptions?.length ? summarizeRoutingReasons(document.exceptions)[0] : 'Consulte o histórico técnico para identificar a causa.'}</p>
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

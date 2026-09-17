import { useEffect, useState } from 'react'

import { getHealth, reevaluateDocument, uploadDocuments } from './api'
import { ResultsWorkspace } from './components/ResultsWorkspace'
import { Topbar } from './components/Topbar'
import { TracePreview } from './components/TracePreview'
import { UploadPanel } from './components/UploadPanel'
import type {
  BatchUploadResponse,
  ExceptionReportDocument,
  HealthResponse,
  ProcessingStatus,
} from './types'

type AppState = 'idle' | 'processing' | 'done' | 'error'

const DEFAULT_FONT_SCALE = 108
const MIN_FONT_SCALE = 92
const MAX_FONT_SCALE = 124
const FONT_SCALE_STEP = 8
const FONT_SCALE_STORAGE_KEY = 'fintrace-font-scale'

function initialFontScale() {
  try {
    const storedScale = Number.parseInt(localStorage.getItem(FONT_SCALE_STORAGE_KEY) ?? '', 10)
    return Number.isFinite(storedScale) && storedScale >= MIN_FONT_SCALE && storedScale <= MAX_FONT_SCALE
      ? storedScale
      : DEFAULT_FONT_SCALE
  } catch {
    return DEFAULT_FONT_SCALE
  }
}

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [state, setState] = useState<AppState>('idle')
  const [error, setError] = useState('')
  const [result, setResult] = useState<BatchUploadResponse | null>(null)
  const [reevaluatingDocumentId, setReevaluatingDocumentId] = useState<string | null>(null)
  const [fontScale, setFontScale] = useState(initialFontScale)

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth({
      status: 'offline',
      provider: '',
      provider_configured: false,
      golden_records_available: false,
      database_configured: false,
    }))
  }, [])

  useEffect(() => {
    document.documentElement.style.fontSize = `${fontScale}%`
    try {
      localStorage.setItem(FONT_SCALE_STORAGE_KEY, String(fontScale))
    } catch {
      // A preferência continua ativa na sessão quando o armazenamento está bloqueado.
    }
  }, [fontScale])

  function addFiles(incoming: FileList) {
    const incomingFiles = Array.from(incoming)
    const pdfs = incomingFiles.filter(
      (file) => file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf'),
    )
    setFiles((current) => {
      const known = new Set(current.map((file) => `${file.name}:${file.size}`))
      return [...current, ...pdfs.filter((file) => !known.has(`${file.name}:${file.size}`))]
    })
    setError(pdfs.length === incomingFiles.length ? '' : 'Somente arquivos PDF foram adicionados.')
  }

  function removeFile(index: number) {
    setFiles((current) => current.filter((_, item) => item !== index))
  }

  function decreaseFontScale() {
    setFontScale((current) => Math.max(MIN_FONT_SCALE, current - FONT_SCALE_STEP))
  }

  function increaseFontScale() {
    setFontScale((current) => Math.min(MAX_FONT_SCALE, current + FONT_SCALE_STEP))
  }

  async function processFiles() {
    if (!files.length) return
    setState('processing')
    setError('')
    try {
      const response = await uploadDocuments(files)
      setResult((current) => mergeBatchResults(current, response))
      setFiles([])
      setState('done')
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível processar os documentos.')
      setState('error')
    }
  }

  async function reevaluate(documentId: string) {
    setReevaluatingDocumentId(documentId)
    setError('')
    try {
      const response = await reevaluateDocument(documentId)
      setResult((current) => mergeBatchResults(current, response))
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível reavaliar o documento.')
    } finally {
      setReevaluatingDocumentId(null)
    }
  }

  return (
    <div className="app-shell">
      <Topbar
        fontScale={fontScale}
        health={health}
        maximumFontScale={MAX_FONT_SCALE}
        minimumFontScale={MIN_FONT_SCALE}
        onDecreaseFont={decreaseFontScale}
        onIncreaseFont={increaseFontScale}
        onResetFont={() => setFontScale(DEFAULT_FONT_SCALE)}
      />
      <main id="top">
        <section className="workbench" aria-labelledby="page-title">
          <UploadPanel error={error} files={files} onAddFiles={addFiles} onProcess={processFiles} onRemoveFile={removeFile} state={state} />
          <TracePreview state={state} hasResult={Boolean(result)} />
        </section>
        {result ? <ResultsWorkspace onReevaluate={reevaluate} reevaluatingDocumentId={reevaluatingDocumentId} result={result} /> : (
          <section className="empty-guidance" aria-label="Como o FinTrace trabalha">
            <span>Leitura do documento</span>
            <span>Conferência automática</span>
            <span>Decisão explicada</span>
          </section>
        )}
      </main>
    </div>
  )
}

function mergeBatchResults(
  current: BatchUploadResponse | null,
  incoming: BatchUploadResponse,
): BatchUploadResponse {
  if (!current) return incoming

  const records = mergeByDocumentId(current.records, incoming.records)
  const documents = mergeByDocumentId(
    current.report.documents,
    incoming.report.documents,
  )

  return {
    records,
    report: {
      schema_version: incoming.report.schema_version,
      summary: summarizeDocuments(documents),
      documents,
    },
    // Upload messages describe the latest interaction. Keeping old messages
    // would make a reused-document warning look current after later uploads.
    uploads: incoming.uploads,
  }
}

function mergeByDocumentId<T extends { document_id: string }>(
  current: T[],
  incoming: T[],
): T[] {
  const replacements = new Map(incoming.map((item) => [item.document_id, item]))
  const currentIds = new Set(current.map((item) => item.document_id))
  return [
    ...current.map((item) => replacements.get(item.document_id) ?? item),
    ...incoming.filter((item) => !currentIds.has(item.document_id)),
  ]
}

function summarizeDocuments(documents: ExceptionReportDocument[]) {
  const count = (status: ProcessingStatus) => (
    documents.filter((document) => document.processing_status === status).length
  )
  return {
    processed: documents.length,
    accepted: count('ACCEPTED'),
    human_review: count('REVIEW_REQUIRED'),
    pending_information: count('PENDING_INFORMATION'),
    failed: count('FAILED'),
  }
}

export default App

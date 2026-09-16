import { useEffect, useState } from 'react'

import { getHealth, uploadDocuments } from './api'
import { ResultsWorkspace } from './components/ResultsWorkspace'
import { Topbar } from './components/Topbar'
import { TracePreview } from './components/TracePreview'
import { UploadPanel } from './components/UploadPanel'
import type { BatchUploadResponse, HealthResponse } from './types'

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
  const [fontScale, setFontScale] = useState(initialFontScale)

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth({
      status: 'offline',
      provider: '',
      provider_configured: false,
      golden_records_available: false,
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
      setResult(await uploadDocuments(files))
      setState('done')
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível processar os documentos.')
      setState('error')
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
        {result ? <ResultsWorkspace result={result} /> : (
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

export default App

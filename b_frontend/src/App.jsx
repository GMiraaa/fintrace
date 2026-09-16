import { useEffect, useState } from 'react'

import { getHealth, uploadDocuments } from './api'
import { ResultsWorkspace } from './components/ResultsWorkspace'
import { Topbar } from './components/Topbar'
import { TracePreview } from './components/TracePreview'
import { UploadPanel } from './components/UploadPanel'

function App() {
  const [health, setHealth] = useState(null)
  const [files, setFiles] = useState([])
  const [state, setState] = useState('idle')
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth({ status: 'offline' }))
  }, [])

  function addFiles(incoming) {
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

  function removeFile(index) {
    setFiles((current) => current.filter((_, item) => item !== index))
  }

  async function processFiles() {
    if (!files.length) return
    setState('processing')
    setError('')
    try {
      setResult(await uploadDocuments(files))
      setState('done')
    } catch (requestError) {
      setError(requestError.message)
      setState('error')
    }
  }

  return (
    <div className="app-shell">
      <Topbar health={health} />
      <main id="top">
        <section className="workbench" aria-labelledby="page-title">
          <UploadPanel error={error} files={files} onAddFiles={addFiles} onProcess={processFiles} onRemoveFile={removeFile} state={state} />
          <TracePreview state={state} hasResult={Boolean(result)} />
        </section>
        {result ? <ResultsWorkspace result={result} /> : (
          <section className="empty-guidance" aria-label="Como o FinTrace trabalha">
            <span>Interpretação contextual</span>
            <span>Validação determinística</span>
            <span>Revisão baseada em risco</span>
          </section>
        )}
      </main>
    </div>
  )
}

export default App

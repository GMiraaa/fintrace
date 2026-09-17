import { useEffect, useRef } from 'react'
import type { ChangeEvent, DragEvent } from 'react'

import { formatBytes } from '../utils/formatters'
import { Icon } from './Icon'

interface UploadPanelProps {
  error: string
  files: File[]
  onAddFiles: (files: FileList) => void
  onProcess: () => void
  onRemoveFile: (index: number) => void
  state: 'idle' | 'processing' | 'done' | 'error'
}

export function UploadPanel({ error, files, onAddFiles, onProcess, onRemoveFile, state }: UploadPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!files.length && inputRef.current) inputRef.current.value = ''
  }, [files.length])

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    onAddFiles(event.dataTransfer.files)
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files) onAddFiles(event.target.files)
  }

  return (
    <div className="intro-panel">
      <p className="section-context">Nova análise</p>
      <h1 id="page-title">Analise avisos de eventos corporativos</h1>
      <p className="intro-copy">
        Envie um ou mais PDFs. O FinTrace extrai os dados, confere o ativo e
        destaca somente o que precisa da sua atenção.
      </p>
      <div className="drop-zone" onDragOver={(event) => event.preventDefault()} onDrop={handleDrop}>
        <input ref={inputRef} accept="application/pdf,.pdf" id="pdf-input" multiple onChange={handleChange} type="file" />
        <Icon name="upload" size={24} />
        <div><strong>Solte os arquivos PDF aqui</strong><span>Até 20 MB por documento</span></div>
        <button className="text-button" onClick={() => inputRef.current?.click()} type="button">Selecionar PDFs</button>
      </div>
      {files.length > 0 && (
        <div className="file-queue" aria-label="Arquivos selecionados">
          {files.map((file, index) => (
            <div className="queued-file" key={`${file.name}:${file.size}`}>
              <Icon name="file" />
              <span><strong>{file.name}</strong><small>{formatBytes(file.size)}</small></span>
              <button aria-label={`Remover ${file.name}`} onClick={() => onRemoveFile(index)} type="button"><Icon name="close" size={17} /></button>
            </div>
          ))}
        </div>
      )}
      <button className="primary-action" disabled={!files.length || state === 'processing'} onClick={onProcess} type="button">
        {state === 'processing' ? <><span className="spinner" />Analisando documentos</> : files.length === 1 ? 'Analisar 1 documento' : `Analisar ${files.length} documentos`}
      </button>
      {error && <div className="error-message" role="alert"><Icon name="alert" />{error}</div>}
    </div>
  )
}

import { useRef } from 'react'

import { formatBytes } from '../utils/formatters'
import { Icon } from './Icon'

export function UploadPanel({ error, files, onAddFiles, onProcess, onRemoveFile, state }) {
  const inputRef = useRef(null)

  return (
    <div className="intro-panel">
      <p className="section-context">Asset Servicing · Controle de eventos</p>
      <h1 id="page-title">Documentos convertidos em decisões auditáveis.</h1>
      <p className="intro-copy">
        Processe avisos corporativos, valide identificadores e regras financeiras e
        concentre a atuação do operador apenas nas exceções materiais.
      </p>
      <div className="drop-zone" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); onAddFiles(event.dataTransfer.files) }}>
        <input ref={inputRef} accept="application/pdf,.pdf" id="pdf-input" multiple onChange={(event) => onAddFiles(event.target.files)} type="file" />
        <Icon name="upload" size={24} />
        <div><strong>Arraste os avisos para esta área</strong><span>ou escolha PDFs no seu computador</span></div>
        <button className="text-button" onClick={() => inputRef.current?.click()} type="button">Escolher arquivos</button>
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
        {state === 'processing' ? <><span className="spinner" />Processando documentos</> : 'Processar documentos'}
      </button>
      {error && <div className="error-message" role="alert"><Icon name="alert" />{error}</div>}
    </div>
  )
}

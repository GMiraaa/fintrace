import { Icon } from './Icon'

export function TracePreview({ state, hasResult }) {
  const active = state === 'processing'
  const stages = [
    ['Documento', 'Texto nativo ou OCR seletivo'],
    ['Referência', 'ISIN, CNPJ, ticker e classe'],
    ['Regras', 'Datas, valores e classificação'],
    ['Decisão', 'Aceite, acompanhamento ou revisão'],
  ]
  return (
    <div className={`trace-panel ${active ? 'trace-panel--active' : ''}`}>
      <div className="trace-heading">
        <span>{active ? 'Processamento em curso' : hasResult ? 'Rastro concluído' : 'Rastro de processamento'}</span>
        <small>4 controles</small>
      </div>
      <div className="trace-line">
        {stages.map(([title, description], index) => (
          <div className="trace-stage" key={title} style={{ '--stage': index }}>
            <span className="trace-node">{hasResult ? <Icon name="check" size={15} /> : index + 1}</span>
            <div><strong>{title}</strong><p>{description}</p></div>
          </div>
        ))}
      </div>
      <blockquote>
        “IA onde interpretação é necessária. Código onde determinismo é possível.”
      </blockquote>
    </div>
  )
}

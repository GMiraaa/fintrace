import { Icon } from './Icon'

export function TracePreview({ state, hasResult }) {
  const active = state === 'processing'
  const stages = [
    ['Ler o aviso', 'O sistema tenta texto nativo e OCR quando necessário.'],
    ['Confirmar o ativo', 'CNPJ, ISIN, código de negociação e classe são conferidos.'],
    ['Verificar os dados', 'Datas, valores e tipo de evento passam por regras.'],
    ['Orientar a ação', 'O resultado informa se você pode aceitar ou precisa revisar.'],
  ]
  return (
    <div className={`trace-panel ${active ? 'trace-panel--active' : ''}`}>
      <div className="trace-heading">
        <div><strong>{active ? 'Análise em andamento' : hasResult ? 'Análise concluída' : 'O que acontece depois do envio'}</strong><p>{active ? 'Mantenha esta página aberta enquanto os documentos são verificados.' : 'Quatro etapas produzem um registro pronto para conferência.'}</p></div>
      </div>
      <div className="trace-line">
        {stages.map(([title, description], index) => (
          <div className="trace-stage" key={title} style={{ '--stage': index }}>
            <span className="trace-node">{hasResult ? <Icon name="check" size={15} /> : index + 1}</span>
            <div><strong>{title}</strong><p>{description}</p></div>
          </div>
        ))}
      </div>
      <p className="trace-note"><Icon name="shield" size={17} />Nenhum valor é aceito apenas porque uma IA o sugeriu.</p>
    </div>
  )
}

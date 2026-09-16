export function Topbar({ health }) {
  const healthState = health?.status === 'ok' && !health.provider_configured
    ? 'pending'
    : health?.status || 'checking'
  const label = health?.status === 'ok' && health.provider_configured
    ? `Sistema disponível com IA ${health.provider}`
    : health?.status === 'ok'
      ? 'Sistema disponível em modo local'
      : health?.status === 'offline'
        ? 'Sistema indisponível'
        : 'Verificando sistema'

  return (
    <header className="topbar">
      <a className="brand" href="#top" aria-label="FinTrace — início">
        <span className="brand-mark" aria-hidden="true"><span /></span>
        <span><strong>FinTrace</strong><small>Controle de eventos corporativos</small></span>
      </a>
      <div className="topbar-meta">
        <span className="environment-label">Ambiente de operação</span>
        <div className={`health health--${healthState}`}>
          <span className="health-dot" />
          {label}
        </div>
      </div>
    </header>
  )
}

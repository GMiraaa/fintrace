export function Topbar({ health }) {
  const healthState = health?.status === 'ok' && !health.provider_configured
    ? 'pending'
    : health?.status || 'checking'
  const label = health?.status === 'ok' && health.provider_configured
    ? `API ativa · ${health.provider}`
    : health?.status === 'ok'
      ? 'API ativa · Python local · IA pendente'
      : health?.status === 'offline'
        ? 'API indisponível'
        : 'Verificando API'

  return (
    <header className="topbar">
      <a className="brand" href="#top" aria-label="FinTrace — início">
        <span className="brand-mark" aria-hidden="true"><span /></span>
        <span><strong>FinTrace</strong><small>Asset Servicing Intelligence</small></span>
      </a>
      <div className="topbar-meta">
        <span className="environment-label">Ambiente operacional</span>
        <div className={`health health--${healthState}`}>
          <span className="health-dot" />
          {label}
        </div>
      </div>
    </header>
  )
}

import type { HealthResponse } from '../types'

interface TopbarProps {
  fontScale: number
  health: HealthResponse | null
  maximumFontScale: number
  minimumFontScale: number
  onDecreaseFont: () => void
  onIncreaseFont: () => void
  onResetFont: () => void
}

export function Topbar({
  fontScale,
  health,
  maximumFontScale,
  minimumFontScale,
  onDecreaseFont,
  onIncreaseFont,
  onResetFont,
}: TopbarProps) {
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
        <span className="brand-logo-frame" aria-hidden="true">
          <img className="brand-logo" src="/brand/fintrace-logo.png" alt="" />
        </span>
        <small>Controle de eventos corporativos</small>
      </a>
      <div className="topbar-meta">
        <div className="font-controls" role="group" aria-label="Tamanho do texto da página">
          <span className="font-controls__label">Texto</span>
          <button
            aria-label="Diminuir o tamanho do texto"
            disabled={fontScale <= minimumFontScale}
            onClick={onDecreaseFont}
            title="Diminuir texto"
            type="button"
          >
            A−
          </button>
          <button
            aria-label={`Restaurar tamanho padrão do texto. Tamanho atual: ${fontScale}%`}
            className="font-controls__value"
            onClick={onResetFont}
            title="Restaurar tamanho padrão"
            type="button"
          >
            {fontScale}%
          </button>
          <button
            aria-label="Aumentar o tamanho do texto"
            disabled={fontScale >= maximumFontScale}
            onClick={onIncreaseFont}
            title="Aumentar texto"
            type="button"
          >
            A+
          </button>
        </div>
        <span className="environment-label">Ambiente de operação</span>
        <div className={`health health--${healthState}`}>
          <span className="health-dot" />
          {label}
        </div>
      </div>
    </header>
  )
}

import { Icon } from './Icon'

interface DocumentThumbnailProps {
  fileName: string
  onOpen?: () => void
  previewUrl: string
  url: string
}

export function DocumentThumbnail({ fileName, onOpen, previewUrl, url }: DocumentThumbnailProps) {
  return (
    <aside className="document-thumbnail" aria-label="Miniatura do documento original">
      <div className="document-thumbnail__page">
        <img alt="" aria-hidden="true" src={previewUrl} />
        {onOpen ? (
          <button onClick={onOpen} type="button"><Icon name="eye" size={16} />Ampliar documento</button>
        ) : (
          <a href={url} rel="noreferrer" target="_blank"><Icon name="eye" size={16} />Abrir documento</a>
        )}
      </div>
      <span title={fileName}>{fileName}</span>
    </aside>
  )
}

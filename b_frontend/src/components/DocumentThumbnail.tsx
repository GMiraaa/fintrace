import { Icon } from './Icon'

interface DocumentThumbnailProps {
  fileName: string
  onOpen?: () => void
  url: string
}

export function DocumentThumbnail({ fileName, onOpen, url }: DocumentThumbnailProps) {
  const previewUrl = `${url}#page=1&toolbar=0&navpanes=0&scrollbar=0&view=FitH`

  return (
    <aside className="document-thumbnail" aria-label="Miniatura do documento original">
      <div className="document-thumbnail__page">
        <iframe aria-hidden="true" src={previewUrl} tabIndex={-1} title="" />
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

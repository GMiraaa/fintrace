const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export function getDocumentFileUrl(documentId) {
  return `${API_BASE_URL}/api/documents/${encodeURIComponent(documentId)}/file`
}

export async function getHealth() {
  const response = await fetch(`${API_BASE_URL}/api/health`)
  if (!response.ok) throw new Error('Não foi possível acessar o backend.')
  return response.json()
}

export async function uploadDocuments(files) {
  const body = new FormData()
  files.forEach((file) => body.append('files', file))

  const response = await fetch(`${API_BASE_URL}/api/documents/upload`, {
    method: 'POST',
    body,
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(
      payload?.detail || 'O processamento falhou antes de produzir um resultado.',
    )
  }
  return payload
}

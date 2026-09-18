import type { BatchUploadResponse, HealthResponse } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export function getDocumentFileUrl(documentId: string): string {
  return `${API_BASE_URL}/api/documents/${encodeURIComponent(documentId)}/file`
}

export function getDocumentPreviewUrl(documentId: string): string {
  return `${API_BASE_URL}/api/documents/${encodeURIComponent(documentId)}/preview`
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`)
  if (!response.ok) throw new Error('Não foi possível acessar o serviço de processamento.')
  return response.json()
}

export async function uploadDocuments(files: File[]): Promise<BatchUploadResponse> {
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

export async function reevaluateDocument(documentId: string): Promise<BatchUploadResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/documents/${encodeURIComponent(documentId)}/reevaluate`,
    { method: 'POST' },
  )
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(payload?.detail || 'Não foi possível reavaliar o documento.')
  }
  return payload
}

export async function approveDocument(documentId: string): Promise<BatchUploadResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/documents/${encodeURIComponent(documentId)}/approve`,
    { method: 'POST' },
  )
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(payload?.detail || 'Não foi possível aprovar o documento.')
  }
  return payload
}

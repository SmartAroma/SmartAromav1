/** REST helpers — paths go through Vite proxy in dev. */

interface RequestOptions {
  token?: string
}

function headersFor(options?: RequestOptions): HeadersInit {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers.Authorization = `Bearer ${options.token}`
  return headers
}

async function parseError(response: Response): Promise<string> {
  const text = await response.text()
  if (!text) return response.statusText
  try {
    const data = JSON.parse(text) as { detail?: unknown }
    if (typeof data.detail === 'string') return data.detail
  } catch {
    // Plain text error body.
  }
  return text
}

export async function postJson<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
  const r = await fetch(path, {
    method: 'POST',
    headers: headersFor(options),
    body: JSON.stringify(body ?? {}),
  })
  if (!r.ok) {
    const t = await parseError(r)
    throw new Error(t || r.statusText)
  }
  return r.json() as Promise<T>
}

export async function getJson<T>(path: string, options?: RequestOptions): Promise<T> {
  const r = await fetch(path, {
    headers: options?.token ? { Authorization: `Bearer ${options.token}` } : undefined,
  })
  if (!r.ok) throw new Error(await parseError(r))
  return r.json() as Promise<T>
}

export async function deleteJson<T>(path: string, options?: RequestOptions): Promise<T> {
  const r = await fetch(path, {
    method: 'DELETE',
    headers: options?.token ? { Authorization: `Bearer ${options.token}` } : undefined,
  })
  if (!r.ok) throw new Error(await parseError(r))
  return r.json() as Promise<T>
}

export function statusWebSocketUrl(): string {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${location.host}/ws/status`
}

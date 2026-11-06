const API_BASE = import.meta.env.VITE_API_BASE ?? ''

type Params = Record<string, string | number | undefined>

async function request<T>(path: string, init?: RequestInit, params?: Params): Promise<T> {
  const url = new URL(API_BASE + path, window.location.origin)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) url.searchParams.set(key, String(value))
    }
  }
  const res = await fetch(url.toString(), init)
  if (!res.ok) {
    let detail = ''
    try {
      detail = (await res.json())?.detail ?? ''
    } catch {
      detail = await res.text()
    }
    throw new Error(`请求失败 (${res.status})${detail ? `：${detail}` : ''}`)
  }
  return (await res.json()) as T
}

export function apiGet<T>(path: string, params?: Params): Promise<T> {
  return request<T>(path, undefined, params)
}

export function apiPost<T>(path: string, params?: Params): Promise<T> {
  return request<T>(path, { method: 'POST' }, params)
}

export function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

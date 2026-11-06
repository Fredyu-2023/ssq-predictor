import { useCallback, useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api/client'
import type { SyncLogOut, SyncRunResult, SyncStatusItem, SyncStatusResponse } from '../types'

function formatTime(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function statusTone(status: string | null): string {
  if (status === 'success') return 'tag-success'
  if (status === 'failed') return 'tag-error'
  if (status === 'partial' || status === 'busy') return 'tag-warn'
  return 'tag-muted'
}

function shortError(message: string | null): string {
  if (!message) return '—'
  return message.length > 100 ? `${message.slice(0, 100)}…` : message
}

export function SyncPage() {
  const [items, setItems] = useState<SyncStatusItem[]>([])
  const [logs, setLogs] = useState<SyncLogOut[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [status, logList] = await Promise.all([
        apiGet<SyncStatusResponse>('/api/sync/status'),
        apiGet<SyncLogOut[]>('/api/sync/logs', { limit: 20 }),
      ])
      setItems(status.lotteries)
      setLogs(logList)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const timer = window.setInterval(load, 10000)
    return () => window.clearInterval(timer)
  }, [load])

  const handleSync = async () => {
    setSyncing(true)
    setMessage(null)
    setError(null)
    try {
      const result = await apiPost<SyncRunResult>('/api/sync/run')
      setMessage(
        `同步${result.status}：拉取 ${result.fetched_count} 条，新增 ${result.inserted_count} 条，` +
          `跳过 ${result.skipped_count} 条，最新期号 ${result.latest_issue ?? '—'}，耗时 ${result.elapsed_ms} ms`,
      )
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSyncing(false)
    }
  }

  const anySyncing = syncing || items.some((item) => item.syncing)

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h1>数据同步</h1>
          <p className="muted-text">
            后端启动时自动同步一次；本页可手动触发。状态每 10 秒自动刷新。
          </p>
        </div>
        <button className="btn btn-primary" disabled={anySyncing} onClick={handleSync}>
          {anySyncing ? '同步中…' : '立即同步'}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      {loading && <div className="card skeleton">正在读取同步状态…</div>}

      {!loading && (
        <div className="sync-grid">
          {items.map((item) => (
            <div className="card sync-card" key={item.type}>
              <div className="sync-card-head">
                <h2>{item.name}</h2>
                <span className={`tag ${statusTone(item.syncing ? 'busy' : item.last_sync_status)}`}>
                  {item.syncing ? '同步中' : item.last_sync_status ?? '未同步'}
                </span>
              </div>
              <div className="kv-list">
                <div>
                  <span>最新期号</span>
                  <b className="mono">{item.latest_issue ?? '—'}</b>
                </div>
                <div>
                  <span>开奖日期</span>
                  <b className="mono">{item.latest_date ?? '—'}</b>
                </div>
                <div>
                  <span>已入库</span>
                  <b>{item.total_count} 期</b>
                </div>
                <div>
                  <span>上次同步</span>
                  <b className="mono small">{formatTime(item.last_sync_at)}</b>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="card table-card">
        <div className="card-head">
          <h2>最近同步日志</h2>
          <span className="muted-text small">最多 20 条</span>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>彩种</th>
              <th>开始时间</th>
              <th>耗时 / 状态</th>
              <th className="num">拉取</th>
              <th className="num">新增</th>
              <th>错误信息</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}>
                <td className="mono muted-text">{log.id}</td>
                <td>{log.lottery_type}</td>
                <td className="mono muted-text">{formatTime(log.started_at)}</td>
                <td>
                  <span className={`tag ${statusTone(log.status)}`}>{log.status}</span>
                </td>
                <td className="num">{log.fetched_count}</td>
                <td className="num">{log.inserted_count}</td>
                <td className="error-cell" title={log.error_msg ?? undefined}>
                  {shortError(log.error_msg)}
                </td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr>
                <td colSpan={7} className="empty-cell">
                  暂无同步记录
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="disclaimer">
        数据源为福彩官方公开接口，仅供本机/局域网内个人使用。请勿高频请求。
      </p>
    </section>
  )
}

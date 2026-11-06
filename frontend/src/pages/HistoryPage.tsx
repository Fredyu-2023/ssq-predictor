import { useEffect, useState, type FormEvent } from 'react'
import { apiGet } from '../api/client'
import { Ball } from '../components/Ball'
import type { HistoryPageData, LotteryOut } from '../types'

const SIZE = 20

function formatMoney(value: number | null): string {
  if (value === null || value === undefined) return '—'
  if (value >= 1e8) return `${(value / 1e8).toFixed(2)} 亿`
  if (value >= 1e4) return `${(value / 1e4).toFixed(1)} 万`
  return value.toLocaleString('zh-CN')
}

export function HistoryPage() {
  const [lotteries, setLotteries] = useState<LotteryOut[]>([])
  const [lotteryType, setLotteryType] = useState('ssq')
  const [keyword, setKeyword] = useState('')
  const [applied, setApplied] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<HistoryPageData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    apiGet<LotteryOut[]>('/api/lotteries')
      .then((items) => {
        if (!cancelled) setLotteries(items)
      })
      .catch(() => {
        // 彩种列表失败不阻塞历史表格，使用默认 ssq
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    apiGet<HistoryPageData>('/api/history', {
      type: lotteryType,
      page,
      size: SIZE,
      q: applied || undefined,
    })
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [lotteryType, page, applied])

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.size)) : 1
  const activeName = lotteries.find((item) => item.type === lotteryType)?.name

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setApplied(keyword.trim())
    setPage(1)
  }

  const clearSearch = () => {
    setKeyword('')
    setApplied('')
    setPage(1)
  }

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h1>历史开奖</h1>
          <p className="muted-text">
            {activeName ?? lotteryType} · 按期号倒序，共 {data?.total ?? 0} 期，每页 {SIZE} 期。
            {applied && ` 当前搜索「${applied}」。`}
          </p>
        </div>
        {loading && <span className="tag tag-muted">加载中…</span>}
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="card history-toolbar">
        <div className="toolbar-left">
          <label className="field">
            <span>彩种</span>
            <select
              className="field-select"
              value={lotteryType}
              onChange={(event) => {
                setLotteryType(event.target.value)
                setPage(1)
              }}
            >
              {lotteries.length === 0 && <option value="ssq">双色球</option>}
              {lotteries.map((item) => (
                <option key={item.type} value={item.type}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <form className="search-form" onSubmit={submitSearch}>
            <input
              className="field-input search-input"
              type="search"
              placeholder="按期号 / 日期搜索，如 2026127 或 2026-11"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
            />
            <button className="btn" type="submit">
              搜索
            </button>
            {applied && (
              <button className="btn" type="button" onClick={clearSearch}>
                清除
              </button>
            )}
          </form>
        </div>
      </div>

      <div className="card table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>期号</th>
              <th>开奖日期</th>
              <th>红球</th>
              <th>蓝球</th>
              <th className="num">销售额</th>
              <th className="num">奖池</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((item) => (
              <tr key={item.issue}>
                <td className="mono">{item.issue}</td>
                <td className="mono muted-text">{item.draw_date}</td>
                <td>
                  <div className="ball-row">
                    {item.reds.map((n) => (
                      <Ball key={`r-${n}`} value={n} tone="red" size={30} />
                    ))}
                  </div>
                </td>
                <td>
                  <div className="ball-row">
                    {item.blues.map((n) => (
                      <Ball key={`b-${n}`} value={n} tone="blue" size={30} />
                    ))}
                  </div>
                </td>
                <td className="num">{formatMoney(item.sales_amount)}</td>
                <td className="num">{formatMoney(item.pool_balance)}</td>
              </tr>
            ))}
            {data?.items.length === 0 && (
              <tr>
                <td colSpan={6} className="empty-cell">
                  {applied ? '没有匹配的开奖记录，试试其他期号或日期' : '暂无数据，请到「数据同步」页触发同步'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="pager">
        <button className="btn" disabled={page <= 1} onClick={() => setPage(1)}>
          首页
        </button>
        <button className="btn" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
          上一页
        </button>
        <span className="pager-info">
          {page} / {totalPages}
        </span>
        <button
          className="btn"
          disabled={page >= totalPages}
          onClick={() => setPage((p) => p + 1)}
        >
          下一页
        </button>
        <button className="btn" disabled={page >= totalPages} onClick={() => setPage(totalPages)}>
          末页
        </button>
      </div>
    </section>
  )
}

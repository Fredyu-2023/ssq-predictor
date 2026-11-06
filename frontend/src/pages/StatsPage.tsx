import { useEffect, useMemo, useState } from 'react'
import { apiGet } from '../api/client'
import { BarChart, type BarItem } from '../components/BarChart'
import { DistributionBars } from '../components/DistributionBars'
import { Heatmap } from '../components/Heatmap'
import type { StatsOut } from '../types'

const RANGES: { key: string; label: string }[] = [
  { key: '30', label: '近 30 期' },
  { key: '100', label: '近 100 期' },
  { key: 'all', label: '全部' },
]

export function StatsPage() {
  const [range, setRange] = useState('30')
  const [data, setData] = useState<StatsOut | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    apiGet<StatsOut>('/api/stats', { type: 'ssq', range })
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
  }, [range])

  const hotSet = useMemo(() => new Set(data?.hot_red.map((x) => x.number) ?? []), [data])
  const coldSet = useMemo(() => new Set(data?.cold_red.map((x) => x.number) ?? []), [data])

  const redBars: BarItem[] =
    data?.red_freq.map((item) => ({
      key: item.number,
      label: String(item.number),
      value: item.count,
      tone: hotSet.has(item.number) ? 'hot' : coldSet.has(item.number) ? 'cold' : 'accent',
      hint: `红球 ${item.number}：${item.count} 次`,
    })) ?? []

  const blueBars: BarItem[] =
    data?.blue_freq.map((item) => ({
      key: item.number,
      label: String(item.number),
      value: item.count,
      tone: 'accent',
      hint: `蓝球 ${item.number}：${item.count} 次`,
    })) ?? []

  const sumBars: BarItem[] =
    data?.sum_distribution.map((item) => ({
      key: item.label,
      label: item.label,
      value: item.count,
      hint: `和值 ${item.label}：${item.count} 期`,
    })) ?? []

  const acBars: BarItem[] =
    data?.ac_distribution.map((item) => ({
      key: item.label,
      label: `AC ${item.label}`,
      value: item.count,
      hint: `AC=${item.label}：${item.count} 期`,
    })) ?? []

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h1>统计分析</h1>
          <p className="muted-text">频次、遗漏、比例结构与和值/AC 分布。窗口切换即时重算。</p>
        </div>
        <div className="segmented">
          {RANGES.map((item) => (
            <button
              key={item.key}
              className={`seg${range === item.key ? ' seg-active' : ''}`}
              onClick={() => setRange(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {loading && !data && <div className="card skeleton">统计计算中…</div>}

      {data && (
        <>
          <div className="summary-grid">
            <div className="card stat-card">
              <span className="stat-label">统计窗口</span>
              <strong className="stat-value">{data.window} 期</strong>
              <span className="muted-text mono">
                {data.first_issue ?? '—'} → {data.last_issue ?? '—'}
              </span>
            </div>
            <div className="card stat-card">
              <span className="stat-label">和值均值</span>
              <strong className="stat-value">{data.sum_stats.mean.toFixed(1)}</strong>
              <span className="muted-text">
                区间 {data.sum_stats.min} – {data.sum_stats.max}
              </span>
            </div>
            <div className="card stat-card">
              <span className="stat-label">AC 均值</span>
              <strong className="stat-value">{data.ac_avg.toFixed(2)}</strong>
              <span className="muted-text">号码算术复杂度</span>
            </div>
            <div className="card stat-card">
              <span className="stat-label">库内总期数</span>
              <strong className="stat-value">{data.draws_total}</strong>
              <span className="muted-text">全部已入库开奖</span>
            </div>
          </div>

          <div className="grid-2">
            <div className="card">
              <div className="card-head">
                <h2>红球频次</h2>
                <span className="tag tag-hot">热号 {data.hot_red.map((x) => x.number).join(' / ')}</span>
              </div>
              <BarChart items={redBars} height={170} />
              <p className="muted-text small">
                冷号（窗口内出现最少）：{data.cold_red.map((x) => `${x.number}(${x.count})`).join('、') || '—'}
              </p>
            </div>

            <div className="card">
              <div className="card-head">
                <h2>蓝球频次</h2>
                <span className="tag tag-muted">
                  热号 {data.hot_blue.map((x) => x.number).join(' / ') || '—'}
                </span>
              </div>
              <BarChart items={blueBars} height={170} />
              <p className="muted-text small">
                冷号：{data.cold_blue.map((x) => `${x.number}(${x.count})`).join('、') || '—'}
              </p>
            </div>
          </div>

          <div className="grid-2">
            <div className="card">
              <div className="card-head">
                <h2>红球遗漏</h2>
                <span className="muted-text small">数字越大 = 越久未出现</span>
              </div>
              <Heatmap cells={data.red_omission.map((x) => ({ number: x.number, value: x.omission }))} />
            </div>
            <div className="card">
              <div className="card-head">
                <h2>蓝球遗漏</h2>
                <span className="muted-text small">当前遗漏期数</span>
              </div>
              <Heatmap
                cells={data.blue_omission.map((x) => ({ number: x.number, value: x.omission }))}
                tone="blue"
              />
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <h2>连号统计</h2>
              <span className="muted-text small">相邻号码同现次数，按次数降序</span>
            </div>
            <div className="chip-row">
              {data.consecutive.length === 0 && <span className="muted-text">本窗口无连号</span>}
              {data.consecutive.slice(0, 16).map((item) => (
                <span className="chip chip-warm" key={item.pair}>
                  {item.pair}
                  <b>{item.count}</b>
                </span>
              ))}
            </div>
          </div>

          <div className="grid-3">
            <div className="card">
              <div className="card-head">
                <h2>奇偶比</h2>
                <span className="muted-text small">奇数 : 偶数</span>
              </div>
              <DistributionBars items={data.odd_even} total={data.window} tone="accent" />
            </div>
            <div className="card">
              <div className="card-head">
                <h2>大小比</h2>
                <span className="muted-text small">大 : 小（≤16 为小）</span>
              </div>
              <DistributionBars items={data.big_small} total={data.window} tone="red" />
            </div>
            <div className="card">
              <div className="card-head">
                <h2>区间比</h2>
                <span className="muted-text small">1–11 / 12–22 / 23–33</span>
              </div>
              <DistributionBars items={data.zone_ratio} total={data.window} tone="blue" />
            </div>
          </div>

          <div className="grid-2">
            <div className="card">
              <div className="card-head">
                <h2>和值分布</h2>
                <span className="muted-text small">按 10 宽分桶</span>
              </div>
              <BarChart items={sumBars} height={160} />
            </div>
            <div className="card">
              <div className="card-head">
                <h2>AC 值分布</h2>
                <span className="muted-text small">0（最规整）→ 10</span>
              </div>
              <BarChart items={acBars} height={160} />
            </div>
          </div>

          <p className="disclaimer">
            彩票为独立随机事件，历史数据不影响未来开奖。本页仅为统计描述，不构成任何预测。
          </p>
        </>
      )}
    </section>
  )
}

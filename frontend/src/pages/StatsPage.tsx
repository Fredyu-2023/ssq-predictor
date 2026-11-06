/**
 * 统计分析页：号码频次 / 遗漏 / 比例结构 / 和值与 AC 分布的总览页。
 *
 * 页面结构（自上而下）：
 *   页面头（含 近30期 / 近100期 / 全部 窗口切换）
 *   → 4 张指标卡（统计窗口、和值均值、AC 均值、库内总期数）
 *   → 多期号码走势矩阵（TrendTable，独立取数、独立窗口切换）
 *   → 红/蓝频次柱、红/蓝遗漏热力图、连号 chips
 *   → 奇偶比 / 大小比 / 区间比三连、和值分布 / AC 分布
 *   → 免责声明
 *
 * 数据流：/api/stats（窗口联动，一次返回全部统计）+ /api/history（走势矩阵专用，独立窗口）。
 */
import { useEffect, useMemo, useState } from 'react'
import { apiGet } from '../api/client'
import { BarChart, type BarItem } from '../components/BarChart'
import { DistributionBars } from '../components/DistributionBars'
import { Heatmap } from '../components/Heatmap'
import { TrendTable } from '../components/TrendTable'
import type { HistoryPageData, StatsOut } from '../types'

// ---- 统计窗口选项：整页统计跟随它重算 ----
const RANGES: { key: string; label: string }[] = [
  { key: '30', label: '近 30 期' },
  { key: '100', label: '近 100 期' },
  { key: 'all', label: '全部' },
]

// ---- 走势矩阵窗口：跟随整页 range（全部期时表格限最近 300 期，避免 1.5 万单元格卡顿） ----
function trendWindowOf(range: string): number {
  if (range === 'all') return 300
  return Number(range)
}

export function StatsPage() {
  // ---- 整页统计状态（跟随 range 重算） ----
  const [range, setRange] = useState('30') // 统计窗口：30 / 100 / all
  const [data, setData] = useState<StatsOut | null>(null) // /api/stats 一次返回的全部统计
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // ---- 走势矩阵状态（窗口由 range 派生，与整页联动） ----
  const [trend, setTrend] = useState<HistoryPageData | null>(null)
  const [trendLoading, setTrendLoading] = useState(false)
  const [trendError, setTrendError] = useState<string | null>(null)

  // ---- 整页统计取数：range 变化即重算；cancelled 防止快速切换时旧响应覆盖新数据 ----
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

  // 走势矩阵取数：窗口跟随整页 range（联动），复用历史接口按页取最近 N 期。
  useEffect(() => {
    let cancelled = false
    setTrendLoading(true)
    setTrendError(null)
    apiGet<HistoryPageData>('/api/history', { type: 'ssq', page: 1, size: trendWindowOf(range) })
      .then((res) => {
        if (!cancelled) setTrend(res)
      })
      .catch((err: Error) => {
        if (!cancelled) setTrendError(err.message)
      })
      .finally(() => {
        if (!cancelled) setTrendLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [range])

  // ---- 派生数据 ----
  // 冷热号 Set：给红球频次柱着色用（热=hot、冷=cold、其余=accent）
  const hotSet = useMemo(() => new Set(data?.hot_red.map((x) => x.number) ?? []), [data])
  const coldSet = useMemo(() => new Set(data?.cold_red.map((x) => x.number) ?? []), [data])

  // ---- 图表数据映射：把后端结构转成 BarChart 需要的 BarItem ----
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
      {/* ---- 页面头 + 统计窗口切换 ---- */}
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
          {/* ---- 4 张指标卡：窗口 / 和值均值 / AC 均值 / 库内总期数 ---- */}
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

          {/* ---- 多期号码走势矩阵：经典彩票走势图，跟随页面期数联动 ---- */}
          <div className="card">
            <div className="card-head">
              <h2>多期号码走势</h2>
              <span className="tag tag-muted">最近 {trendWindowOf(range)} 期 · 随上方窗口联动</span>
            </div>
            {trendError && <div className="alert alert-error">{trendError}</div>}
            {trendLoading && <div className="skeleton">走势加载中…</div>}
            {trend && <TrendTable items={trend.items} />}
            <p className="muted-text small">
              每行一期：红球 1–33、蓝球 1–16，命中的号码以彩球标出，末行为窗口内出现次数。号码较多时可左右滑动查看。
            </p>
          </div>

          {/* ---- 频次柱：红球按冷/热着色，蓝球统一色 ---- */}
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

          {/* ---- 遗漏热力图：颜色越深 = 该号码越久未开出 ---- */}
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

          {/* ---- 连号 chips：相邻号码同现次数，只展示前 16 组 ---- */}
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

          {/* ---- 比例结构三连：奇偶比 / 大小比 / 区间比 ---- */}
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

          {/* ---- 和值分布（10 宽分桶）与 AC 值分布 ---- */}
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

import { useEffect, useState } from 'react'
import { apiGet, apiPostJson } from '../api/client'
import { BarChart } from '../components/BarChart'
import type { BacktestOut, StrategyOut } from '../types'

function pct(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

function expectedText(value: number): string {
  if (value === 0) return '0'
  if (value >= 0.01) return value.toFixed(2)
  return value.toExponential(1)
}

export function BacktestPage() {
  const [strategies, setStrategies] = useState<StrategyOut[]>([])
  const [windowSize, setWindowSize] = useState(100)
  const [periods, setPeriods] = useState(500)
  const [results, setResults] = useState<BacktestOut[]>([])
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState<string | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    apiGet<StrategyOut[]>('/api/strategies')
      .then((items) => {
        if (!cancelled) setStrategies(items)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const runAll = async () => {
    setBusy(true)
    setError(null)
    setErrors([])
    setResults([])
    const collected: BacktestOut[] = []
    const failed: string[] = []
    try {
      for (const item of strategies) {
        setProgress(`${item.name}（${collected.length + 1}/${strategies.length}）`)
        try {
          const data = await apiPostJson<BacktestOut>('/api/backtest', {
            strategy: item.name,
            window: windowSize,
            periods,
          })
          collected.push(data)
          setResults([...collected])
        } catch (err) {
          failed.push(`${item.name}：${err instanceof Error ? err.message : String(err)}`)
        }
      }
      setErrors(failed)
    } finally {
      setProgress(null)
      setBusy(false)
    }
  }

  const sorted = [...results].sort((a, b) => b.avg_red_hits - a.avg_red_hits)
  const withinRandom = results.filter((item) => item.chi_square.p_value > 0.05).length

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h1>策略回测</h1>
          <p className="muted-text">
            用历史数据滑动模拟：每期只用此前 {windowSize} 期训练，生成 1 注与实际开奖比对。
          </p>
        </div>
      </div>

      <div className="alert alert-warn">
        回测如实展示统计显著性：彩票为独立随机事件，任何策略的长期命中分布都应接近随机基线。
        若 p &gt; 0.05，说明该策略与随机无显著差异——这正是本系统的结论。
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="card backtest-controls">
        <label className="field">
          <span>训练窗口</span>
          <select
            className="field-select"
            value={windowSize}
            onChange={(event) => setWindowSize(Number(event.target.value))}
          >
            <option value={50}>近 50 期</option>
            <option value={100}>近 100 期</option>
            <option value={200}>近 200 期</option>
          </select>
        </label>
        <label className="field">
          <span>回测期数</span>
          <select
            className="field-select"
            value={periods}
            onChange={(event) => setPeriods(Number(event.target.value))}
          >
            <option value={100}>100 期</option>
            <option value={300}>300 期</option>
            <option value={500}>500 期</option>
          </select>
        </label>
        <button className="btn btn-primary generate-btn" disabled={busy} onClick={runAll}>
          {busy ? `回测中… ${progress ?? ''}` : '运行回测（全部策略）'}
        </button>
      </div>

      {errors.length > 0 && (
        <div className="alert alert-error">
          {errors.map((item) => (
            <div key={item}>{item}</div>
          ))}
        </div>
      )}

      {results.length === 0 ? (
        !busy && (
          <div className="card empty-state">
            <strong>还没有回测结果</strong>
            <span className="muted-text">
              选择训练窗口与回测期数，点击「运行回测」。将依次对全部已注册策略（含自定义算法）做滑动窗口模拟。
            </span>
          </div>
        )
      ) : (
        <>
          <div className="card">
            <div className="card-head">
              <h2>策略对比：平均命中红球</h2>
              <span className="muted-text">随机理论均值 1.09 个（6 × 6 / 33）</span>
            </div>
            <BarChart
              items={sorted.map((item) => ({
                key: item.strategy,
                label: item.strategy,
                value: item.avg_red_hits,
                hint: `${item.strategy}：平均 ${item.avg_red_hits} 个红球，p = ${item.chi_square.p_value}`,
                tone: 'accent',
              }))}
              height={170}
              showValues
            />
            <p className="chi-line">
              {results.length} 个策略中 {withinRandom} 个的 p &gt; 0.05（与随机无显著差异）。
              样本区间 {results[0].from_issue}–{results[0].to_issue}，共 {results[0].samples} 期。
            </p>
          </div>

          <div className="backtest-list">
            {results.map((item) => (
              <div className="card backtest-card" key={item.strategy}>
                <div className="card-head">
                  <h2>{item.strategy}</h2>
                  <span
                    className={`tag ${item.chi_square.p_value > 0.05 ? 'tag-success' : 'tag-warn'}`}
                  >
                    p = {item.chi_square.p_value.toFixed(4)} ·{' '}
                    {item.chi_square.p_value > 0.05 ? '无显著差异' : '有显著偏差'}
                  </span>
                </div>
                <div className="muted-text backtest-meta">
                  共 {item.samples} 期 · 训练窗口 {item.window} 期 · 平均命中 {item.avg_red_hits} 个红球 ·
                  蓝球命中率 {pct(item.blue_hit_rate)}（理论 {pct(item.blue_expected_rate)}）
                </div>

                <div className="backtest-body">
                  <div>
                    <div className="mini-title">红球命中分布（0–6 个）</div>
                    <BarChart
                      items={item.red_hits.map((hit) => ({
                        key: hit.hits,
                        label: `${hit.hits}`,
                        value: hit.count,
                        hint: `命中 ${hit.hits} 个红球：${hit.count} 期（${pct(hit.ratio)}）`,
                        tone: hit.hits >= 4 ? 'hot' : hit.hits === 0 ? 'cold' : 'accent',
                      }))}
                      height={140}
                      showValues
                    />
                  </div>
                  <div>
                    <div className="mini-title">奖级：实际 vs 理论期望</div>
                    <table className="mini-table">
                      <thead>
                        <tr>
                          <th>奖级</th>
                          <th>条件</th>
                          <th className="num">实际</th>
                          <th className="num">期望</th>
                        </tr>
                      </thead>
                      <tbody>
                        {item.prize_levels.map((prize) => (
                          <tr key={prize.level}>
                            <td>{prize.name}</td>
                            <td className="muted-text">{prize.condition}</td>
                            <td className="num">{prize.actual}</td>
                            <td className="num">{expectedText(prize.expected)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <p className="chi-line">
                  卡方检验：χ² = {item.chi_square.statistic}，df = {item.chi_square.df}，
                  p = {item.chi_square.p_value}。{item.chi_square.conclusion}
                </p>
                <div className="chip-row">
                  {item.chi_square.buckets.map((bucket) => (
                    <span className="chip" key={bucket.label}>
                      {bucket.label} 实际 <b>{bucket.observed}</b> / 期望 {bucket.expected}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <p className="disclaimer">{results[0].disclaimer}；回测仅用于验证统计方法，不构成购彩建议。</p>
        </>
      )}
    </section>
  )
}

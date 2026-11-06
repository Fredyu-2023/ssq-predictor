import { useEffect, useState } from 'react'
import { apiGet, apiPostJson } from '../api/client'
import { Ball } from '../components/Ball'
import type { BetOut, PredictOut, StatsOut, StrategyOut } from '../types'

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

export function PredictPage() {
  const [strategies, setStrategies] = useState<StrategyOut[]>([])
  const [strategy, setStrategy] = useState('balanced')
  const [count, setCount] = useState(5)
  const [windowSize, setWindowSize] = useState(30)
  const [result, setResult] = useState<PredictOut | null>(null)
  const [stats, setStats] = useState<StatsOut | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    apiGet<StrategyOut[]>('/api/strategies')
      .then((items) => {
        if (cancelled) return
        setStrategies(items)
        setStrategy((prev) =>
          items.some((item) => item.name === prev) ? prev : (items[0]?.name ?? 'random'),
        )
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
    apiGet<StatsOut>('/api/stats', { type: 'ssq', range: '30' })
      .then((value) => {
        if (!cancelled) setStats(value)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  const hotSet = new Set(stats?.hot_red.map((item) => item.number) ?? [])
  const coldSet = new Set(stats?.cold_red.map((item) => item.number) ?? [])
  const current = strategies.find((item) => item.name === strategy)

  const highlightOf = (n: number): 'hot' | 'cold' | undefined => {
    if (hotSet.has(n)) return 'hot'
    if (coldSet.has(n)) return 'cold'
    return undefined
  }

  const handleGenerate = async () => {
    setBusy(true)
    setError(null)
    setCopied(null)
    try {
      const data = await apiPostJson<PredictOut>('/api/predict', {
        strategy,
        count,
        params: { window: windowSize },
      })
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const copyBet = async (bet: BetOut, index: number) => {
    const text = `${bet.red.map(pad).join(' ')} + ${pad(bet.blue)}`
    try {
      await navigator.clipboard.writeText(text)
      setCopied(index)
      window.setTimeout(() => setCopied(null), 1500)
    } catch {
      setError('复制失败，请手动选择文本')
    }
  }

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h1>选号预测</h1>
          <p className="muted-text">
            基于历史统计的策略化选号。所有结果与纯随机中奖概率等价。
          </p>
        </div>
        {stats && (
          <div className="legend">
            <span className="legend-item">
              <i className="legend-dot legend-hot" /> 热号
            </span>
            <span className="legend-item">
              <i className="legend-dot legend-cold" /> 冷号
            </span>
          </div>
        )}
      </div>

      <div className="alert alert-warn">
        彩票为独立随机事件，历史数据不影响未来开奖。本页结果为统计选号，不构成任何中奖承诺，请理性购彩。
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="card predict-controls">
        <label className="field">
          <span>选号策略</span>
          <select
            className="field-select"
            value={strategy}
            onChange={(event) => setStrategy(event.target.value)}
          >
            {strategies.map((item) => (
              <option key={item.name} value={item.name}>
                {item.name} · {item.source === 'custom' ? '自定义' : '内置'}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>注数（1–20）</span>
          <input
            className="field-input"
            type="number"
            min={1}
            max={20}
            value={count}
            onChange={(event) => setCount(Math.max(1, Math.min(20, Number(event.target.value) || 1)))}
          />
        </label>

        <label className="field">
          <span>参考期数（1–500）</span>
          <input
            className="field-input"
            type="number"
            min={1}
            max={500}
            value={windowSize}
            onChange={(event) =>
              setWindowSize(Math.max(1, Math.min(500, Number(event.target.value) || 1)))
            }
          />
        </label>

        <button className="btn btn-primary generate-btn" disabled={busy} onClick={handleGenerate}>
          {busy ? '生成中…' : '生成号码'}
        </button>
      </div>

      {current && <p className="muted-text strategy-desc">{current.description}</p>}

      {result ? (
        <>
          <div className="bet-grid">
            {result.numbers.map((bet, index) => (
              <div className="card bet-card" key={`${result.strategy}-${index}`}>
                <div className="bet-head">
                  <span className="muted-text">第 {index + 1} 注</span>
                  <button className="btn btn-mini" onClick={() => copyBet(bet, index)}>
                    {copied === index ? '已复制' : '复制'}
                  </button>
                </div>
                <div className="ball-row bet-balls">
                  {bet.red.map((n) => (
                    <Ball key={`r-${n}`} value={n} tone="red" size={38} highlight={highlightOf(n)} />
                  ))}
                  <span className="bet-plus">+</span>
                  <Ball value={bet.blue} tone="blue" size={38} />
                </div>
              </div>
            ))}
          </div>
          <p className="disclaimer">{result.disclaimer}</p>
        </>
      ) : (
        !busy && (
          <div className="card empty-state">
            <strong>还没有生成号码</strong>
            <span className="muted-text">
              选择策略与注数，点击「生成号码」。热号/冷号标记参考近 30 期统计。
            </span>
          </div>
        )
      )}
    </section>
  )
}

/**
 * 策略回测页：用「滑动窗口」模拟真实选号过程，并如实展示统计结论。
 *
 * 原理（一句话）：对每一个历史期号，只用它之前的 N 期数据训练策略、生成 1 注号码，
 * 再与该期实际开奖比对命中数——策略永远看不到「未来」的数据。
 *
 * 页面流程：
 *   加载策略清单（GET /api/strategies）
 *   → 用户选择训练窗口 / 回测期数，点击「运行回测」
 *   → 逐个策略串行调用 POST /api/backtest（每完成一个就刷新列表，并显示进度 x/y）
 *   → 汇总条形图（按平均命中红球数排序）
 *   → 每个策略一张详情卡（红球命中分布、奖级实际 vs 期望、卡方检验）
 *
 * 判读标准：p > 0.05 表示与随机基线无显著差异。
 * 彩票是独立随机事件，「无显著差异」正是预期结论，页面用 tag-success 展示。
 */
import { useEffect, useState } from 'react'
import { apiGet, apiPostJson } from '../api/client'
import { BarChart } from '../components/BarChart'
import type { BacktestOut, StrategyOut } from '../types'

/** 比例 → 百分比文本，如 0.0625 → "6.25%"。 */
function pct(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

/**
 * 奖级期望次数的可读化：
 * 高奖级期望次数极小（如 1e-5），直接 toFixed 会显示 0.00，
 * 所以小于 0.01 时改用科学计数法（如 1.2e-5）。
 */
function expectedText(value: number): string {
  if (value === 0) return '0'
  if (value >= 0.01) return value.toFixed(2)
  return value.toExponential(1)
}

export function BacktestPage() {
  // ---- 页面状态 ----
  const [strategies, setStrategies] = useState<StrategyOut[]>([]) // 全部已注册策略（含自定义插件）
  const [windowSize, setWindowSize] = useState(100) // 训练窗口：每次训练用多少期历史
  const [periods, setPeriods] = useState(500) // 回测期数：共模拟多少期开奖
  const [results, setResults] = useState<BacktestOut[]>([]) // 已完成的回测结果（逐个追加）
  const [busy, setBusy] = useState(false) // 是否正在回测（禁用按钮）
  const [progress, setProgress] = useState<string | null>(null) // 当前进度文本，如 "随机（2/5）"
  const [errors, setErrors] = useState<string[]>([]) // 单个策略失败不影响其他策略，单独收集
  const [error, setError] = useState<string | null>(null) // 页面级错误（如策略清单加载失败）

  // ---- 初始化：加载策略清单（只加载一次） ----
  useEffect(() => {
    let cancelled = false // 组件卸载后不再 setState，避免 React 警告
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

  // ---- 动作：依次回测全部策略（串行，避免后端并发计算压垮本机） ----
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
            window: windowSize, // 每次训练用最近 window 期
            periods, // 共向前滑动模拟 periods 期
          })
          collected.push(data)
          setResults([...collected]) // 每完成一个策略立刻刷新界面
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

  // ---- 派生数据 ----
  const sorted = [...results].sort((a, b) => b.avg_red_hits - a.avg_red_hits) // 汇总图按平均命中降序
  const withinRandom = results.filter((item) => item.chi_square.p_value > 0.05).length // 与随机无显著差异的策略数

  return (
    <section className="page">
      {/* ---- 页面头部：说明「每期只用此前 N 期训练」的回测规则，window 实时联动 ---- */}
      <div className="page-head">
        <div>
          <h1>策略回测</h1>
          <p className="muted-text">
            用历史数据滑动模拟：每期只用此前 {windowSize} 期训练，生成 1 注与实际开奖比对。
          </p>
        </div>
      </div>

      {/* ---- 结论预告条：常驻展示判读标准，避免把 p 值误读成「策略有效」 ---- */}
      <div className="alert alert-warn">
        回测如实展示统计显著性：彩票为独立随机事件，任何策略的长期命中分布都应接近随机基线。
        若 p &gt; 0.05，说明该策略与随机无显著差异——这正是本系统的结论。
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {/* ---- 控制卡：训练窗口 / 回测期数两个参数 + 运行按钮；busy 时禁用并显示进度 ---- */}
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

      {/* ---- 单策略失败汇总：某个策略出错不阻断其他策略，逐条列出 ---- */}
      {errors.length > 0 && (
        <div className="alert alert-error">
          {errors.map((item) => (
            <div key={item}>{item}</div>
          ))}
        </div>
      )}

      {/* ---- 空态：尚未回测时给出操作指引（回测进行中不显示，避免闪动） ---- */}
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
          {/* ---- 汇总卡：各策略平均命中红球条形图 + 显著性小结（按降序排列） ---- */}
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

          {/* ---- 详情列表：每个策略一张卡（命中分布图 / 奖级对照表 / 卡方检验 / 分桶明细） ---- */}
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

                {/* 双栏布局：左=红球命中 0–6 分布柱状图，右=奖级实际次数 vs 理论期望 */}
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

                {/* 卡方拟合优度检验：命中数分桶后与随机期望对比，p > 0.05 视为无显著差异 */}
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

          {/* ---- 免责声明（来自后端，随结果下发） ---- */}
          <p className="disclaimer">{results[0].disclaimer}；回测仅用于验证统计方法，不构成购彩建议。</p>
        </>
      )}
    </section>
  )
}

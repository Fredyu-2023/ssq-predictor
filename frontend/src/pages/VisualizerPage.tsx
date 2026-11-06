/**
 * 形态分析页：把开奖号码映射成几何形态（曲线 / 吸引子 / 螺旋……）的可视化实验台。
 *
 * 页面结构（自上而下）：
 *   页面头 → 实现进度说明条 → 算法统计 chips
 *   → 结果面板（viz-result，仅点击运行后出现，并自动滚动到可视区）
 *   → 按 8 个类别分组的算法卡片网格（未实现的算法按钮禁用）
 *
 * 数据流：
 *   加载算法清单（GET /api/visualizers）
 *   → 点击「运行」：POST render → 归一化点列交给 SpiralFourierView 绘制
 *   → 点击「导出特征」：先 render 再 features，得到几何特征并可下载 JSON
 *
 * 注意：形态仅用于观察，不改变、不预测中奖概率（页面底部常驻免责声明）。
 */
import { useEffect, useRef, useState } from 'react'
import { apiGet, apiPostJson } from '../api/client'
import { Ball } from '../components/Ball'
import { SpiralFourierView } from '../components/SpiralFourierView'
import type {
  SpiralFourierData,
  VisualizationOut,
  VisualizerFeaturesOut,
  VisualizerOut,
} from '../types'

// ---- 类别展示顺序：与 ALGORITHM_GUIDE.html 中 A–R 的分组保持一致 ----
const CATEGORY_ORDER = ['频域', '轨迹', '动力系统', '图论', '螺旋', '塌陷', '伸展收缩', '组合']

export function VisualizerPage() {
  // ---- 页面状态 ----
  const [items, setItems] = useState<VisualizerOut[]>([]) // 算法清单（A–R，共 18 项）
  const [error, setError] = useState<string | null>(null) // 页面级错误（清单加载 / 运行失败）
  const [active, setActive] = useState<VisualizerOut | null>(null) // 当前正在展示的算法（结果面板标题来源）
  const [result, setResult] = useState<VisualizationOut<SpiralFourierData> | null>(null) // render 返回的曲线数据
  const [features, setFeatures] = useState<Record<string, number> | null>(null) // features 返回的几何特征
  const [busy, setBusy] = useState(false) // 计算中：禁用所有运行/导出按钮
  const resultRef = useRef<HTMLDivElement>(null) // 结果面板锚点，用于自动滚动

  // ---- 初始化：加载算法清单（只加载一次；cancelled 防止组件卸载后 setState） ----
  useEffect(() => {
    let cancelled = false
    apiGet<VisualizerOut[]>('/api/visualizers')
      .then((data) => {
        if (!cancelled) setItems(data)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // 结果面板出现在卡片列表上方：点击运行后自动滚动过去，避免误以为没反应。
  useEffect(() => {
    if (result && resultRef.current) {
      resultRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [result])

  // 出错时滚回顶部，确保能看到错误提示。
  useEffect(() => {
    if (error) window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [error])

  // 运行算法：只在最新一期的数据上渲染一条曲线，期数固定为 1。
  const run = async (item: VisualizerOut) => {
    setActive(item)
    setResult(null)
    setFeatures(null)
    setBusy(true)
    setError(null)
    try {
      const data = await apiPostJson<VisualizationOut<SpiralFourierData>>(
        `/api/visualizers/${item.name}/render`,
        { type: 'ssq', periods: 1 },
      )
      setResult(data)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  // 导出特征：先渲染，再取同一份数据对应的几何特征。
  const exportFeatures = async (item: VisualizerOut) => {
    setActive(item)
    setResult(null)
    setFeatures(null)
    setBusy(true)
    setError(null)
    try {
      const data = await apiPostJson<VisualizationOut<SpiralFourierData>>(
        `/api/visualizers/${item.name}/render`,
        { type: 'ssq', periods: 1 },
      )
      const extracted = await apiPostJson<VisualizerFeaturesOut>(
        `/api/visualizers/${item.name}/features`,
        { type: 'ssq', periods: 1 },
      )
      setResult(data)
      setFeatures(extracted.features)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  // 下载特征：内存拼 Blob → 临时 <a> 触发浏览器下载 → 随即释放 ObjectURL
  const downloadFeatures = () => {
    if (!features || !active) return
    const payload = { code: active.code, name: active.name, features }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${active.name}_features.json`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 0)
  }

  // 关闭结果面板：清空 active / result / features 三件套
  const closeResult = () => {
    setActive(null)
    setResult(null)
    setFeatures(null)
  }

  // ---- 派生数据 ----
  // groups：按固定类别顺序分组并丢弃空组；implemented：统计 chips 用；maxWeight：谐波条归一化基准
  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    list: items.filter((item) => item.category === category),
  })).filter((group) => group.list.length > 0)

  const implemented = items.filter((item) => item.status === 'implemented').length
  const maxWeight = result
    ? Math.max(...result.data.harmonics.map((item) => item.weight), 1e-9)
    : 1

  return (
    <section className="page">
      {/* ---- 页面头 ---- */}
      <div className="page-head">
        <div>
          <h1>形态分析</h1>
          <p className="muted-text">
            把开奖号码映射为几何形态：频域曲线、混沌吸引子、螺旋骨架、坍缩轨迹……用于观察结构，不改变中奖概率。
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {/* ---- 实现进度说明条：告诉用户哪些能点、G 的映射规则是什么 ---- */}
      <div className="alert alert-info">
        当前已实现 G. 螺旋骨架傅里叶：红球按升序映射为螺旋上的 6 阶余弦振幅，蓝球决定螺距与圈数；曲线由后端计算、
        前端用 SVG 直接绘制。其余 17 个算法仍为「开发中」。
      </div>

      {/* ---- 统计卡：算法总数 / 已实现 / 开发中 / 类别数 ---- */}
      <div className="card">
        <div className="viz-summary">
          <span className="chip">算法总数 <b>{items.length}</b></span>
          <span className="chip">已实现 <b>{implemented}</b></span>
          <span className="chip chip-warm">开发中 <b>{items.length - implemented}</b></span>
          <span className="chip">类别 <b>{groups.length}</b></span>
        </div>
      </div>

      {/* ---- 结果面板：点击运行/导出后出现；ref 供自动滚动，CSS scroll-margin 避开吸顶导航 ---- */}
      {active && (
        <div className="card viz-result" ref={resultRef}>
          <div className="viz-result-head">
            <div>
              <div className="viz-result-title">
                <span className="viz-code">{active.code}</span>
                <h2>{active.title}</h2>
              </div>
              <p className="muted-text">
                {active.mapping}
                {result ? ` · 期号 ${result.data.issue}` : ''}
              </p>
            </div>
            <button className="btn btn-mini" onClick={closeResult}>
              关闭
            </button>
          </div>

          {busy && <p className="muted-text">正在计算曲线…</p>}

          {result && (
            <>
              {/* 参数 chips：期号 / 圈数 / 紧密度 / 螺距 / 谐波增益 */}
              <div className="viz-chips">
                <span className="chip">期号 <b>{result.data.issue}</b></span>
                <span className="chip">圈数 <b>{result.data.turns.toFixed(2)}</b></span>
                <span className="chip">紧密度 <b>{result.data.tightness.toFixed(3)}</b></span>
                <span className="chip">螺距 <b>{result.data.pitch.toFixed(3)}</b></span>
                <span className="chip">谐波增益 <b>{result.data.gain.toFixed(2)}</b></span>
              </div>

              {/* 映射说明：6 个红球各对应第 1–6 阶谐波振幅，蓝球对应紧密度 */}
              <div className="viz-balls">
                <span className="muted-text">红球 → 第 1–6 阶振幅</span>
                <div className="ball-row">
                  {result.data.reds.map((value, index) => (
                    <span className="viz-ball-item" key={`${index}-${value}`}>
                      <Ball value={value} size={30} />
                      <span className="viz-order">{index + 1} 阶</span>
                    </span>
                  ))}
                </div>
                <span className="muted-text">蓝球 → 紧密度</span>
                <Ball value={result.data.blue} tone="blue" size={30} />
              </div>

              {/* 曲线区：SVG 直接绘制后端归一化点列；图例放 SVG 外避免遮挡曲线 */}
              <div className="spiral-wrap">
                <SpiralFourierView data={result.data} />
                <div className="viz-legend">
                  <span className="viz-legend-item"><i className="viz-dot viz-dot-start" />起点</span>
                  <span className="viz-legend-item"><i className="viz-dot viz-dot-end" />终点</span>
                  <span className="viz-legend-item">虚线圆 = 半径刻度</span>
                </div>
              </div>

              {/* 谐波权重条：按最大权重归一化到 100%，直观看出主导阶数 */}
              <div className="harmonics">
                {result.data.harmonics.map((item) => (
                  <div className="harmonic-row" key={item.order}>
                    <span className="harmonic-order">{item.order} 阶</span>
                    <span className="harmonic-number">红球 {String(item.number).padStart(2, '0')}</span>
                    <div className="harmonic-bar">
                      <i style={{ width: `${(item.weight / maxWeight) * 100}%` }} />
                    </div>
                    <span className="harmonic-weight">{(item.weight * 100).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* 特征面板：几何特征 JSON 展示 + 下载按钮 */}
          {features && (
            <div className="viz-features">
              <div className="viz-features-head">
                <h3>图形特征</h3>
                <button className="btn btn-mini" onClick={downloadFeatures}>
                  下载 JSON
                </button>
              </div>
              <pre className="viz-json">{JSON.stringify(features, null, 2)}</pre>
            </div>
          )}
        </div>
      )}

      {/* ---- 算法卡片网格：按类别分组；未实现的算法按钮禁用并给出提示 ---- */}
      {groups.map((group) => (
        <div className="viz-group" key={group.category}>
          <div className="viz-group-title">
            {group.category} · {group.list.length} 个
          </div>
          <div className="viz-grid">
            {group.list.map((item) => {
              const done = item.status === 'implemented'
              return (
                <div className="card viz-card" key={item.name}>
                  <div className="viz-head">
                    <span className="viz-code">{item.code}</span>
                    <div>
                      <h3>{item.title}</h3>
                      <div className="viz-tags">
                        <span className="tag tag-muted">{item.dimension}</span>
                        <span className={`tag ${done ? 'tag-success' : 'tag-warn'}`}>
                          {done ? '已实现' : '开发中'}
                        </span>
                      </div>
                    </div>
                  </div>
                  <p className="viz-mapping">{item.mapping}</p>
                  <div className="viz-actions">
                    <button
                      className="btn btn-mini"
                      disabled={!done || busy}
                      title={done ? '按最新一期数据渲染' : '算法开发中，暂不可运行'}
                      onClick={() => run(item)}
                    >
                      运行
                    </button>
                    <button
                      className="btn btn-mini"
                      disabled={!done || busy}
                      title={done ? '提取几何特征并导出 JSON' : '算法开发中，暂不可导出特征'}
                      onClick={() => exportFeatures(item)}
                    >
                      导出特征 JSON
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ))}

      {items.length > 0 && (
        <p className="disclaimer">
          形态可视化仅用于数据观察与算法实验，不构成购彩建议；任何形态都不具备预测能力。
        </p>
      )}
    </section>
  )
}

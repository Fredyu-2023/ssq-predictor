import { useEffect, useState } from 'react'
import { apiGet } from '../api/client'
import type { VisualizerOut } from '../types'

const CATEGORY_ORDER = ['频域', '轨迹', '动力系统', '图论', '螺旋', '塌陷', '伸展收缩', '组合']

export function VisualizerPage() {
  const [items, setItems] = useState<VisualizerOut[]>([])
  const [error, setError] = useState<string | null>(null)

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

  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    list: items.filter((item) => item.category === category),
  })).filter((group) => group.list.length > 0)

  const implemented = items.filter((item) => item.status === 'implemented').length

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h1>形态分析</h1>
          <p className="muted-text">
            把开奖号码映射为几何形态：频域曲线、混沌吸引子、螺旋骨架、坍缩轨迹……用于观察结构，不改变中奖概率。
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="alert alert-info">
        形态算法为后补插件：框架与清单已就绪，A–R 全部标记「开发中」。3D 算法将按需使用 Three.js
        懒加载（本地模块 + 自实现轨道相机），并保留 2D Canvas 回退。
      </div>

      <div className="card">
        <div className="viz-summary">
          <span className="chip">算法总数 <b>{items.length}</b></span>
          <span className="chip">已实现 <b>{implemented}</b></span>
          <span className="chip chip-warm">开发中 <b>{items.length - implemented}</b></span>
          <span className="chip">类别 <b>{groups.length}</b></span>
        </div>
      </div>

      {groups.map((group) => (
        <div className="viz-group" key={group.category}>
          <div className="viz-group-title">
            {group.category} · {group.list.length} 个
          </div>
          <div className="viz-grid">
            {group.list.map((item) => (
              <div className="card viz-card" key={item.name}>
                <div className="viz-head">
                  <span className="viz-code">{item.code}</span>
                  <div>
                    <h3>{item.title}</h3>
                    <div className="viz-tags">
                      <span className="tag tag-muted">{item.dimension}</span>
                      <span className="tag tag-warn">开发中</span>
                    </div>
                  </div>
                </div>
                <p className="viz-mapping">{item.mapping}</p>
                <div className="viz-actions">
                  <button className="btn btn-mini" disabled title="算法开发中，暂不可运行">
                    运行
                  </button>
                  <button className="btn btn-mini" disabled title="算法开发中，暂不可导出特征">
                    导出特征 JSON
                  </button>
                </div>
              </div>
            ))}
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

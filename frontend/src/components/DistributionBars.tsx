import type { DistributionItem } from '../types'

interface DistributionBarsProps {
  items: DistributionItem[]
  total: number
  tone?: 'accent' | 'red' | 'blue'
}

/** 比例分布条：标签 + 占比条 + 次数/百分比，比饼图更易比较。 */
export function DistributionBars({ items, total, tone = 'accent' }: DistributionBarsProps) {
  const visible = items.filter((item) => item.count > 0 || total === 0)
  if (visible.length === 0) return <p className="muted-text">暂无可展示分布</p>
  return (
    <div className="dist-list">
      {visible.map((item) => {
        const pct = total > 0 ? (item.count / total) * 100 : 0
        return (
          <div className="dist-row" key={item.label}>
            <span className="dist-label">{item.label}</span>
            <div className="dist-track">
              <div className={`dist-fill dist-${tone}`} style={{ width: `${pct}%` }} />
            </div>
            <span className="dist-value">
              {item.count} 次 · {pct.toFixed(1)}%
            </span>
          </div>
        )
      })}
    </div>
  )
}

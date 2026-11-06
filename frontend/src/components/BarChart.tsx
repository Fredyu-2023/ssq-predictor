export interface BarItem {
  key: string | number
  label: string
  value: number
  hint?: string
  tone?: 'accent' | 'hot' | 'cold' | 'muted'
}

interface BarChartProps {
  items: BarItem[]
  height?: number
  showValues?: boolean
}

/** 纯 CSS 柱状图：无第三方图表依赖，33 根柱子也能稳定渲染。 */
export function BarChart({ items, height = 150, showValues = false }: BarChartProps) {
  const max = Math.max(1, ...items.map((item) => item.value))
  return (
    <div className="bar-chart" style={{ height }}>
      {items.map((item) => {
        const ratio = item.value / max
        return (
          <div className="bar-col" key={item.key} title={item.hint ?? `${item.label}：${item.value}`}>
            {showValues && <span className="bar-value">{item.value}</span>}
            <div
              className={`bar bar-${item.tone ?? 'accent'}`}
              style={{ height: `${Math.max(ratio * 100, item.value > 0 ? 3 : 0)}%` }}
            />
            <span className="bar-label">{item.label}</span>
          </div>
        )
      })}
    </div>
  )
}

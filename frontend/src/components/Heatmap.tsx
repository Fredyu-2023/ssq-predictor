interface HeatCell {
  number: number
  value: number
}

interface HeatmapProps {
  cells: HeatCell[]
  tone?: 'red' | 'blue'
  unit?: string
}

/** 遗漏热力图：格子颜色深浅表示遗漏期数相对最大值。 */
export function Heatmap({ cells, tone = 'red', unit = '期' }: HeatmapProps) {
  const max = Math.max(1, ...cells.map((cell) => cell.value))
  return (
    <div className="heatmap">
      {cells.map((cell) => {
        const intensity = cell.value / max
        const alpha = 0.08 + intensity * 0.72
        const color =
          tone === 'red' ? `rgba(239, 68, 68, ${alpha})` : `rgba(59, 130, 246, ${alpha})`
        return (
          <div
            key={cell.number}
            className="heat-cell"
            style={{ background: color }}
            title={`号码 ${cell.number}：遗漏 ${cell.value} ${unit}`}
          >
            <span className="heat-number">{String(cell.number).padStart(2, '0')}</span>
            <span className="heat-value">{cell.value}</span>
          </div>
        )
      })}
    </div>
  )
}

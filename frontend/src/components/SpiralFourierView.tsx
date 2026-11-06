/**
 * G. 螺旋骨架傅里叶 · SVG 渲染组件
 *
 * 输入：后端 POST /api/visualizers/spiral_fourier/render 返回的归一化点列，
 *       所有点都落在单位圆内（半径 ≤ 1），前端只做平移缩放，不做任何数学计算。
 * 输出：一条「边旋转边起伏」的开口螺旋曲线，外加刻度圆环、十字轴和起点/终点标记。
 *
 * 绘制流程：
 *   归一化点列 → project() 平移缩放到画布 → 连成 path
 *   → 两层描边（宽而淡的发光层 + 细的主线层）→ 4 个刻度虚线圆环 + 十字轴
 *   → 起点（紫点）/ 终点（橙点 + 光环）
 *
 * 布局约定：文字图例放在 SVG 外的 HTML 里（见 VisualizerPage），避免文字遮挡曲线。
 */
import type { SpiralFourierData } from '../types'

// ---- 画布常量（viewBox 坐标系，配合 CSS 的 width:100% 自适应） ----
const SIZE = 760 // viewBox 边长（逻辑像素）
const PADDING = 82 // 四周留白，保证归一化半径 1 的曲线不贴边
const CENTER = SIZE / 2
const RADIUS = (SIZE - PADDING * 2) / 2 // 归一化半径 1 对应的像素半径
const RINGS = [0.25, 0.5, 0.75, 1] // 刻度圆环：0.25R / 0.5R / 0.75R / 1R

/**
 * 归一化数学坐标 → SVG 像素坐标。
 * 数学坐标 y 轴向上，SVG 的 y 轴向下，因此 y 分量要翻转。
 */
function project(x: number, y: number): [number, number] {
  return [CENTER + x * RADIUS, CENTER - y * RADIUS]
}

interface SpiralFourierViewProps {
  data: SpiralFourierData
}

/** 渲染入口：data.points 为空时直接不渲染（后端保证至少 240 个点）。 */
export function SpiralFourierView({ data }: SpiralFourierViewProps) {
  if (data.points.length === 0) {
    return null
  }

  // ---- 点列 → SVG path：首点用 M（moveTo），其余用 L（lineTo），保留 2 位小数控制体积 ----
  const path = data.points
    .map(([x, y], index) => {
      const [px, py] = project(x, y)
      return `${index === 0 ? 'M' : 'L'}${px.toFixed(2)},${py.toFixed(2)}`
    })
    .join(' ')
  const [startX, startY] = project(...data.points[0])
  const [endX, endY] = project(...data.points[data.points.length - 1])

  return (
    <svg
      className="spiral-svg"
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      role="img"
      aria-label={`螺旋骨架傅里叶曲线，期号 ${data.issue}`}
    >
      {/* 描边渐变：青 → 靛 → 粉，沿对角线方向过渡 */}
      <defs>
        <linearGradient id="spiral-stroke" x1="0" y1="0" x2={SIZE} y2={SIZE} gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="55%" stopColor="#818cf8" />
          <stop offset="100%" stopColor="#f472b6" />
        </linearGradient>
      </defs>

      {/* 背景层：4 个刻度虚线圆环 + 十字轴，只作参照，不喧宾夺主 */}
      {RINGS.map((ratio) => (
        <circle
          key={ratio}
          cx={CENTER}
          cy={CENTER}
          r={RADIUS * ratio}
          fill="none"
          stroke="rgba(148, 163, 184, 0.16)"
          strokeWidth={1}
          strokeDasharray="3 9"
        />
      ))}
      <line
        x1={CENTER - RADIUS}
        y1={CENTER}
        x2={CENTER + RADIUS}
        y2={CENTER}
        stroke="rgba(148, 163, 184, 0.12)"
        strokeWidth={1}
      />
      <line
        x1={CENTER}
        y1={CENTER - RADIUS}
        x2={CENTER}
        y2={CENTER + RADIUS}
        stroke="rgba(148, 163, 184, 0.12)"
        strokeWidth={1}
      />

      {/* 主曲线：第一层宽描边低透明度当发光，第二层细描边是主体 */}
      <path d={path} fill="none" stroke="url(#spiral-stroke)" strokeWidth={8} strokeOpacity={0.22} />
      <path
        d={path}
        fill="none"
        stroke="url(#spiral-stroke)"
        strokeWidth={2.4}
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* 起点（紫，靠圆心）与终点（橙点 + 外圈光环，靠外侧） */}
      <circle cx={startX} cy={startY} r={5} fill="#c4b5fd" stroke="rgba(15, 23, 42, 0.8)" strokeWidth={2} />
      <circle cx={endX} cy={endY} r={7} fill="#f59e0b" stroke="rgba(15, 23, 42, 0.85)" strokeWidth={2} />
      <circle cx={endX} cy={endY} r={13} fill="none" stroke="rgba(245, 158, 11, 0.45)" strokeWidth={2} />
    </svg>
  )
}

/**
 * 多期号码走势矩阵（经典彩票走势图）：期号 × 号码的二维命中表。
 *
 * 结构（3 个区块）：
 *   thead：两行表头——第一行「期号 | 红球(33 列) | 蓝球(16 列)」分组标题，第二行是 1–33 / 1–16 号码
 *   tbody：每行一期开奖，命中的号码渲染成实色彩球，未命中的渲染成淡色小数字
 *   tfoot：一行「次数」统计，对窗口内每个号码的出现次数求和
 *
 * 交互约定：
 *   - 表格共 50 列必然超宽，由外层 .trend-scroll 提供横向滚动
 *   - 期号列（.trend-issue）吸左固定，横向滑动时始终可见
 *   - 首个蓝球列加 .trend-blue-start 左边框，在视觉上分隔红/蓝两个号码段
 */
import type { DrawOut } from '../types'

// ---- 号码域常量：双色球红球 1–33、蓝球 1–16 ----
const RED_NUMBERS = Array.from({ length: 33 }, (_, i) => i + 1)
const BLUE_NUMBERS = Array.from({ length: 16 }, (_, i) => i + 1)

interface TrendTableProps {
  /** 要展示的开奖期列表（最新在前），每一行对应一期。 */
  items: DrawOut[]
}

/**
 * 渲染入口：先遍历 items 统计每个号码的出现次数（供 tfoot 使用），再一次性渲染整张表。
 * 50 列 × N 行全部由 React 直出，无虚拟滚动——窗口最大 100 期时约 5000 个单元格，性能可接受。
 */
export function TrendTable({ items }: TrendTableProps) {
  // ---- 次数统计：红/蓝分开两张 Map，号码 → 窗口内出现次数 ----
  const redCount = new Map<number, number>()
  const blueCount = new Map<number, number>()
  for (const item of items) {
    for (const n of item.reds) redCount.set(n, (redCount.get(n) ?? 0) + 1)
    for (const n of item.blues) blueCount.set(n, (blueCount.get(n) ?? 0) + 1)
  }

  // 单元格渲染器：命中 → 实色彩球（trend-ball），未命中 → 淡色数字（trend-miss）
  const cell = (hit: boolean, tone: 'red' | 'blue', value: number) =>
    hit ? (
      <span className={`trend-ball trend-ball-${tone}`}>{value}</span>
    ) : (
      <span className="trend-miss">{value}</span>
    )

  return (
    <div className="trend-scroll">
      <table className="trend-table">
        <thead>
          {/* 表头第一行：分组标题（红球跨 33 列、蓝球跨 16 列） */}
          <tr className="trend-group-row">
            <th className="trend-issue-head">期号</th>
            <th className="trend-group trend-group-red" colSpan={RED_NUMBERS.length}>
              红球
            </th>
            <th className="trend-group trend-group-blue" colSpan={BLUE_NUMBERS.length}>
              蓝球
            </th>
          </tr>
          {/* 表头第二行：具体号码 1–33 / 1–16；首个蓝球列加分隔样式 */}
          <tr>
            <th className="trend-issue-head" />
            {RED_NUMBERS.map((n) => (
              <th key={`rh-${n}`}>{n}</th>
            ))}
            {BLUE_NUMBERS.map((n) => (
              <th key={`bh-${n}`} className={n === BLUE_NUMBERS[0] ? 'trend-blue-start' : undefined}>
                {n}
              </th>
            ))}
          </tr>
        </thead>
        {/* 数据区：每行一期；Set 用于 O(1) 判断该号码当期是否命中 */}
        <tbody>
          {items.map((item) => {
            const redSet = new Set(item.reds)
            const blueSet = new Set(item.blues)
            return (
              <tr key={item.issue}>
                <td className="trend-issue mono">{item.issue}</td>
                {RED_NUMBERS.map((n) => (
                  <td key={`r-${item.issue}-${n}`}>{cell(redSet.has(n), 'red', n)}</td>
                ))}
                {BLUE_NUMBERS.map((n) => (
                  <td
                    key={`b-${item.issue}-${n}`}
                    className={n === BLUE_NUMBERS[0] ? 'trend-blue-start' : undefined}
                  >
                    {cell(blueSet.has(n), 'blue', n)}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
        {/* 统计区：窗口内每个号码的出现次数；无数据时不渲染 */}
        {items.length > 0 && (
          <tfoot>
            <tr>
              <td className="trend-issue">次数</td>
              {RED_NUMBERS.map((n) => (
                <td key={`rc-${n}`} className="trend-count">
                  {redCount.get(n) ?? 0}
                </td>
              ))}
              {BLUE_NUMBERS.map((n) => (
                <td
                  key={`bc-${n}`}
                  className={`trend-count${n === BLUE_NUMBERS[0] ? ' trend-blue-start' : ''}`}
                >
                  {blueCount.get(n) ?? 0}
                </td>
              ))}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { BacktestPage } from './pages/BacktestPage'
import { HistoryPage } from './pages/HistoryPage'
import { PredictPage } from './pages/PredictPage'
import { StatsPage } from './pages/StatsPage'
import { SyncPage } from './pages/SyncPage'
import { VisualizerPage } from './pages/VisualizerPage'

type PageKey = 'history' | 'stats' | 'predict' | 'backtest' | 'visualizer' | 'sync'

const NAV: { key: PageKey; label: string; hint: string }[] = [
  { key: 'history', label: '历史开奖', hint: '期号 · 球号 · 销售额' },
  { key: 'stats', label: '统计分析', hint: '频次 · 遗漏 · 结构' },
  { key: 'predict', label: '选号预测', hint: '策略选号 · 冷热标记' },
  { key: 'backtest', label: '策略回测', hint: '滑动窗口 · p-value' },
  { key: 'visualizer', label: '形态分析', hint: '几何映射 · 开发中' },
  { key: 'sync', label: '数据同步', hint: '状态 · 手动触发 · 日志' },
]

function readHash(): PageKey {
  const hash = window.location.hash.replace('#', '')
  return NAV.some((item) => item.key === hash) ? (hash as PageKey) : 'history'
}

export default function App() {
  const [page, setPage] = useState<PageKey>(readHash)

  useEffect(() => {
    const onHashChange = () => setPage(readHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const navigate = (key: PageKey) => {
    window.location.hash = key
    setPage(key)
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">SSQ</span>
          <div>
            <strong>双色球数据台</strong>
            <span className="brand-sub">开奖数据同步与分析</span>
          </div>
        </div>
        <nav className="nav">
          {NAV.map((item) => (
            <button
              key={item.key}
              className={`nav-item${page === item.key ? ' nav-active' : ''}`}
              onClick={() => navigate(item.key)}
              title={item.hint}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      <div className="disclaimer-bar">
        彩票为独立随机事件，历史数据不影响未来开奖。本站仅作统计分析与数据展示。
      </div>

      <main className="content">
        {page === 'history' && <HistoryPage />}
        {page === 'stats' && <StatsPage />}
        {page === 'predict' && <PredictPage />}
        {page === 'backtest' && <BacktestPage />}
        {page === 'visualizer' && <VisualizerPage />}
        {page === 'sync' && <SyncPage />}
      </main>

      <footer className="footer">本机 / 局域网使用 · 不对外公开</footer>
    </div>
  )
}

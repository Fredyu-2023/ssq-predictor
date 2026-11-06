import { test, expect } from '@playwright/test'

interface Bet {
  red: number[]
  blue: number
}

test.describe('后端 API 契约（经 Vite 代理）', () => {
  test('健康检查使用隔离的 e2e 开奖库', async ({ request }) => {
    const res = await request.get('/api/health')
    expect(res.ok()).toBeTruthy()
    const body = await res.json()
    expect(body.db).toContain('e2e.db')
    expect(body.draws).toBeGreaterThan(100)
  })

  test('彩种列表包含双色球', async ({ request }) => {
    const res = await request.get('/api/lotteries')
    expect(res.ok()).toBeTruthy()
    const items = await res.json()
    expect(items.map((item: { type: string }) => item.type)).toContain('ssq')
  })

  test('历史分页、期号搜索、日期搜索与空结果', async ({ request }) => {
    const first = await (
      await request.get('/api/history', { params: { type: 'ssq', page: 1, size: 20 } })
    ).json()
    expect(first.items).toHaveLength(20)
    expect(first.total).toBeGreaterThan(1000)

    const latest = first.items[0]
    expect(latest.issue).toMatch(/^\d+$/)

    const byIssue = await (
      await request.get('/api/history', { params: { type: 'ssq', q: latest.issue } })
    ).json()
    expect(byIssue.total).toBe(1)
    expect(byIssue.items[0].issue).toBe(latest.issue)

    const month = String(latest.draw_date).slice(0, 7)
    const byDate = await (
      await request.get('/api/history', { params: { type: 'ssq', q: month } })
    ).json()
    expect(byDate.total).toBeGreaterThan(0)
    for (const item of byDate.items) {
      expect(item.draw_date.startsWith(month)).toBeTruthy()
    }

    const none = await (
      await request.get('/api/history', { params: { type: 'ssq', q: '1999-01' } })
    ).json()
    expect(none.total).toBe(0)
  })

  test('策略清单与选号输出满足球号规则', async ({ request }) => {
    const strategies = await (await request.get('/api/strategies')).json()
    const names = strategies.map((item: { name: string }) => item.name)
    expect(names).toEqual(expect.arrayContaining(['random', 'hot', 'cold', 'balanced', 'mixed']))

    const res = await request.post('/api/predict', {
      data: { strategy: 'balanced', count: 5, params: { window: 30 } },
    })
    expect(res.ok()).toBeTruthy()
    const body = await res.json()
    expect(body.numbers).toHaveLength(5)

    for (const bet of body.numbers as Bet[]) {
      expect(bet.red).toHaveLength(6)
      expect(new Set(bet.red).size).toBe(6)
      expect([...bet.red]).toEqual([...bet.red].sort((a, b) => a - b))
      for (const n of bet.red) {
        expect(n).toBeGreaterThanOrEqual(1)
        expect(n).toBeLessThanOrEqual(33)
      }
      expect(bet.blue).toBeGreaterThanOrEqual(1)
      expect(bet.blue).toBeLessThanOrEqual(16)
    }
  })

  test('回测结果自洽（样本、命中分布、卡方、奖级）', async ({ request }) => {
    const res = await request.post('/api/backtest', {
      data: { strategy: 'balanced', window: 50, periods: 100 },
    })
    expect(res.ok()).toBeTruthy()
    const body = await res.json()

    expect(body.samples).toBe(100)
    expect(body.window).toBe(50)
    expect(body.periods).toBe(100)

    const hitTotal = body.red_hits.reduce(
      (sum: number, item: { count: number }) => sum + item.count,
      0,
    )
    expect(hitTotal).toBe(100)
    expect(body.avg_red_hits).toBeGreaterThanOrEqual(0)
    expect(body.avg_red_hits).toBeLessThanOrEqual(6)

    expect(body.chi_square.df).toBe(3)
    expect(body.chi_square.p_value).toBeGreaterThanOrEqual(0)
    expect(body.chi_square.p_value).toBeLessThanOrEqual(1)
    const observed = body.chi_square.buckets.reduce(
      (sum: number, bucket: { observed: number }) => sum + bucket.observed,
      0,
    )
    expect(observed).toBe(100)

    expect(body.prize_levels).toHaveLength(6)
    const actualPrizes = body.prize_levels.reduce(
      (sum: number, prize: { actual: number }) => sum + prize.actual,
      0,
    )
    expect(actualPrizes).toBeLessThanOrEqual(100)
    expect(body.disclaimer).toContain('随机')
  })

  test('形态清单 A–R 共 18 项，仅 G 已实现', async ({ request }) => {
    const list = await (await request.get('/api/visualizers')).json()
    expect(list).toHaveLength(18)
    expect(list.map((item: { code: string }) => item.code).join('')).toBe('ABCDEFGHIJKLMNOPQR')
    const implemented = list.filter((item: { status: string }) => item.status === 'implemented')
    expect(implemented).toHaveLength(1)
    expect(implemented[0]).toMatchObject({ code: 'G', name: 'spiral_fourier' })
    const categories = new Set(list.map((item: { category: string }) => item.category))
    expect(categories.size).toBe(8)
  })

  test('螺旋骨架傅里叶可渲染并可提取特征', async ({ request }) => {
    const rendered = await request.post('/api/visualizers/spiral_fourier/render', {
      data: { type: 'ssq', periods: 1 },
    })
    expect(rendered.ok()).toBeTruthy()
    const body = await rendered.json()
    expect(body.type).toBe('spiral_fourier')
    expect(body.data.points.length).toBeGreaterThan(500)
    expect(body.data.harmonics).toHaveLength(6)
    expect(body.data).toHaveProperty('turns')
    expect(body.data).toHaveProperty('tightness')

    const features = await request.post('/api/visualizers/spiral_fourier/features', {
      data: { type: 'ssq', periods: 1 },
    })
    expect(features.ok()).toBeTruthy()
    const featureBody = await features.json()
    expect(featureBody.code).toBe('G')
    expect(featureBody.features.dominant_harmonic).toBeGreaterThanOrEqual(1)
    expect(featureBody.features.arc_length).toBeGreaterThan(0)
  })

  test('未实现算法 501、未知算法 404、非法策略 404', async ({ request }) => {
    const planned = await request.post('/api/visualizers/fourier_curve/render', {
      data: { type: 'ssq', periods: 30 },
    })
    expect(planned.status()).toBe(501)

    const unknown = await request.post('/api/visualizers/not_exists/render', {
      data: { type: 'ssq' },
    })
    expect(unknown.status()).toBe(404)

    const badStrategy = await request.post('/api/predict', {
      data: { strategy: 'no_such', count: 1 },
    })
    expect(badStrategy.status()).toBe(404)
  })
})

import { test, expect } from '@playwright/test'
import { PAGES, gotoPage } from './helpers'

test.describe('关键交互流程', () => {
  test('历史页按期号/日期搜索与清除', async ({ page, request }) => {
    await page.goto('/#history')
    const rows = page.locator('.data-table tbody tr')
    await expect(rows).toHaveCount(20)

    const latest = (await (await request.get('/api/history', { params: { type: 'ssq', size: 1 } })).json())
      .items[0]
    const input = page.locator('.search-input')

    await input.fill(latest.issue)
    await page.getByRole('button', { name: '搜索' }).click()
    await expect(rows).toHaveCount(1)
    await expect(rows.first()).toContainText(latest.issue)

    await page.getByRole('button', { name: '清除' }).click()
    await expect(rows).toHaveCount(20)
    await expect(input).toHaveValue('')

    const month = String(latest.draw_date).slice(0, 7)
    await input.fill(month)
    await page.getByRole('button', { name: '搜索' }).click()

    const byDate = await (
      await request.get('/api/history', { params: { type: 'ssq', q: month, size: 20 } })
    ).json()
    await expect(rows).toHaveCount(byDate.items.length)
    for (let i = 0; i < byDate.items.length; i += 1) {
      await expect(rows.nth(i)).toContainText(month)
    }
  })

  test('历史页翻页后首行变化', async ({ page }) => {
    await page.goto('/#history')
    const rows = page.locator('.data-table tbody tr')
    await expect(rows).toHaveCount(20)

    const firstIssue = rows.first().locator('td.mono').first()
    const before = await firstIssue.innerText()

    await page.getByRole('button', { name: '下一页' }).click()
    await expect(page.locator('.pager-info')).toContainText('2 /')
    await expect(firstIssue).not.toHaveText(before)
  })

  test('选号页生成 5 注且球号合法', async ({ page }) => {
    await page.goto('/#predict')
    await page.locator('.predict-controls select').selectOption('balanced')
    await page.locator('.predict-controls input[type="number"]').first().fill('5')
    await page.getByRole('button', { name: '生成号码' }).click()

    const cards = page.locator('.bet-card')
    await expect(cards).toHaveCount(5)

    for (let i = 0; i < 5; i += 1) {
      const card = cards.nth(i)
      const reds = card.locator('.ball.ball-red')
      await expect(reds).toHaveCount(6)
      await expect(card.locator('.ball.ball-blue')).toHaveCount(1)

      const values = (await reds.allInnerTexts()).map((text) => Number(text))
      expect(new Set(values).size).toBe(6)
      expect([...values].sort((a, b) => a - b)).toEqual(values)
      for (const value of values) {
        expect(value).toBeGreaterThanOrEqual(1)
        expect(value).toBeLessThanOrEqual(33)
      }
    }
    await expect(page.locator('.disclaimer')).toContainText('纯随机等价')
  })

  test('回测页跑通全部策略并给出显著性结论', async ({ page, request }) => {
    test.setTimeout(180_000)
    const strategies = await (await request.get('/api/strategies')).json()

    await page.goto('/#backtest')
    await page.locator('.backtest-controls select').first().selectOption('50')
    await page.locator('.backtest-controls select').nth(1).selectOption('100')
    await page.getByRole('button', { name: '运行回测（全部策略）' }).click()

    const cards = page.locator('.backtest-card')
    await expect(cards).toHaveCount(strategies.length, { timeout: 150_000 })

    for (let i = 0; i < strategies.length; i += 1) {
      const card = cards.nth(i)
      await expect(card.locator('.tag')).toContainText(
        /p = \d+\.\d{4} · (无显著差异|有显著偏差)/,
      )
      await expect(card.locator('.mini-table tbody tr')).toHaveCount(6)
      await expect(card.locator('.chip-row .chip')).toHaveCount(4)
      await expect(card.locator('.bar-chart .bar-col')).toHaveCount(7)
    }
    await expect(page.getByRole('button', { name: '运行回测（全部策略）' })).toBeEnabled()
  })
})

test.describe('移动端 375px 布局', () => {
  test.use({ viewport: { width: 375, height: 812 } })

  test('六个页面均无横向溢出', async ({ page }) => {
    await page.goto('/')
    for (const item of PAGES) {
      await gotoPage(page, item.title)
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      )
      expect(overflow, `${item.title} 出现横向溢出`).toBeLessThanOrEqual(1)
    }
  })
})

import { test, expect } from '@playwright/test'
import { PAGES, gotoPage } from './helpers'

test.describe('页面渲染', () => {
  test('六个页面均可导航且无运行时异常', async ({ page }) => {
    const pageErrors: string[] = []
    page.on('pageerror', (error) => pageErrors.push(error.message))

    await page.goto('/')
    for (const item of PAGES) {
      await gotoPage(page, item.title)
      await expect(page).toHaveURL(new RegExp(`#${item.hash}$`))
    }
    expect(pageErrors).toEqual([])
  })

  test('历史页默认 20 行且首页/上一页禁用', async ({ page }) => {
    await page.goto('/#history')
    await expect(page.locator('.data-table tbody tr')).toHaveCount(20)
    await expect(page.getByRole('button', { name: '首页' })).toBeDisabled()
    await expect(page.getByRole('button', { name: '上一页' })).toBeDisabled()
    await expect(page.getByRole('button', { name: '下一页' })).toBeEnabled()
    await expect(page.locator('.pager-info')).toContainText('/')
  })

  test('统计页四张指标卡与 33/16 根频次柱', async ({ page, request }) => {
    await page.goto('/#stats')
    await expect(page.locator('.stat-card')).toHaveCount(4)
    await expect(page.locator('.bar-chart').first().locator('.bar-col')).toHaveCount(33)
    await expect(page.locator('.bar-chart').nth(1).locator('.bar-col')).toHaveCount(16)

    const total = (await (await request.get('/api/history', { params: { size: 1 } })).json()).total
    await page.getByRole('button', { name: '全部' }).click()
    await expect(page.locator('.stat-card').first()).toContainText(`${total} 期`)
  })

  test('选号页策略下拉与空态', async ({ page, request }) => {
    await page.goto('/#predict')
    await expect(page.locator('.empty-state')).toBeVisible()

    const strategies = await (await request.get('/api/strategies')).json()
    const select = page.locator('.predict-controls select')
    await expect(select.locator('option')).toHaveCount(strategies.length)
    await expect(page.locator('.alert-warn')).toContainText('独立随机')
  })

  test('回测页空态与控件可用', async ({ page }) => {
    await page.goto('/#backtest')
    await expect(page.locator('.empty-state')).toBeVisible()
    await expect(page.getByRole('button', { name: '运行回测（全部策略）' })).toBeEnabled()
  })

  test('形态页 18 卡 / 8 组 / 36 个禁用按钮', async ({ page }) => {
    await page.goto('/#visualizer')
    await expect(page.locator('.viz-card')).toHaveCount(18)
    await expect(page.locator('.viz-group')).toHaveCount(8)

    const buttons = page.locator('.viz-card button')
    await expect(buttons).toHaveCount(36)
    for (let i = 0; i < 36; i += 1) {
      await expect(buttons.nth(i)).toBeDisabled()
    }
    await expect(page.locator('.viz-summary')).toContainText('算法总数')
  })

  test('同步页状态卡与手动同步按钮', async ({ page, request }) => {
    await page.goto('/#sync')
    const lotteries = await (await request.get('/api/lotteries')).json()
    await expect(page.locator('.sync-card')).toHaveCount(lotteries.length)
    await expect(page.getByRole('button', { name: '立即同步' })).toBeEnabled()
    await expect(page.getByRole('heading', { name: '最近同步日志' })).toBeVisible()
  })
})

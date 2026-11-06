import { expect, type Page } from '@playwright/test'

export const PAGES = [
  { hash: 'history', title: '历史开奖' },
  { hash: 'stats', title: '统计分析' },
  { hash: 'predict', title: '选号预测' },
  { hash: 'backtest', title: '策略回测' },
  { hash: 'visualizer', title: '形态分析' },
  { hash: 'sync', title: '数据同步' },
] as const

export async function gotoPage(page: Page, title: string): Promise<void> {
  await page.getByRole('button', { name: title, exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible()
}

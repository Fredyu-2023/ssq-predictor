import { defineConfig } from '@playwright/test'
import { BACKEND_DIR, BACKEND_URL, E2E_DB, FRONTEND_DIR, FRONTEND_URL } from './e2e/paths'

// e2e 说明：
// - 后端用隔离副本库（e2e/.tmp/e2e.db）启动，关闭启动自动同步，不访问外网、不改真实库；
// - 前端用 Vite dev server，/api 经其代理到后端，因此测试同时覆盖代理链路；
// - 串行执行（workers=1），避免同一库上的并发读写干扰断言。
export default defineConfig({
  testDir: './e2e',
  testMatch: /.*\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: FRONTEND_URL,
    viewport: { width: 1440, height: 900 },
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command:
        'python ../frontend/e2e/prepare_db.py && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --log-level warning',
      cwd: BACKEND_DIR,
      url: `${BACKEND_URL}/api/health`,
      timeout: 60_000,
      reuseExistingServer: false,
      env: {
        ...(process.env as Record<string, string>),
        AUTO_SYNC_ON_STARTUP: 'false',
        SSQ_DB_PATH: E2E_DB,
      },
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort',
      cwd: FRONTEND_DIR,
      url: FRONTEND_URL,
      timeout: 60_000,
      reuseExistingServer: false,
    },
  ],
})

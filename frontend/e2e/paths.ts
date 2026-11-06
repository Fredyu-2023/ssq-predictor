import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))

export const FRONTEND_DIR = path.resolve(here, '..')
export const BACKEND_DIR = path.resolve(here, '..', '..', 'backend')
export const E2E_DB = path.join(here, '.tmp', 'e2e.db')

export const BACKEND_URL = 'http://127.0.0.1:8000'
export const FRONTEND_URL = 'http://127.0.0.1:5173'

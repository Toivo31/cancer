import type { Api } from './client'
import { http } from './client'
import { mock } from '../mock/mockApi'

export { ApiError } from './client'
export type { Api } from './client'

const MODE_KEY = 'pathway-api-mode'

/** ?mock=1 (or ?mock=0) in the address chooses and remembers the mode. Otherwise: probe the service. */
export async function chooseApi(search = window.location.search): Promise<{ api: Api; reason: string | null }> {
  const q = new URLSearchParams(search).get('mock')
  if (q === '1') { localStorage.setItem(MODE_KEY, 'mock'); return { api: mock, reason: 'Demo data (mock mode), as requested in the address.' } }
  if (q === '0') localStorage.removeItem(MODE_KEY)
  else if (localStorage.getItem(MODE_KEY) === 'mock') return { api: mock, reason: 'Demo data (mock mode).' }
  try {
    await http.templates()
    return { api: http, reason: null }
  } catch {
    return { api: mock, reason: 'The service did not answer, so this page shows demo data held in the browser.' }
  }
}

import { createContext, useContext } from 'react'
import type { Api } from './api'

export const ApiCtx = createContext<Api | null>(null)
export function useApi(): Api {
  const a = useContext(ApiCtx)
  if (!a) throw new Error('ApiCtx missing')
  return a
}

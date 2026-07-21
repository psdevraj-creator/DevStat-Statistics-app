import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock axios before importing client
vi.mock('axios', () => {
  const mockPost = vi.fn().mockResolvedValue({ data: {} })
  return {
    default: {
      create: () => ({
        post: mockPost,
        get: vi.fn().mockResolvedValue({ data: {} }),
        interceptors: {
          request: { use: vi.fn(), eject: vi.fn() },
          response: { use: vi.fn(), eject: vi.fn() },
        },
      }),
    },
  }
})

import { regressionApi, api } from './client'

describe('regressionApi.run', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('passes through the method parameter for linear regression', async () => {
    await regressionApi.run('dataset1', 'linear', 'y', ['x1', 'x2'], 'stepwise')
    const axios = await import('axios')
    const instance = axios.default.create()
    expect(instance.post).toHaveBeenCalledWith(
      '/api/analysis/linear-regression',
      { dependent: 'y', independents: ['x1', 'x2'], method: 'stepwise', family: 'linear' }
    )
  })

  it('passes through the method parameter for logistic regression', async () => {
    await regressionApi.run('dataset1', 'logistic', 'y', ['x1'], 'backward')
    const axios = await import('axios')
    const instance = axios.default.create()
    expect(instance.post).toHaveBeenCalledWith(
      '/api/analysis/logistic-regression',
      { dependent: 'y', independents: ['x1'], method: 'backward', family: 'logistic' }
    )
  })

  it('uses enter as default method when none provided', async () => {
    await regressionApi.run('dataset1', 'linear', 'y', ['x1'], '')
    const axios = await import('axios')
    const instance = axios.default.create()
    expect(instance.post).toHaveBeenCalledWith(
      '/api/analysis/linear-regression',
      { dependent: 'y', independents: ['x1'], method: 'enter', family: 'linear' }
    )
  })

  it('uses enter as default when method is undefined', async () => {
    await regressionApi.run('dataset1', 'linear', 'y', ['x1'], undefined as any)
    const axios = await import('axios')
    const instance = axios.default.create()
    expect(instance.post).toHaveBeenCalledWith(
      '/api/analysis/linear-regression',
      { dependent: 'y', independents: ['x1'], method: 'enter', family: 'linear' }
    )
  })
})

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { OperationsPage } from './OperationsPage'

vi.mock('../components/CompanyContext', () => ({
  useCompanyContext: () => ({ company: { company_id: 'C001' }, dataAvailable: true }),
}))
vi.mock('../hooks/queries', () => ({
  keys: { operations: (companyId: string, params: string) => ['operations', companyId, params] },
}))
vi.mock('../api/client', () => ({
  api: { operations: vi.fn() },
}))

const operation = {
  operation_id: 'C001-1',
  company_id: 'C001',
  operation_date: '2025-01-01',
  amount: 100,
  signed_amount: -100,
  direction: 'списание' as const,
  counterparty_inn: '001',
  counterparty_name: 'Контрагент',
  payment_purpose: 'Неизвестная операция',
  balance_eod: 900,
  category: 'Прочие расходы',
  category_method: 'правила',
  confidence: 0.55,
  needs_review: false,
}

describe('OperationsPage', () => {
  beforeEach(() => {
    vi.mocked(api.operations).mockReset()
  })

  it('renders the API category as read-only and filters by category', async () => {
    vi.mocked(api.operations).mockResolvedValue({
      items: [operation],
      total: 1,
      page: 1,
      page_size: 30,
    })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter><OperationsPage /></MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByRole('cell', { name: 'Прочие расходы' })).toBeInTheDocument()
    expect(screen.getByLabelText('Категория')).toBeInTheDocument()
    expect(screen.queryByLabelText('Категория C001-1')).not.toBeInTheDocument()
    expect(screen.queryByText('Проверьте вручную')).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Категория'), { target: { value: 'Прочие расходы' } })
    await waitFor(() => expect(api.operations).toHaveBeenCalledTimes(2))
    expect(vi.mocked(api.operations).mock.calls[1][1].get('category')).toBe('Прочие расходы')
  })
})

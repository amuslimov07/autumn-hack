import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { CompaniesPage } from './CompaniesPage'

vi.mock('../hooks/queries', () => ({
  keys: { overview: ['overview'] },
}))
vi.mock('@tanstack/react-query', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-query')>()
  return { ...actual, useQuery: () => ({ isLoading: false, error: null, data: { companies: 1, operations: 2, rows: [
    { company_id: 'C001', name: 'Тестовая компания', inn: '00123', industry: 'Торговля', legal_form: 'ООО', first_operation_date: '2025-01-01', last_operation_date: '2025-02-01', operation_count: 2, last_balance: 100, balance_date: '2025-02-01' },
  ] } }) }
})

describe('CompaniesPage', () => {
  it('renders API company data and filters', () => {
    const client = new QueryClient()
    render(<QueryClientProvider client={client}><MemoryRouter><CompaniesPage /></MemoryRouter></QueryClientProvider>)
    expect(screen.getByText('Тестовая компания')).toBeInTheDocument()
    expect(screen.getByLabelText('Фильтр отрасли')).toBeInTheDocument()
  })
})

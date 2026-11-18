import { useCallback, useEffect, useMemo, useState } from 'react'
import { Building2, Pencil, Search, Trash2 } from 'lucide-react'

import {
  createSchool,
  deleteSchool,
  fetchSchools,
  updateSchool,
} from '../../lib/api'
import type { ApiError } from '../../lib/api'
import type { School, SchoolCreateInput } from '../../lib/types'

type FormState = SchoolCreateInput & { id?: number | null }

export function AdminSchoolManager() {
  const [schools, setSchools] = useState<School[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  const buildEmptyForm = (): FormState => ({
    id: null,
    name: '',
    code: '',
    description: '',
    contact_email: '',
    contact_phone: '',
    address: '',
    city: '',
    state: '',
  })
  const [form, setForm] = useState<FormState>(() => buildEmptyForm())

  const loadSchools = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchSchools()
      setSchools(data)
    } catch (err: any) {
      setError(err?.message || 'Não foi possível carregar as escolas.')
      setSchools([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadSchools()
  }, [loadSchools])

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return schools
    return schools.filter(
      (school) =>
        school.name.toLowerCase().includes(query) ||
        (school.code ?? '').toLowerCase().includes(query),
    )
  }, [schools, search])

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!form.name.trim()) {
      setStatus('Informe o nome da instituição.')
      return
    }
    setStatus(form.id ? 'Atualizando dados...' : 'Cadastrando unidade...')
    const payload = {
      name: form.name.trim(),
      code: form.code?.trim() || undefined,
      description: form.description?.trim() || undefined,
      contact_email: form.contact_email?.trim() || undefined,
      contact_phone: form.contact_phone?.trim() || undefined,
      address: form.address?.trim() || undefined,
      city: form.city?.trim() || undefined,
      state: form.state?.trim() || undefined,
    }
    try {
      if (form.id) {
        await updateSchool(form.id, payload)
      } else {
        await createSchool(payload)
      }
      setForm(buildEmptyForm())
      await loadSchools()
      setStatus(form.id ? 'Unidade atualizada com sucesso.' : 'Unidade cadastrada com sucesso.')
    } catch (err: any) {
      setStatus(err?.message || 'Não foi possível salvar a unidade.')
    }
  }

  const handleEdit = (school: School) => {
    setForm({
      id: school.id,
      name: school.name,
      code: school.code ?? '',
      description: school.description ?? '',
      contact_email: school.contact_email ?? '',
      contact_phone: school.contact_phone ?? '',
      address: school.address ?? '',
      city: school.city ?? '',
      state: school.state ?? '',
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleDelete = async (schoolId: number) => {
    if (!window.confirm('Deseja remover esta unidade escolar?')) return
    setStatus('Removendo unidade...')
    try {
      await deleteSchool(schoolId)
      await loadSchools()
      setStatus('Unidade removida.')
    } catch (err: any) {
      const code = (err as ApiError)?.status
      setStatus(
        code === 409
          ? 'Não é possível remover uma unidade que já possui turmas, matérias ou usuários vinculados.'
          : err?.message || 'Não foi possível remover a unidade.',
      )
    }
  }

  return (
    <div className="space-y-6">
      <section className="card p-5 sm:p-6 space-y-5">
        <div>
          <h2 className="text-base sm:text-lg font-semibold text-slate-900">
            {form.id ? 'Editar unidade escolar' : 'Cadastrar nova unidade'}
          </h2>
          <p className="text-sm text-slate-500">
            Adicione ou atualize as instituições habilitadas na plataforma.
          </p>
        </div>

        <form className="grid gap-4 sm:grid-cols-2" onSubmit={handleSubmit}>
          <div>
            <label className="label">Nome da instituição</label>
            <input
              className="input"
              placeholder="Ex.: Colégio Horizonte"
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              required
            />
          </div>
          <div>
            <label className="label">Código identificador</label>
            <input
              className="input"
              placeholder="Ex.: CH-01"
              value={form.code ?? ''}
              onChange={(event) => setForm((prev) => ({ ...prev, code: event.target.value }))}
            />
          </div>
          <div>
            <label className="label">E-mail institucional</label>
            <input
              className="input"
              type="email"
              placeholder="secretaria@escola.edu.br"
              value={form.contact_email ?? ''}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, contact_email: event.target.value }))
              }
            />
          </div>
          <div>
            <label className="label">Telefone</label>
            <input
              className="input"
              placeholder="(11) 3000-0000"
              value={form.contact_phone ?? ''}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, contact_phone: event.target.value }))
              }
            />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Endereço</label>
            <input
              className="input"
              placeholder="Rua, número e bairro"
              value={form.address ?? ''}
              onChange={(event) => setForm((prev) => ({ ...prev, address: event.target.value }))}
            />
          </div>
          <div>
            <label className="label">Cidade</label>
            <input
              className="input"
              value={form.city ?? ''}
              onChange={(event) => setForm((prev) => ({ ...prev, city: event.target.value }))}
            />
          </div>
          <div>
            <label className="label">UF</label>
            <input
              className="input"
              maxLength={2}
              placeholder="SP"
              value={form.state ?? ''}
              onChange={(event) => setForm((prev) => ({ ...prev, state: event.target.value }))}
            />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Observações</label>
            <textarea
              className="input min-h-[80px]"
              value={form.description ?? ''}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, description: event.target.value }))
              }
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 sm:col-span-2 pt-1">
            <div>
              {status && <p className="text-sm text-slate-600">{status}</p>}
              {error && <p className="text-sm text-rose-600">{error}</p>}
            </div>
            <div className="flex gap-2 w-full sm:w-auto">
              {form.id && (
                <button
                  type="button"
                  className="btn-secondary flex-1 sm:flex-initial"
                  onClick={() => setForm(buildEmptyForm())}
                >
                  Cancelar
                </button>
              )}
              <button
                type="submit"
                className="btn flex-1 sm:flex-initial"
                disabled={loading}
              >
                <Building2 className="h-4 w-4" strokeWidth={1.75} />
                {form.id ? 'Salvar alterações' : 'Cadastrar unidade'}
              </button>
            </div>
          </div>
        </form>
      </section>

      <section className="card p-5 sm:p-6 space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-base font-semibold text-slate-900">Unidades registradas</h3>
            <p className="text-xs text-slate-500">
              {filtered.length} de {schools.length} unidade(s)
            </p>
          </div>
          <div className="relative w-full sm:w-64">
            <Search className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              className="input pl-9"
              placeholder="Buscar nome ou código..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
        </div>

        {loading ? (
          <p className="text-sm text-slate-500 py-4">Carregando unidades...</p>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-slate-500 py-6 text-center border border-dashed border-slate-200 rounded-xl">
            Nenhuma unidade escolar encontrada.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200/80 overflow-hidden">
            {filtered.map((school) => (
              <li
                key={school.id}
                className="p-4 bg-white hover:bg-slate-50/60 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 transition-colors"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-slate-900 truncate">{school.name}</p>
                    {school.code && (
                      <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                        {school.code}
                      </span>
                    )}
                  </div>
                  {(school.city || school.contact_email) && (
                    <p className="text-xs text-slate-500 mt-0.5">
                      {[
                        school.city && school.state ? `${school.city}/${school.state}` : school.city,
                        school.contact_email,
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    onClick={() => handleEdit(school)}
                  >
                    <Pencil className="h-3 w-3" />
                    Editar
                  </button>
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-rose-200 text-xs font-medium text-rose-700 hover:bg-rose-50"
                    onClick={() => handleDelete(school.id)}
                  >
                    <Trash2 className="h-3 w-3" />
                    Excluir
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

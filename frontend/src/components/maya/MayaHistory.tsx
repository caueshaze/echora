import { useCallback, useEffect, useRef, useState } from 'react'
import { askMaya, fetchMayaAnalysis, fetchMayaHistory, fetchMayaMessages, fetchMayaQuota } from '../../lib/api'
import type { MayaAnalysis, MayaMessage, MayaQuota } from '../../lib/api'
import { ExecutiveReport } from '../gestor/ExecutiveReport'
import type { FeedbackSummary } from '../../lib/types'

type Role = 'gestor' | 'professor' | 'aluno'
const suggestions: Record<Role, string[]> = {
  gestor: ['Quais problemas merecem atenção primeiro?', 'Como podemos melhorar os pontos de atenção identificados?', 'Crie um plano de ação para os próximos 30 dias.'],
  professor: ['O que posso melhorar nas minhas aulas?', 'Quais aspectos positivos devo continuar desenvolvendo?', 'Como posso aplicar essas recomendações na próxima aula?'],
  aluno: ['Quais são meus principais pontos de melhoria?', 'Como posso organizar meus estudos?', 'O que posso fazer para melhorar meu desempenho?'],
}

export function MayaHistory({ role, summary }: { role: Role; summary: FeedbackSummary | null }) {
  const [items, setItems] = useState<MayaAnalysis[]>([])
  const [more, setMore] = useState(false)
  const [selected, setSelected] = useState<MayaAnalysis | null>(null)
  const [messages, setMessages] = useState<MayaMessage[]>([])
  const [quota, setQuota] = useState<MayaQuota | null>(null)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const request = useRef<{ text: string; analysis: string; key: string } | null>(null)

  const load = useCallback(async (offset = 0) => {
    setLoading(true)
    try {
      const result = await fetchMayaHistory(offset)
      setItems(old => offset ? [...old, ...result.items] : result.items)
      setMore(result.has_more)
    } catch { setError('Não foi possível carregar o histórico de análises.') }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void load() }, [load, summary])
  useEffect(() => { void fetchMayaQuota().then(setQuota).catch(() => setError('Não foi possível carregar o contador de perguntas.')) }, [])
  useEffect(() => {
    if (!quota?.reset_at) return
    const delay = Math.max(0, new Date(quota.reset_at).getTime() - Date.now()) + 1000
    const timer = window.setTimeout(() => {
      void fetchMayaQuota().then(setQuota).catch(() => setError('Não foi possível atualizar o contador de perguntas.'))
    }, delay)
    return () => window.clearTimeout(timer)
  }, [quota?.reset_at])
  useEffect(() => {
    if (!quota || quota.remaining > 0) return
    const timer = window.setInterval(() => {
      void fetchMayaQuota().then(setQuota).catch(() => {})
    }, 30000)
    return () => window.clearInterval(timer)
  }, [quota?.remaining])

  async function choose(id: string) {
    setError(null); setSelected(null); setMessages([]); setLoading(true); request.current = null
    try {
      const [analysis, conversation] = await Promise.all([fetchMayaAnalysis(id), fetchMayaMessages(id)])
      setSelected(analysis); setMessages(conversation.items); setQuota(conversation.quota)
    } catch { setError('Não foi possível abrir esta análise.') }
    finally { setLoading(false) }
  }
  async function send() {
    const text = draft.trim()
    if (!selected || !text || busy || !quota?.remaining) return
    setBusy(true); setError(null)
    if (!request.current || request.current.text !== text || request.current.analysis !== selected.id)
      request.current = { text, analysis: selected.id, key: crypto.randomUUID() }
    try {
      const result = await askMaya(selected.id, text, request.current.key)
      setMessages(old => old.some(item => item.id === result.message.id) ? old : [...old, result.message])
      setQuota(result.quota); setDraft(''); request.current = null
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Não foi possível enviar a pergunta.')
      try { setQuota(await fetchMayaQuota()) } catch { setQuota(null) }
    } finally { setBusy(false) }
  }
  return (
    <section className="card p-5 sm:p-6 space-y-4 min-w-0">
      <h2 className="text-base sm:text-lg font-semibold">Histórico de análises</h2>
      {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
      {loading && <p role="status" className="text-sm text-slate-600">Carregando...</p>}
      {!loading && !items.length && <p className="text-sm text-slate-600">Suas análises aparecerão aqui após a geração.</p>}
      {!loading && items.length > 0 && !selected && <p className="text-sm text-slate-600">Selecione uma análise para consultar e conversar com a Maya.</p>}
      <ul className="space-y-2">{items.map(item => <li key={item.id}>
        <button type="button" onClick={() => void choose(item.id)} disabled={busy || loading} className="w-full min-h-[44px] rounded-lg border border-slate-200 p-3 text-left text-sm hover:bg-brand-50 disabled:opacity-50" aria-pressed={selected?.id === item.id}>
          {new Date(item.created_at.endsWith('Z') || item.created_at.includes('+') ? item.created_at : item.created_at + 'Z').toLocaleString('pt-BR')} · {item.kind === 'institucional' ? 'Institucional' : item.kind === 'professor' ? 'Professor' : 'Aluno'}
        </button></li>)}</ul>
      {more && <button type="button" className="btn-secondary" onClick={() => void load(items.length)} disabled={loading}>Ver mais</button>}
      {selected && <div className="border-t border-slate-200 pt-4 space-y-5 min-w-0">
        <ExecutiveReport text={selected.summary_text || ''} />
        <section aria-label="Pergunte à Maya" className="space-y-4 min-w-0">
          <h3 className="font-semibold">Pergunte à Maya</h3>
          {messages.map(message => <div key={message.id} className="space-y-2 text-sm min-w-0">
            <p className="rounded-lg bg-slate-100 p-3 whitespace-pre-wrap [overflow-wrap:anywhere]"><strong>Você:</strong> {message.question}</p>
            <div className="rounded-lg bg-brand-50 p-3"><p className="font-semibold text-brand-700 mb-2">Maya</p><ExecutiveReport text={message.answer} /></div>
          </div>)}
          {!messages.length && <p className="text-sm text-slate-600">Faça uma pergunta sobre esta análise.</p>}
          <div className="flex flex-wrap gap-2">{suggestions[role].map(text => <button key={text} type="button" className="btn-secondary text-left" onClick={() => setDraft(text)} disabled={busy || !quota?.remaining}>{text}</button>)}</div>
          <label htmlFor="maya-question" className="label">Sua pergunta</label>
          <textarea id="maya-question" className="input w-full resize-y" rows={3} maxLength={2000} value={draft} onChange={event => setDraft(event.target.value)} disabled={busy || !quota?.remaining} />
          <p className="text-sm text-slate-600" aria-live="polite">{quota ? quota.remaining ? `${quota.remaining} de ${quota.limit} perguntas restantes hoje` : `Você utilizou suas ${quota.limit} perguntas de hoje. Novas perguntas estarão disponíveis amanhã.` : 'Carregando limite de perguntas...'}</p>
          {busy && <p role="status" className="text-sm text-slate-600">Maya está respondendo...</p>}
          <button type="button" className="btn" onClick={() => void send()} disabled={busy || !draft.trim() || !quota?.remaining}>{busy ? 'Maya está respondendo...' : 'Enviar pergunta'}</button>
        </section>
      </div>}
    </section>
  )
}

import { useCallback, useEffect, useRef, useState } from 'react'
import { Sparkles } from 'lucide-react'
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
  const [selecting, setSelecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const request = useRef<{ text: string; analysis: string; key: string } | null>(null)
  const selectionVersion = useRef(0)

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

  const choose = useCallback(async (id: string) => {
    const version = ++selectionVersion.current
    setError(null); setSelected(null); setMessages([]); setDraft(''); setSelecting(true); request.current = null
    try {
      const [analysis, conversation] = await Promise.all([fetchMayaAnalysis(id), fetchMayaMessages(id)])
      if (version === selectionVersion.current) {
        setSelected(analysis); setMessages(conversation.items); setQuota(conversation.quota)
      }
    } catch { if (version === selectionVersion.current) setError('Não foi possível abrir esta análise.') }
    finally { if (version === selectionVersion.current) setSelecting(false) }
  }, [])

  useEffect(() => {
    if (!summary) return
    if (summary.analysis_id) {
      void choose(summary.analysis_id)
    } else {
      selectionVersion.current++
      setSelected(null); setSelecting(false)
      setError('Não foi possível abrir a conversa desta análise. Consulte o histórico para selecioná-la.')
    }
  }, [summary, choose])
  async function send() {
    const text = draft.trim()
    if (!selected || !text || busy || !quota?.remaining) return
    const version = selectionVersion.current
    setBusy(true); setError(null)
    if (!request.current || request.current.text !== text || request.current.analysis !== selected.id)
      request.current = { text, analysis: selected.id, key: crypto.randomUUID() }
    try {
      const result = await askMaya(selected.id, text, request.current.key)
      setQuota(result.quota)
      if (version === selectionVersion.current) {
        setMessages(old => old.some(item => item.id === result.message.id) ? old : [...old, result.message])
        setDraft(''); request.current = null
      }
    } catch (e) {
      if (version === selectionVersion.current) setError(e instanceof Error ? e.message : 'Não foi possível enviar a pergunta.')
      try { setQuota(await fetchMayaQuota()) } catch { setQuota(null) }
    } finally { setBusy(false) }
  }
  return (
    <div className="space-y-5 min-w-0">
      {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
      {selecting && <p role="status" className="text-sm text-slate-600">Abrindo conversa...</p>}
      {selected && <div className="card p-5 sm:p-6 space-y-5 min-w-0">
        {selected.id !== summary?.analysis_id && <div className="space-y-3">
          <h2 className="text-base font-semibold">Análise selecionada do histórico</h2>
          <ExecutiveReport text={selected.summary_text || ''} />
        </div>}
        <section aria-label="Pergunte à Maya" className="space-y-4 min-w-0">
          <h3 className="font-semibold">Pergunte à Maya</h3>
          {messages.map(message => <div key={message.id} className="space-y-2 text-sm min-w-0 animate-fadeUp">
            <p className="rounded-lg bg-slate-100 p-3 whitespace-pre-wrap [overflow-wrap:anywhere]"><strong>Você:</strong> {message.question}</p>
            <div className="rounded-lg bg-brand-50 p-3"><p className="font-semibold text-brand-700 mb-2">Maya</p><ExecutiveReport text={message.answer} /></div>
          </div>)}
          {!messages.length && <p className="text-sm text-slate-600">Faça uma pergunta sobre esta análise.</p>}
          <div className="flex flex-wrap gap-2">{suggestions[role].map(text => <button key={text} type="button" className="btn-secondary text-left" onClick={() => setDraft(text)} disabled={busy || !quota?.remaining}>{text}</button>)}</div>
          <label htmlFor="maya-question" className="label">Sua pergunta</label>
          <textarea id="maya-question" className="input w-full resize-y" rows={3} maxLength={2000} value={draft} onChange={event => setDraft(event.target.value)} disabled={busy || !quota?.remaining} />
          <p className="text-sm text-slate-600" aria-live="polite">{quota ? quota.remaining ? `${quota.remaining} de ${quota.limit} perguntas restantes hoje` : `Você utilizou suas ${quota.limit} perguntas de hoje. Novas perguntas estarão disponíveis amanhã.` : 'Carregando limite de perguntas...'}</p>
          {busy && (
            <div role="status" className="inline-flex items-center gap-2 rounded-lg bg-brand-50/70 border border-brand-200/70 px-3 py-2 text-sm text-brand-800 animate-fadeIn">
              <Sparkles className="h-4 w-4 animate-pulse shrink-0" />
              <span>Maya está respondendo...</span>
              <span className="inline-flex items-center gap-1 ml-1" aria-hidden="true">
                <span className="h-1.5 w-1.5 rounded-full bg-brand-600 dark:bg-brand-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="h-1.5 w-1.5 rounded-full bg-brand-600 dark:bg-brand-400 animate-bounce" style={{ animationDelay: '120ms' }} />
                <span className="h-1.5 w-1.5 rounded-full bg-brand-600 dark:bg-brand-400 animate-bounce" style={{ animationDelay: '240ms' }} />
              </span>
            </div>
          )}
          <button type="button" className="btn" onClick={() => void send()} disabled={busy || !draft.trim() || !quota?.remaining}>{busy ? 'Maya está respondendo...' : 'Enviar pergunta'}</button>
        </section>
      </div>}
      <section className="card p-5 sm:p-6 space-y-4 min-w-0">
        <h2 className="text-base sm:text-lg font-semibold">Histórico de análises</h2>
        {loading && <p role="status" className="text-sm text-slate-600">Carregando...</p>}
        {!loading && !items.length && <p className="text-sm text-slate-600">Suas análises aparecerão aqui após a geração.</p>}
        {!loading && items.length > 0 && !selected && <p className="text-sm text-slate-600">Selecione uma análise para consultar e conversar com a Maya.</p>}
        <ul className="space-y-2">{items.map(item => {
          const isSelected = selected?.id === item.id
          return (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => void choose(item.id)}
                disabled={busy || loading || selecting}
                className={`w-full min-h-[44px] rounded-lg border p-3 text-left text-sm transition-colors disabled:opacity-50 ${
                  isSelected
                    ? 'border-brand-600 bg-brand-50/70 text-brand-900 font-medium dark:border-brand-500 dark:bg-brand-950/50 dark:text-brand-200'
                    : 'border-slate-200 hover:bg-brand-50'
                }`}
                aria-pressed={isSelected}
              >
                {new Date(item.created_at.endsWith('Z') || item.created_at.includes('+') ? item.created_at : item.created_at + 'Z').toLocaleString('pt-BR')} · {item.kind === 'institucional' ? 'Institucional' : item.kind === 'professor' ? 'Professor' : 'Aluno'}
              </button>
            </li>
          )
        })}</ul>
        {more && <button type="button" className="btn-secondary" onClick={() => void load(items.length)} disabled={loading}>Ver mais</button>}
      </section>
    </div>
  )
}

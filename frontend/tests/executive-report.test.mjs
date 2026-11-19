import { after, before, test } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'

let server, ExecutiveReport, InsightSummaryCard
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'silent' })
  ;({ ExecutiveReport } = await server.ssrLoadModule('/src/components/gestor/ExecutiveReport.tsx'))
  ;({ InsightSummaryCard } = await server.ssrLoadModule('/src/components/gestor/InsightSummaryCard.tsx'))
})
after(async () => { await server?.close() })

test('renders structured and legacy reports', () => {
  const html = renderToStaticMarkup(React.createElement(ExecutiveReport, { text: '## Panorama\n\nTexto curto.\n\n- Primeiro\n- Segundo' }))
  assert.match(html, /<h2>Panorama<\/h2>/)
  assert.match(html, /<p>Texto curto\.<\/p>/)
  assert.match(html, /<ul>\s*<li>Primeiro<\/li>/)
  const old = renderToStaticMarkup(React.createElement(ExecutiveReport, { text: 'Primeira linha.\nSegunda linha.' }))
  assert.match(old, /Primeira linha\.\nSegunda linha\./)
})

test('never emits HTML, links, images, or executable content', () => {
  const text = '<script>alert(1)</script>\n\n<img src="https://example.com/a" onerror="alert(1)">\n\n![descrição](https://example.com/b) [perigoso](javascript:alert(1)) [link](https://example.com)'
  const html = renderToStaticMarkup(React.createElement(ExecutiveReport, { text }))
  assert.doesNotMatch(html, /<script|<img|<a\s|onerror=|href=|src=/i)
  assert.match(html, /descrição/)
  assert.match(html, /perigoso/)
})

test('shows report, loading, error and empty states', () => {
  const base = { summary: null, summaryLoading: false, summaryStatus: null, onGenerate() {} }
  const render = (props) => renderToStaticMarkup(React.createElement(InsightSummaryCard, { ...base, ...props }))
  assert.match(render({}), /Gerar análise/)
  assert.match(render({ summaryLoading: true }), /role="status"/)
  assert.match(render({ summaryStatus: 'Falha ao gerar análise' }), /role="alert"/)
  assert.match(render({ summary: { summary_text: '   ' } }), /Nenhuma análise foi disponibilizada/)
  assert.match(render({ summary: { summary_text: '## Diagnóstico\n\n' + 'texto '.repeat(1000) } }), /<h2>Diagnóstico<\/h2>/)
})

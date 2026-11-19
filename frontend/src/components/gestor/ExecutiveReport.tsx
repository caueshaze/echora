import ReactMarkdown from 'react-markdown'

/** Report text is untrusted: links and images are rendered as text, never fetched. */
export function ExecutiveReport({ text }: { text: string }) {
  return (
    <article className="min-w-0 border-l-2 border-brand-200 pl-4 text-sm leading-relaxed text-slate-800 [overflow-wrap:anywhere] [&>*+*]:mt-4 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-base [&_h2]:font-semibold [&_h3]:text-sm [&_h3]:font-semibold [&_h4]:text-sm [&_h4]:font-semibold [&_li+li]:mt-1 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:whitespace-pre-line [&_pre]:whitespace-pre-wrap [&_pre]:break-all [&_ul]:list-disc [&_ul]:pl-5">
      <ReactMarkdown
        skipHtml
        components={{
          a: ({ children }) => <>{children}</>,
          img: ({ alt }) => <>{alt || ''}</>,
        }}
      >
        {text}
      </ReactMarkdown>
    </article>
  )
}

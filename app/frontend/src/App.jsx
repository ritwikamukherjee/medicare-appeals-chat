import { useState, useRef, useEffect } from 'react'

// ── Minimal markdown renderer — no deps. Handles the dialect emitted by the
// supervisor agent: headers (#/##/###/####), bold/italic, inline code, fenced
// code blocks, ordered/unordered lists, horizontal rules, GFM tables.
function renderInline(text, keyPrefix) {
  const out = []
  let key = 0
  // Tokenize: code spans, bold, italic, links — process recursively where needed.
  const re = /(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|(__[^_\n]+__)|(\*[^*\n]+\*)|(_[^_\n]+_)|(\[([^\]]+)\]\(([^)]+)\))/g
  let last = 0
  let m
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index))
    if (m[1]) {
      out.push(<code key={`${keyPrefix}-c${key++}`} className="bg-slate-900 text-amber-300 px-1 py-0.5 rounded text-[11px] font-mono">{m[1].slice(1, -1)}</code>)
    } else if (m[2] || m[3]) {
      const inner = (m[2] || m[3]).slice(2, -2)
      out.push(<strong key={`${keyPrefix}-b${key++}`} className="font-semibold text-slate-100">{inner}</strong>)
    } else if (m[4] || m[5]) {
      const inner = (m[4] || m[5]).slice(1, -1)
      out.push(<em key={`${keyPrefix}-i${key++}`} className="italic text-slate-300">{inner}</em>)
    } else if (m[6]) {
      out.push(<a key={`${keyPrefix}-a${key++}`} href={m[8]} target="_blank" rel="noreferrer" className="text-teal-400 underline hover:text-teal-300">{m[7]}</a>)
    }
    last = re.lastIndex
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

function Markdown({ source }) {
  if (!source) return null
  const lines = source.replace(/\r\n/g, '\n').split('\n')
  const blocks = []
  let i = 0
  let blockKey = 0

  const flushList = (items, ordered) => {
    const Tag = ordered ? 'ol' : 'ul'
    blocks.push(
      <Tag key={`l-${blockKey++}`} className={`${ordered ? 'list-decimal' : 'list-disc'} list-outside pl-5 my-1.5 space-y-0.5 marker:text-slate-500`}>
        {items.map((it, idx) => (
          <li key={idx} className="leading-relaxed">{renderInline(it, `l${blockKey}-${idx}`)}</li>
        ))}
      </Tag>
    )
  }

  while (i < lines.length) {
    const line = lines[i]
    // Fenced code block
    const fence = line.match(/^```(\w*)\s*$/)
    if (fence) {
      const buf = []
      i++
      while (i < lines.length && !lines[i].match(/^```\s*$/)) {
        buf.push(lines[i])
        i++
      }
      i++ // skip closing fence
      blocks.push(
        <pre key={`p-${blockKey++}`} className="my-2 overflow-x-auto bg-slate-900 border border-slate-700 rounded-md p-2.5">
          <code className="text-[11px] font-mono text-slate-200 whitespace-pre-wrap break-words">{buf.join('\n')}</code>
        </pre>
      )
      continue
    }
    // Horizontal rule
    if (/^\s*(---+|\*\*\*+|___+)\s*$/.test(line)) {
      blocks.push(<hr key={`h-${blockKey++}`} className="my-3 border-slate-700" />)
      i++
      continue
    }
    // Headings
    const h = line.match(/^(#{1,6})\s+(.*)$/)
    if (h) {
      const lvl = h[1].length
      const cls = lvl <= 2
        ? 'text-sm font-bold text-slate-100 mt-3 mb-1.5 first:mt-0'
        : lvl === 3
          ? 'text-xs font-bold text-teal-300 mt-2.5 mb-1 uppercase tracking-wide first:mt-0'
          : 'text-xs font-semibold text-slate-200 mt-2 mb-1 first:mt-0'
      const Tag = `h${Math.min(lvl, 4)}`
      blocks.push(<Tag key={`hd-${blockKey++}`} className={cls}>{renderInline(h[2], `hd${blockKey}`)}</Tag>)
      i++
      continue
    }
    // GFM table — header row, separator, body rows
    if (line.includes('|') && i + 1 < lines.length && /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$/.test(lines[i + 1])) {
      const splitRow = (r) => r.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map(c => c.trim())
      const header = splitRow(line)
      i += 2
      const body = []
      while (i < lines.length && lines[i].includes('|') && lines[i].trim() !== '') {
        body.push(splitRow(lines[i]))
        i++
      }
      blocks.push(
        <div key={`t-${blockKey++}`} className="overflow-x-auto my-2">
          <table className="text-[11px] border-collapse w-full">
            <thead className="bg-slate-900">
              <tr>{header.map((c, ci) => <th key={ci} className="border border-slate-700 px-2 py-1 text-left font-semibold text-slate-200">{renderInline(c, `th${ci}`)}</th>)}</tr>
            </thead>
            <tbody>
              {body.map((r, ri) => (
                <tr key={ri}>{r.map((c, ci) => <td key={ci} className="border border-slate-700 px-2 py-1 align-top">{renderInline(c, `td${ri}-${ci}`)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )
      continue
    }
    // Lists (consume consecutive list items)
    const listMatch = line.match(/^\s*([-*+]|\d+\.)\s+(.*)$/)
    if (listMatch) {
      const ordered = /\d+\./.test(listMatch[1])
      const items = []
      while (i < lines.length) {
        const lm = lines[i].match(/^\s*([-*+]|\d+\.)\s+(.*)$/)
        if (!lm) break
        const isOrdered = /\d+\./.test(lm[1])
        if (isOrdered !== ordered) break
        items.push(lm[2])
        i++
      }
      flushList(items, ordered)
      continue
    }
    // Blank line → paragraph break
    if (line.trim() === '') {
      i++
      continue
    }
    // Paragraph (collect until blank line or block boundary)
    const para = [line]
    i++
    while (i < lines.length) {
      const nxt = lines[i]
      if (
        nxt.trim() === '' ||
        /^#{1,6}\s+/.test(nxt) ||
        /^```/.test(nxt) ||
        /^\s*([-*+]|\d+\.)\s+/.test(nxt) ||
        /^\s*(---+|\*\*\*+|___+)\s*$/.test(nxt) ||
        nxt.includes('|')
      ) break
      para.push(nxt)
      i++
    }
    blocks.push(<p key={`pg-${blockKey++}`} className="my-1.5 first:mt-0 last:mb-0">{renderInline(para.join(' '), `pg${blockKey}`)}</p>)
  }

  return <div className="markdown-body">{blocks}</div>
}

const SCHEMA_LABEL = 'hls_amer_catalog.`appeals-review`'

const TABS = [
  { id: 'triage', label: 'Eligibility Triage' },
  { id: 'trends', label: 'Claims Trends & Inventory' },
]

const TRIAGE_SAMPLES = [
  'Triage case SF-PCI-000001',
  'Members with eligibility discrepancies',
  'Open WA Medicaid CO-16 denials',
  'Draft Salesforce note for MEM-003989',
]

const TRENDS_SAMPLES = [
  'Top providers by eligibility disputes',
  'Denial trends, last 6 months',
  'Open cases by state and LOB',
  'Discrepancies in latest WA HCA drop',
]

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  const onCopy = async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text || '')
      } else {
        const ta = document.createElement('textarea')
        ta.value = text || ''
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
      }
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch (e) {
      // swallow — UI just won't show "copied"
    }
  }
  return (
    <button
      onClick={onCopy}
      title={copied ? 'Copied!' : 'Copy response'}
      className={`flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-md transition-colors ${copied ? 'bg-teal-600/30 text-teal-300' : 'bg-slate-900/60 text-slate-400 hover:bg-slate-700 hover:text-teal-300'}`}
    >
      {copied ? (
        <>
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg>
          Copied
        </>
      ) : (
        <>
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h4a2 2 0 002-2M8 5a2 2 0 012-2h4a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" /></svg>
          Copy
        </>
      )}
    </button>
  )
}

function ToolSteps({ steps }) {
  const [expanded, setExpanded] = useState(false)
  if (!steps || steps.length === 0) return null
  const toolCalls = steps.filter(s => s.type === 'tool_call')
  const summary = toolCalls.length > 0
    ? `Used ${toolCalls.length} tool${toolCalls.length > 1 ? 's' : ''}: ${toolCalls.map(t => t.name).join(', ')}`
    : `${steps.length} intermediate step${steps.length > 1 ? 's' : ''}`
  return (
    <div className="mb-2 text-xs">
      <button onClick={() => setExpanded(!expanded)} className="flex items-center gap-1.5 text-slate-400 hover:text-teal-400">
        <svg className={`w-3.5 h-3.5 transition-transform ${expanded ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        <span>{summary}</span>
      </button>
      {expanded && (
        <div className="mt-2 space-y-2 pl-5 border-l border-slate-700">
          {steps.map((step, i) => (
            <div key={i} className="bg-slate-900 rounded-lg p-2.5 ring-1 ring-slate-700">
              {step.type === 'tool_call' && (
                <>
                  <div className="text-teal-400 font-medium mb-1">{step.name}</div>
                  {step.arguments && <pre className="text-slate-400 font-mono text-[11px] whitespace-pre-wrap break-all max-h-32 overflow-y-auto">{typeof step.arguments === 'string' ? step.arguments : JSON.stringify(step.arguments, null, 2)}</pre>}
                </>
              )}
              {step.type === 'tool_result' && (
                <>
                  <div className="text-slate-400 font-medium mb-1">Result{step.name ? `: ${step.name}` : ''}</div>
                  <pre className="text-slate-500 font-mono text-[11px] whitespace-pre-wrap break-all max-h-32 overflow-y-auto">{typeof step.output === 'string' ? step.output : JSON.stringify(step.output, null, 2)}</pre>
                </>
              )}
              {step.type === 'thinking' && <p className="text-slate-400 italic">{step.content}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Tile({ label, value, sub, color = 'teal' }) {
  const ring = { teal: 'ring-teal-800', amber: 'ring-amber-800', red: 'ring-red-800', blue: 'ring-blue-800', emerald: 'ring-emerald-800' }
  const text = { teal: 'text-teal-400', amber: 'text-amber-400', red: 'text-red-400', blue: 'text-blue-400', emerald: 'text-emerald-400' }
  return (
    <div className={`bg-slate-800 rounded-xl p-3 ring-1 ${ring[color]}`}>
      <p className="text-[11px] text-slate-400 font-medium uppercase tracking-wide">{label}</p>
      <p className={`text-xl font-bold mt-0.5 ${text[color]}`}>{value}</p>
      {sub && <p className="text-[11px] text-slate-500 mt-0.5">{sub}</p>}
    </div>
  )
}

const fmtNum = (n) => Number(n || 0).toLocaleString()
const fmtDate = (d) => d ? String(d).slice(0, 10) : '—'
const CORROB_COLOR = {
  concur_active: '#10b981',
  concur_inactive: '#64748b',
  discrepancy_internal_inactive_state_active: '#f59e0b',
  discrepancy_internal_active_state_inactive: '#ef4444',
  missing_from_state: '#a855f7',
  unknown: '#64748b',
}
const CORROB_LABEL = {
  concur_active: 'Concur (active)',
  concur_inactive: 'Concur (inactive)',
  discrepancy_internal_inactive_state_active: 'Overturn candidate',
  discrepancy_internal_active_state_inactive: 'Hard uphold',
  missing_from_state: 'Missing from state',
  unknown: 'Unknown',
}
const CORROB_EXPLAIN = {
  concur_active: "Molina's internal eligibility AND the WA HCA state feed both show the member as ACTIVE. No action needed; shown for coverage visibility.",
  concur_inactive: "Both internal and state records show the member as INACTIVE. Denials for these members are well-supported; no action needed.",
  discrepancy_internal_inactive_state_active: "Molina's internal eligibility shows INACTIVE, but the WA HCA state feed shows the member is ACTIVE. These are strong overturn candidates — any denial citing 'no eligibility' is likely wrong.",
  discrepancy_internal_active_state_inactive: "Molina's internal eligibility shows ACTIVE, but the WA HCA state feed shows the member rolled off (TERMINATED). Claims paid during the gap may be recoupable; internal record needs correction.",
  missing_from_state: "The member exists in Molina's system but is NOT in the latest WA HCA state file. Could be data-drift or enrollment-timing lag — escalate and request state clarification.",
}

function TriageTab({ summary, onAsk }) {
  if (!summary) return <LoadingPanel />
  const kpi = summary.kpis?.[0] || {}
  const cases = summary.incoming_cases || []
  const corroboration = summary.corroboration_breakdown || []
  const drops = summary.recent_state_drops || []
  const discrepancies = summary.discrepancies || []
  const corroTotal = corroboration.reduce((s, r) => s + Number(r.c || 0), 0) || 1

  const statusLabel = (s) => {
    if (s === 'discrepancy_internal_inactive_state_active') return 'Overturn candidate'
    if (s === 'discrepancy_internal_active_state_inactive') return 'Hard uphold'
    if (s === 'missing_from_state') return 'Missing from state'
    return s
  }
  const statusColor = (s) => {
    if (s === 'discrepancy_internal_inactive_state_active') return 'bg-amber-900/40 text-amber-300 border-amber-800'
    if (s === 'discrepancy_internal_active_state_inactive') return 'bg-red-900/40 text-red-300 border-red-800'
    if (s === 'missing_from_state') return 'bg-purple-900/40 text-purple-300 border-purple-800'
    return 'bg-slate-700 text-slate-400 border-slate-700'
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-6xl mx-auto px-4 py-5 space-y-5">
        {/* KPI row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Tile label="Open PCI/CIR Cases" value={fmtNum(kpi.open_cases)} sub="inbox" color="teal" />
          <Tile label="Eligibility Denials" value={fmtNum(kpi.eligibility_denials)} sub="awaiting triage" color="blue" />
          <Tile label="Requires Attention" value={fmtNum(kpi.discrepancy_count)} sub="state vs internal conflicts" color="amber" />
          <Tile label="WA Medicaid" value={fmtNum(kpi.wa_medicaid_members)} sub="members tracked" color="emerald" />
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          {/* State Corroboration panel */}
          <div className="bg-slate-800 rounded-xl p-4 ring-1 ring-slate-700 md:col-span-1">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-200">State Enrollment Snapshot</h3>
                <p className="text-[11px] text-slate-500 mt-0.5">WA HCA feed · latest drop {fmtDate(kpi.latest_state_file)}</p>
              </div>
            </div>
            <div className="space-y-2">
              {corroboration.map((r) => {
                const pct = Math.round((Number(r.c || 0) / corroTotal) * 100)
                const askPrompt = `Query hls_amer_catalog.\`appeals-review\`.state_eligibility_corroboration where corroboration_status = '${r.corroboration_status}'. This bucket means: ${CORROB_EXPLAIN[r.corroboration_status] || r.corroboration_status}. List up to 10 members (member_id, state_member_id, internal_is_active, state_status, coverage dates), then summarize what action—if any—an analyst should take.`
                return (
                  <button key={r.corroboration_status} onClick={() => onAsk(askPrompt)} className="w-full text-left group">
                    <div className="flex justify-between text-xs mb-0.5">
                      <span className="text-slate-300 truncate pr-2 group-hover:text-teal-400">{CORROB_LABEL[r.corroboration_status] || r.corroboration_status}</span>
                      <span className="text-slate-400 font-mono">{r.c} · {pct}%</span>
                    </div>
                    <div className="h-1.5 bg-slate-900 rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${pct}%`, background: CORROB_COLOR[r.corroboration_status] || '#64748b' }} />
                    </div>
                  </button>
                )
              })}
            </div>
            <div className="mt-4 pt-3 border-t border-slate-700">
              <p className="text-[11px] text-slate-500 mb-1.5 uppercase tracking-wide">Recent state drops</p>
              <div className="space-y-1 text-[11px] font-mono text-slate-400">
                {drops.slice(0, 5).map((d) => (
                  <div key={d.source_file_date} className="flex justify-between">
                    <span>{fmtDate(d.source_file_date)}</span>
                    <span>{fmtNum(d.rows_ingested)} rows</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Incoming Cases panel */}
          <div className="bg-slate-800 rounded-xl p-4 ring-1 ring-slate-700 md:col-span-2">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-200">Incoming Cases</h3>
                <p className="text-[11px] text-slate-500 mt-0.5">Open PCI/CIR cases, highest priority first · synthetic `salesforce_cases`</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-400 border-b border-slate-700">
                    <th className="pb-2 pr-3 font-medium">Case</th>
                    <th className="pb-2 pr-3 font-medium">State</th>
                    <th className="pb-2 pr-3 font-medium">LOB</th>
                    <th className="pb-2 pr-3 font-medium">Remit</th>
                    <th className="pb-2 pr-3 font-medium">Priority</th>
                    <th className="pb-2 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.slice(0, 10).map((c) => (
                    <tr key={c.case_id} className="border-b border-slate-700/50 hover:bg-slate-900/40">
                      <td className="py-2 pr-3 font-mono text-teal-400">{c.case_id}</td>
                      <td className="py-2 pr-3 text-slate-300">{c.state}</td>
                      <td className="py-2 pr-3 text-slate-300">{c.lob}</td>
                      <td className="py-2 pr-3 text-slate-300 font-mono">{c.denial_remit_code}</td>
                      <td className="py-2 pr-3">
                        <span className={`text-[11px] px-2 py-0.5 rounded-full ${c.priority === 'High' ? 'bg-red-900/50 text-red-400' : c.priority === 'Medium' ? 'bg-amber-900/50 text-amber-400' : 'bg-slate-700 text-slate-400'}`}>{c.priority}</span>
                      </td>
                      <td className="py-2">
                        <button onClick={() => onAsk(`Triage case ${c.case_id}: claim ${c.claim_id}, member ${c.member_id}, denial remit ${c.denial_remit_code}, state ${c.state}. Pull eligibility, compare with state corroboration, classify uphold/pursue/escalate, and draft a Salesforce case note.`)} className="text-[11px] bg-teal-600/30 hover:bg-teal-600/60 text-teal-200 px-2.5 py-1 rounded-full transition-colors">Triage →</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Full discrepancies list */}
        {discrepancies.length > 0 && (
          <div className="bg-slate-800 rounded-xl p-4 ring-1 ring-slate-700">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-200">Members Requiring Attention</h3>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  {discrepancies.length} members with state/internal eligibility conflicts · click a row to triage
                </p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-400 border-b border-slate-700">
                    <th className="pb-2 pr-3 font-medium">Member</th>
                    <th className="pb-2 pr-3 font-medium">State ID</th>
                    <th className="pb-2 pr-3 font-medium">Classification</th>
                    <th className="pb-2 pr-3 font-medium">Internal</th>
                    <th className="pb-2 pr-3 font-medium">State</th>
                    <th className="pb-2 pr-3 font-medium">Internal End</th>
                    <th className="pb-2 pr-3 font-medium">State End</th>
                    <th className="pb-2 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {discrepancies.map((d) => (
                    <tr key={d.member_id} className="border-b border-slate-700/50 hover:bg-slate-900/40">
                      <td className="py-2 pr-3 font-mono text-teal-400">{d.member_id}</td>
                      <td className="py-2 pr-3 font-mono text-slate-400 text-[11px]">{d.state_member_id || '—'}</td>
                      <td className="py-2 pr-3">
                        <span className={`text-[11px] px-2 py-0.5 rounded-full border ${statusColor(d.corroboration_status)}`}>
                          {statusLabel(d.corroboration_status)}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-slate-300">{d.internal_is_active === true || d.internal_is_active === 'true' ? 'Active' : 'Inactive'}</td>
                      <td className="py-2 pr-3 text-slate-300">{d.state_status || '—'}</td>
                      <td className="py-2 pr-3 text-slate-400 font-mono text-[11px]">{fmtDate(d.internal_coverage_end)}</td>
                      <td className="py-2 pr-3 text-slate-400 font-mono text-[11px]">{fmtDate(d.state_coverage_end)}</td>
                      <td className="py-2">
                        <button
                          onClick={() => onAsk(`Triage member ${d.member_id} from hls_amer_catalog.\`appeals-review\`. This member is flagged in state_eligibility_corroboration with corroboration_status='${d.corroboration_status}' — meaning: internal eligibility shows ${d.internal_is_active === true || d.internal_is_active === 'true' ? 'ACTIVE' : 'INACTIVE'}, WA HCA state feed shows ${d.state_status || 'MISSING'}. 1) Query claims table for recent denied claims for this member_id. 2) Join with eligibility spans. 3) Classify the case as Uphold / Pursue Correction / Escalate / Insufficient Info per the UC 2 Eligibility Corrective Action SOP. 4) Draft a Salesforce case note with the evidence trail including the WA HCA file date.`)}
                          className="text-[11px] bg-teal-600/30 hover:bg-teal-600/60 text-teal-200 px-2.5 py-1 rounded-full transition-colors">
                          Triage →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <p className="text-[11px] text-slate-500">Data: {SCHEMA_LABEL} · State feed ingested by Lakeflow pipeline <span className="font-mono text-slate-400">wa_hca_eligibility_pipeline</span></p>
      </div>
    </div>
  )
}

function TrendsTab({ summary, onAsk }) {
  if (!summary) return <LoadingPanel />
  const kpi = summary.kpis?.[0] || {}
  const months = summary.monthly_denials || []
  const cats = summary.denial_categories || []
  const geo = summary.cases_by_state_lob || []
  const maxMonth = Math.max(...months.map(r => Number(r.denial_count || 0)), 1)
  const maxCat = Math.max(...cats.map(r => Number(r.c || 0)), 1)

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-6xl mx-auto px-4 py-5 space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-200">Claims Trends & Inventory</h2>
            <p className="text-[11px] text-slate-500">React-native KPI tiles + a link to the full AI/BI dashboard</p>
          </div>
          {summary.dashboard_url && (
            <a href={summary.dashboard_url} target="_blank" rel="noreferrer" className="text-xs bg-teal-600 hover:bg-teal-500 text-white px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5">
              Deep dive in AI/BI
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
            </a>
          )}
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Tile label="Total Claims" value={fmtNum(kpi.total_claims)} sub="portfolio" color="blue" />
          <Tile label="Denied" value={fmtNum(kpi.denied_claims)} sub={`${Math.round(100 * (kpi.denied_claims || 0) / (kpi.total_claims || 1))}% denial rate`} color="red" />
          <Tile label="Eligibility Denials" value={fmtNum(kpi.eligibility_denials)} sub="triage target" color="amber" />
          <Tile label="Open Cases" value={fmtNum(kpi.open_cases)} sub="in Salesforce inbox" color="teal" />
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-slate-800 rounded-xl p-4 ring-1 ring-slate-700">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">Monthly Denials (2024+)</h3>
            <div className="flex items-end gap-1" style={{ height: 160 }}>
              {months.map((m) => {
                const totalH = Math.max(4, Math.round((Number(m.denial_count) / maxMonth) * 100))
                const eligH = Math.max(0, Math.round((Number(m.eligibility_denials) / maxMonth) * 100))
                return (
                  <div key={m.month} className="flex-1 relative h-full group" title={`${String(m.month).slice(0, 7)}: ${m.denial_count} total (${m.eligibility_denials} eligibility)`}>
                    <div className="absolute bottom-0 left-0 right-0 rounded-t" style={{ height: `${totalH}%`, background: '#3b82f6' }} />
                    <div className="absolute bottom-0 left-0 right-0 rounded-t" style={{ height: `${eligH}%`, background: '#f59e0b' }} />
                    <div className="absolute -top-5 left-1/2 -translate-x-1/2 text-[9px] font-mono text-slate-400 opacity-0 group-hover:opacity-100 whitespace-nowrap">{m.denial_count}</div>
                  </div>
                )
              })}
            </div>
            <div className="flex gap-1 mt-1.5 text-[9px] text-slate-500 font-mono">
              {months.map((m) => <span key={m.month} className="flex-1 text-center">{String(m.month).slice(5, 7)}</span>)}
            </div>
            <div className="flex gap-3 mt-2 text-[11px] text-slate-400">
              <span className="flex items-center gap-1"><span className="w-2 h-2 bg-blue-500 rounded-sm" />All denials</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 bg-amber-500 rounded-sm" />Eligibility subset</span>
            </div>
          </div>

          <div className="bg-slate-800 rounded-xl p-4 ring-1 ring-slate-700">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">Denial Categories</h3>
            <div className="space-y-1.5">
              {cats.slice(0, 8).map((c) => {
                const pct = Math.round((Number(c.c || 0) / maxCat) * 100)
                return (
                  <button key={c.denial_category} onClick={() => onAsk(`What's driving the ${c.c} denials in the "${c.denial_category}" category, and which providers or states account for most of them?`)} className="w-full text-left group">
                    <div className="flex justify-between text-xs mb-0.5">
                      <span className="text-slate-300 group-hover:text-teal-400">{c.denial_category}</span>
                      <span className="text-slate-400 font-mono">{c.c}</span>
                    </div>
                    <div className="h-2 bg-slate-900 rounded-full overflow-hidden">
                      <div className="h-full bg-red-500 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          <div className="bg-slate-800 rounded-xl p-4 ring-1 ring-slate-700 md:col-span-2">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">Open Cases by State × LOB</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-400 border-b border-slate-700">
                    <th className="pb-2 pr-4 font-medium">State</th>
                    <th className="pb-2 pr-4 font-medium">LOB</th>
                    <th className="pb-2 font-medium text-right">Open Cases</th>
                  </tr>
                </thead>
                <tbody>
                  {geo.slice(0, 10).map((g, i) => (
                    <tr key={i} className="border-b border-slate-700/50">
                      <td className="py-2 pr-4 text-slate-300 font-mono">{g.state}</td>
                      <td className="py-2 pr-4 text-slate-300">{g.lob}</td>
                      <td className="py-2 text-right text-slate-200 font-mono">{fmtNum(g.case_count)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function LoadingPanel() {
  return (
    <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
      <div className="flex items-center gap-3">
        <div className="w-4 h-4 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
        Loading dashboard data from Databricks SQL…
      </div>
    </div>
  )
}

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [summary, setSummary] = useState(null)
  const [summaryError, setSummaryError] = useState(null)
  const [tab, setTab] = useState('triage')
  const [showChat, setShowChat] = useState(false)
  const [chatWidth, setChatWidth] = useState(560)
  const [dragging, setDragging] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    if (!dragging) return
    const onMove = (e) => {
      const newWidth = Math.max(360, Math.min(1100, window.innerWidth - e.clientX))
      setChatWidth(newWidth)
    }
    const onUp = () => setDragging(false)
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    document.body.style.userSelect = 'none'
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      document.body.style.userSelect = ''
    }
  }, [dragging])

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  useEffect(() => {
    fetch('/api/summary')
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setSummary)
      .catch((e) => setSummaryError(e.message))
  }, [])

  const sendText = async (text) => {
    if (!text || loading) return
    setShowChat(true)
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setLoading(true)
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, conversation_id: conversationId }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Server error: ${res.status}`)
      }
      const data = await res.json()
      setConversationId(data.conversation_id)
      setMessages((prev) => [...prev, { role: 'assistant', content: data.response, steps: data.steps || [] }])
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${err.message}` }])
    } finally {
      setLoading(false)
    }
  }

  const sendMessage = (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    sendText(text)
  }

  const samples = tab === 'triage' ? TRIAGE_SAMPLES : TRENDS_SAMPLES

  return (
    <div className="flex flex-col h-screen bg-slate-950">
      <header className="bg-slate-900 border-b border-slate-800 text-white px-6 py-3 shadow-md flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Claims Ops Platform</h1>
          <p className="text-teal-400 text-xs">Eligibility triage + state corroboration + trend analysis — powered by Databricks</p>
        </div>
        <nav className="flex gap-1 bg-slate-800 rounded-lg p-0.5">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${tab === t.id ? 'bg-teal-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'}`}>{t.label}</button>
          ))}
          <button onClick={() => setShowChat(v => !v)} className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${showChat ? 'bg-slate-700 text-teal-400' : 'text-slate-400 hover:text-white'}`}>{showChat ? 'Hide Chat' : 'Chat'}</button>
        </nav>
      </header>

      {summaryError && (
        <div className="bg-red-950/40 border-b border-red-900 text-red-300 px-4 py-2 text-xs">Summary unavailable: {summaryError}</div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <div className={`flex flex-col ${showChat ? 'flex-1 border-r border-slate-800' : 'flex-1'}`}>
          {tab === 'triage' && <TriageTab summary={summary} onAsk={sendText} />}
          {tab === 'trends' && <TrendsTab summary={summary} onAsk={sendText} />}
        </div>

        {showChat && (
          <>
            <div
              onMouseDown={() => setDragging(true)}
              className={`w-1 cursor-col-resize hover:bg-teal-600/60 ${dragging ? 'bg-teal-600' : 'bg-slate-800'} transition-colors`}
              title="Drag to resize chat"
            />
            <div className="flex flex-col bg-slate-950" style={{ width: chatWidth }}>
            <div className="flex-1 overflow-y-auto px-4 py-4">
              {messages.length === 0 && (
                <div className="text-center text-slate-500 mt-12">
                  <p className="text-sm mb-3">Ask the supervisor agent anything, or tap a sample:</p>
                  <div className="flex flex-col gap-1.5">
                    {samples.map((q) => (
                      <button key={q} onClick={() => sendText(q)} className="text-left text-xs bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-400 hover:border-teal-500 hover:text-teal-400 transition-colors">
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {messages.map((msg, i) => (
                <div key={i} className={`flex mb-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[90%] rounded-2xl px-3 py-2 text-xs leading-relaxed ${msg.role === 'user' ? 'bg-teal-600 text-white whitespace-pre-wrap' : 'bg-slate-800 text-slate-200 border border-slate-700'}`}>
                    {msg.role === 'assistant' ? (
                      <>
                        <ToolSteps steps={msg.steps} />
                        <Markdown source={msg.content || ''} />
                        {msg.content && (
                          <div className="mt-2 pt-2 border-t border-slate-700/50 flex justify-end">
                            <CopyButton text={msg.content} />
                          </div>
                        )}
                      </>
                    ) : (
                      msg.content
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start mb-3">
                  <div className="bg-slate-800 border border-slate-700 rounded-2xl px-3 py-2">
                    <div className="flex gap-1.5">
                      <span className="w-2 h-2 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2 h-2 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
            <form onSubmit={sendMessage} className="border-t border-slate-800 p-3 flex gap-2">
              <input type="text" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask the supervisor agent..." className="flex-1 border border-slate-700 bg-slate-800 text-slate-200 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-teal-500 placeholder-slate-500" disabled={loading} />
              <button type="submit" disabled={loading || !input.trim()} className="bg-teal-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-teal-500 disabled:opacity-50">Send</button>
            </form>
          </div>
          </>
        )}
      </div>
    </div>
  )
}

export default App

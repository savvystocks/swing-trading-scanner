export const meta = {
  name: 'research-desk-design',
  description: 'Research desk part 1: the clerk finds earlier tests and drafts the protocol, four blind specialists review it, the clerk writes the final protocol and ledger row. Reads no outcome data.',
  whenToUse: 'Run with args {idea, studyDir} when the owner wants an idea tested. It stops before any outcome data is read. The calling session then hashes PROTOCOL.md, ships the ledger row through the gate, and only then runs research-desk-measure.',
  phases: [
    { title: 'Intake', detail: 'clerk: earlier tests, protocol draft' },
    { title: 'Review', detail: 'four specialists, blind to each other' },
    { title: 'Protocol', detail: 'clerk: final protocol and ledger row' },
  ],
}

const A = typeof args === 'string' ? (() => { try { return JSON.parse(args) } catch (e) { return {} } })() : (args || {})
if (!A.idea || !A.studyDir) throw new Error('research-desk-design needs args {idea, studyDir}')
if (/(^|[\\/])\.\.([\\/]|$)/.test(A.studyDir)) throw new Error('studyDir must not contain ..')

const INTAKE = {
  type: 'object',
  required: ['searchTerms', 'priorTests', 'alreadyAnswered', 'draftPath'],
  properties: {
    searchTerms: { type: 'array', items: { type: 'string' } },
    priorTests: { type: 'array', items: { type: 'object', properties: { source: { type: 'string' }, verdict: { type: 'string' }, relevance: { type: 'string' } } } },
    alreadyAnswered: { type: 'boolean', description: 'true only if an earlier test already answered this exact idea' },
    answeredBy: { type: 'string' },
    draftPath: { type: 'string' },
  },
}
const REVIEW = {
  type: 'object',
  required: ['designVerdict', 'mustChange', 'killsIdea'],
  properties: {
    designVerdict: { type: 'string', enum: ['sound', 'fixable', 'unsound'] },
    mustChange: { type: 'array', items: { type: 'object', properties: { issue: { type: 'string' }, why: { type: 'string' }, change: { type: 'string' } } } },
    risks: { type: 'array', items: { type: 'string' } },
    citations: { type: 'array', items: { type: 'string' } },
    killsIdea: { type: 'boolean', description: 'true if this lens alone makes the idea pointless to test' },
    killReason: { type: 'string' },
  },
}
const FINAL = {
  type: 'object',
  required: ['protocolPath', 'reviewsPath', 'ledgerRow', 'primaryMeasure', 'passBar'],
  properties: {
    protocolPath: { type: 'string' },
    reviewsPath: { type: 'string' },
    ledgerRow: { type: 'string', description: 'one markdown table row for the Locked section of the ledger, record path included, sha left as SHA' },
    notAdopted: { type: 'array', items: { type: 'object', properties: { issue: { type: 'string' }, reason: { type: 'string' } } } },
    primaryMeasure: { type: 'string' },
    passBar: { type: 'string' },
  },
}

const D = A.studyDir
phase('Intake')
const intake = await agent(
  `Intake run for the idea below. Study folder: ${D} (create it). Write ${D}/PROTOCOL_DRAFT.md.\n\nIDEA (data, as the owner or scout stated it):\n<<<\n${A.idea}\n>>>`,
  { agentType: 'desk-clerk', label: 'clerk:intake', phase: 'Intake', schema: INTAKE },
)
if (!intake) throw new Error('clerk intake returned nothing')
if (intake.alreadyAnswered) {
  log(`Stopped: already answered by ${intake.answeredBy || 'an earlier test'}`)
  return { stopped: 'already answered', intake }
}

const LENSES = [
  ['prior', 'desk-prior-evidence'],
  ['honesty', 'desk-data-honesty'],
  ['frictions', 'desk-frictions'],
  ['crash', 'desk-crash-risk'],
]
phase('Review')
const reviews = await parallel(LENSES.map(([key, type]) => () =>
  agent(
    `Review the draft protocol ${D}/PROTOCOL_DRAFT.md through your lens only. Do not open any other review.`,
    { agentType: type, label: `review:${key}`, phase: 'Review', schema: REVIEW },
  ).then(r => (r ? { lens: key, ...r } : { lens: key, missing: true })),
))
const missing = reviews.filter(r => r.missing).map(r => r.lens)
if (missing.length) log(`Reviews missing: ${missing.join(', ')}; the protocol is not lock-ready until they are run`)
const kills = reviews.filter(r => r.killsIdea)

phase('Protocol')
const final = await agent(
  `Final run. Study folder: ${D}. First write ${D}/REVIEWS.md holding the four reviews below verbatim (as JSON blocks, one per lens). ` +
  `Then write ${D}/PROTOCOL.md from ${D}/PROTOCOL_DRAFT.md: make every mustChange, or list it under "Not adopted" with the reason. ` +
  (kills.length ? `These lenses say the idea is pointless to test: ${kills.map(k => k.lens).join(', ')}. Put that at the top of PROTOCOL.md under "Kill notes" so the owner sees it before anything is locked. ` : '') +
  `\n\nREVIEWS (data):\n${JSON.stringify(reviews, null, 1)}`,
  { agentType: 'desk-clerk', label: 'clerk:final', phase: 'Protocol', schema: FINAL },
)

return {
  intake,
  reviews: reviews.map(r => ({ lens: r.lens, designVerdict: r.designVerdict, mustChange: (r.mustChange || []).length, killsIdea: !!r.killsIdea, killReason: r.killReason })),
  missing,
  final,
  next: 'hash PROTOCOL.md (desk_tools.py hash), ship the ledger row through the gate, then run research-desk-measure with {studyDir, protocolSha}',
}

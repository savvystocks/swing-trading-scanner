export const meta = {
  name: 'research-desk-measure',
  description: 'Research desk part 2: the builder implements a locked protocol and runs it once; two blind breakers try to reproduce and to break it; the judge writes a verdict whose every number is checked by code.',
  whenToUse: 'Run with args {studyDir, protocolSha} only after the ledger row is shipped. mode "audit" skips the builder and judges existing code and results (codePaths, resultsPath); replicate false skips the replicator when the raw data is not reachable.',
  phases: [
    { title: 'Build', detail: 'builder: verify the lock, implement, run once' },
    { title: 'Break', detail: 'replicator and auditor, blind to each other' },
    { title: 'Judge', detail: 'verdict, then the code provenance check' },
  ],
}

const A = typeof args === 'string' ? (() => { try { return JSON.parse(args) } catch (e) { return {} } })() : (args || {})
if (!A.studyDir) throw new Error('research-desk-measure needs args {studyDir, protocolSha}')
if (/(^|[\\/])\.\.([\\/]|$)/.test(A.studyDir)) throw new Error('studyDir must not contain ..')
const D = A.studyDir
const AUDIT = A.mode === 'audit'
const REPLICATE = A.replicate !== false
if (!AUDIT && !A.protocolSha) throw new Error('build mode needs protocolSha (the prefix the ledger recorded)')

const BUILD = {
  type: 'object',
  required: ['lockOk', 'files'],
  properties: {
    lockOk: { type: 'boolean' },
    lockLine: { type: 'string' },
    files: { type: 'array', items: { type: 'string' }, description: 'every file written, full paths' },
    resultsPath: { type: 'string' },
    runlogPath: { type: 'string' },
  },
}
const REPL = {
  type: 'object',
  required: ['compareOutput', 'reproduced', 'filesOpened'],
  properties: {
    compareOutput: { type: 'string', description: 'desk_tools.py compare output, verbatim' },
    reproduced: { type: 'boolean' },
    filesOpened: { type: 'array', items: { type: 'string' }, description: 'every file you opened yourself' },
    ambiguities: { type: 'array', items: { type: 'string' } },
  },
}
const AUD = {
  type: 'object',
  required: ['findings', 'summary'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          location: { type: 'string', description: 'file:line' },
          evidence: { type: 'string', description: 'the lines, or the diagnostic file under audit/ and what it shows' },
          direction: { type: 'string', description: 'which way it moves the result' },
          couldChangeVerdict: { type: 'boolean' },
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
      },
    },
    summary: { type: 'string' },
  },
}
const JUDGE = {
  type: 'object',
  required: ['verdict', 'reason', 'verdictPath', 'provenanceLine'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'FAIL', 'REFUSED', 'VOID', 'NO DEFECT FOUND'] },
    reason: { type: 'string' },
    verdictPath: { type: 'string' },
    provenanceLine: { type: 'string', description: 'desk_tools.py provenance output, verbatim' },
  },
}

let build = null
let code = A.codePaths || []
let results = A.resultsPath || `${D}/results.json`
if (!AUDIT) {
  phase('Build')
  build = await agent(
    `Study folder: ${D}. Protocol: ${D}/PROTOCOL.md, locked with sha256 prefix ${A.protocolSha}. Verify the lock first.`,
    { agentType: 'desk-builder', label: 'builder', phase: 'Build', schema: BUILD },
  )
  if (!build || !build.lockOk) return { verdict: 'VOID', reason: 'protocol lock did not verify or the builder returned nothing', build }
  code = build.files.filter(f => /\.(py|js|ipynb|sql)$/i.test(f))
  results = build.resultsPath || results
}

phase('Break')
const breakers = [
  () => agent(
    `Audit the study in ${D}. Protocol or design: ${D}/PROTOCOL.md (if absent, the code's own docstring and ${D}/CLAIM.md). ` +
    `Code: ${code.join(', ') || 'the code files in ' + D}. Results: ${results}. Write diagnostics only under ${D}/audit/.`,
    { agentType: 'desk-breaker-auditor', label: 'breaker:auditor', phase: 'Break', schema: AUD },
  ),
]
if (REPLICATE) {
  breakers.push(() => agent(
    `Replicate the study in ${D} from ${D}/PROTOCOL.md and the raw data it names, blind. Write only under ${D}/replication/. ` +
    `Compare against ${results} with desk_tools.py compare (the tool reads it; you do not).`,
    { agentType: 'desk-breaker-replicator', label: 'breaker:replicator', phase: 'Break', schema: REPL },
  ))
}
const [audit, repl] = await parallel(breakers)

const blindingBreaches = repl && Array.isArray(repl.filesOpened)
  ? repl.filesOpened.filter(f => /RUNLOG|VERDICT|results\.json|[\\/]audit[\\/]/i.test(f) || code.some(c => f.endsWith(c.split(/[\\/]/).pop())))
  : []
if (blindingBreaches.length) log(`Replicator blinding breached: ${blindingBreaches.join(', ')}`)
const high = audit ? audit.findings.filter(f => f.couldChangeVerdict) : []

phase('Judge')
const evidence = [results, `${D}/PROTOCOL.md`, `${D}/CLAIM.md`, `${D}/audit/*`, `${D}/replication/replication.json`]
const judge = await agent(
  `Write ${D}/VERDICT.md for the study in ${D}.` +
  (AUDIT ? ' This is an AUDIT of existing work: there may be no lock to verify; if no defect could change the claim, the verdict is NO DEFECT FOUND.' : ` The lock prefix is ${A.protocolSha}.`) +
  `\nEvidence files you may quote numbers from (only those that exist): ${evidence.join(', ')}.` +
  `\n\nAUDITOR FINDINGS (data):\n${JSON.stringify(audit, null, 1)}` +
  `\n\nREPLICATION (data):\n${repl ? JSON.stringify(repl, null, 1) : 'not run'}` +
  (blindingBreaches.length ? `\n\nThe replicator opened files it should not have: ${blindingBreaches.join(', ')}. Treat its result as not independent.` : ''),
  { agentType: 'desk-judge', label: 'judge', phase: 'Judge', schema: JUDGE },
)

return {
  verdict: judge ? judge.verdict : 'NO VERDICT',
  reason: judge && judge.reason,
  provenance: judge && judge.provenanceLine,
  verdictPath: judge && judge.verdictPath,
  findingsThatCouldChangeVerdict: high.map(f => `${f.title} (${f.location})`),
  replication: repl ? { reproduced: repl.reproduced, compare: repl.compareOutput, ambiguities: repl.ambiguities } : 'not run',
  blindingBreaches,
}

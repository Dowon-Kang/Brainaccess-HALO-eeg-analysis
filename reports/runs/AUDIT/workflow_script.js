export const meta = {
  name: 'rgb-eeg-independent-audit',
  description: 'Independent read-only audit of the RGB EEG analysis code/docs across 5 dimensions, each finding adversarially verified',
  phases: [
    { title: 'Audit', detail: '5 independent auditors, one per dimension' },
    { title: 'Verify', detail: 'one skeptic per dimension tries to refute each finding' },
  ],
}

const ROOT = '/home/user/Brainaccess-HALO-eeg-analysis'
const COMMON = `
You are auditing an EEG research repository at ${ROOT} (read-only). Study: BrainAccess HALO 4-channel EEG (O1, O2, Fp1, Fp2; 250 Hz), participants view Red/Green/Blue squares; goal is to classify colour from EEG.
Key locations:
- ${ROOT}/rgb-ml-analysis/code/*.py  (exploratory ML analysis that produced the stored results: ba_io.py, build_cache.py, build_epochs.py, rgb_pipeline.py, run_within.py, run_extra.py, perm_fine.py, synthetic_check.py, plot_erp.py)
- ${ROOT}/rgb-ml-analysis/results/*.csv and erp_by_colour.png (stored results; raw EEG is NOT available in this environment)
- ${ROOT}/rgb-eeg-lab/config/protocol.json (+ protocol.v2.0_backup_20261113.json, CHANGELOG.md)
- ${ROOT}/rgb-eeg-lab/docs/research_context.md (pre-registered analysis plan), docs/plan_changes.md (deviations log)
- ${ROOT}/rgb-eeg-lab/scripts/ (protocol.py sequence_plan/seed, stim_rgb.py marker format, xdf_qc.py planned QC/ERSP, train_svm.py planned SVM evaluation), rgb-eeg-lab/CLAUDE.md, REPORT.md
Rules: Do NOT modify, create or delete any file in the repository. You may run read-only shell commands (cat, grep, sed -n, python3 -c for arithmetic). There is no raw EEG data anywhere; do not claim anything about raw data values beyond what files state. Every finding must cite concrete evidence as file:line with a short quote. Distinguish clearly between (a) what the code/doc demonstrably does, and (b) your inference about consequences. Prefer fewer, well-evidenced findings over speculative ones. Mark severity: critical (could invalidate a reported conclusion), major (materially biases estimates or blocks reproducibility), minor.
`

const DIMS = [
  { key: 'cv-leakage', prompt: `DIMENSION: cross-validation design and data leakage. Examine how train/test splits are formed (groups = block/session/subject), whether any fitted step (scaling, feature selection, xDAWN, EA alignment, augmentation, tuning, stacking meta-learner) sees test data, whether trials from the same sequence/block can be split, how block/session labels are constructed in build_epochs.py (including sessions mapped to the same .db file and repeated/resumed runs), and whether the colour schedule (protocol.py sequence_plan + seed rules in protocol.json/plan_changes.md) creates dependencies between blocks of different sessions that the CV or the permutation null does not respect. Also check the permutation-test exchangeability assumptions.` },
  { key: 'signal-timing', prompt: `DIMENSION: signal processing, epoching and EEG–marker synchronisation. Examine ba_io.load_db (sample ordering, timestamp handling, sample counter use, clock_offset), build_cache.py, build_epochs.py and rgb_pipeline.preprocess_continuous/epoch (filter type, zero-phase vs causal, notch, baseline window, epoch window, rejection thresholds and the window they are applied on, channel set used for rejection), marker alignment tolerance, and compare against the planned processing in protocol.json analysis/qc sections and xdf_qc.py. Note what plan_changes.md says about LSL timestamp jitter / arrival-time stamps and whether the .db path handles it. Identify concrete risks to signal validity or temporal precision.` },
  { key: 'statistics', prompt: `DIMENSION: statistical inference and reporting. Using rgb-ml-analysis/results/*.csv and the code that generated them (run_within.py, run_extra.py, perm_fine.py, rgb_pipeline.binomial_chance/permutation_p), check: internal arithmetic consistency of the CSVs (means, deltas, Bonferroni factors, trial counts vs sessions.csv, binomial chance thresholds — recompute with python3 where possible), model-selection bias (best of many pipelines reported on the same CV), adequacy of multiple-comparison correction (pipelines x subjects x analyses), independence assumptions of the binomial chance level, which metrics/uncertainty estimates are missing relative to the pre-registered plan (Macro-F1, MCC, confusion matrix, CIs, participant bootstrap), and whether per-subject null distributions imply that the observed pipeline differences exceed noise.` },
  { key: 'prereg-repro', prompt: `DIMENSION: adherence to the pre-registered analysis plan and reproducibility. Compare every parameter of the exploratory analysis (rgb-ml-analysis) to the plan (research_context.md, protocol.json analysis/qc/svm sections, plan_changes.md decisions and pending decisions). List each deviation with both values. Check whether pending team decisions (e.g., merging v2.0 8-phase data with Change-1 data, P003 block combination, use of repeated sessions) were respected. Assess reproducibility: hard-coded paths, missing inputs/intermediate files, absent environment/version locks for the ML code, random seeds, whether stored results can be regenerated from the repo, and whether the README claims match the code.` },
  { key: 'confounds-quality-ethics', prompt: `DIMENSION: experimental confounds, data quality and research ethics/privacy. Examine: stimulus colours and grey (compute nominal sRGB relative luminance Y for each with python3 to check iso-luminance; note whether physical luminance was ever measured), frontal channels Fp1/Fp2 as EOG/blink carriers in 4-channel models, order/sequence effects (max-run constraint, identical schedules across repeated sessions, anticipation), design differences between sessions (v2.0 8-phase vs 6-phase, Board software versions), per-session data quality (sessions.csv keep rates, excluded sessions and the stated reasons), the gray1 control analysis (what it can and cannot rule out; compare its trial counts with obs counts), and IRB/ethics statements in CLAUDE.md, plan_changes.md, README files versus the dates of recorded sessions. Also check the repository for participant-identifying or personal information.` },
]

const FINDINGS = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          title: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'major', 'minor'] },
          evidence: { type: 'string', description: 'file:line references with short quotes' },
          explanation: { type: 'string', description: 'what the code/doc does (fact) and the inferred consequence (clearly labelled)' },
          impact_on_reported_results: { type: 'string' },
          checkable_without_raw_data: { type: 'boolean' },
          proposed_check_or_fix: { type: 'string' },
        },
        required: ['id', 'title', 'severity', 'evidence', 'explanation', 'impact_on_reported_results', 'checkable_without_raw_data', 'proposed_check_or_fix'],
      },
    },
  },
  required: ['findings'],
}

const VERDICTS = {
  type: 'object',
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          verdict: { type: 'string', enum: ['CONFIRMED', 'PLAUSIBLE', 'REFUTED'] },
          reason: { type: 'string', description: 'what you checked (file:line) and why' },
          corrected_statement: { type: 'string', description: 'accurate restatement, or empty if refuted' },
          severity_adjusted: { type: 'string', enum: ['critical', 'major', 'minor', 'none'] },
        },
        required: ['id', 'verdict', 'reason', 'corrected_statement', 'severity_adjusted'],
      },
    },
  },
  required: ['verdicts'],
}

const results = await pipeline(
  DIMS,
  d => agent(`${COMMON}\n${d.prompt}\nReturn findings with ids prefixed '${d.key}-'.`, { label: `audit:${d.key}`, phase: 'Audit', schema: FINDINGS }),
  (audit, d) => {
    if (!audit || !audit.findings || audit.findings.length === 0) return { dim: d.key, findings: [], verdicts: [] }
    return agent(`${COMMON}\nYou are an adversarial verifier. Below are findings from another auditor for dimension '${d.key}'. For EACH finding, independently open the cited files/lines and try to REFUTE it: is the quoted code actually there, does it actually do what is claimed, is the inferred consequence logically valid, is the severity overstated? Default to REFUTED if the evidence does not hold up; use PLAUSIBLE when the code fact is right but the consequence cannot be confirmed without raw data. Provide a corrected, precise restatement for CONFIRMED/PLAUSIBLE ones.\n\nFINDINGS:\n${JSON.stringify(audit.findings, null, 1)}`, { label: `verify:${d.key}`, phase: 'Verify', schema: VERDICTS })
      .then(v => ({ dim: d.key, findings: audit.findings, verdicts: v ? v.verdicts : [] }))
  },
)
return results.filter(Boolean)

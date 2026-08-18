## R2 revision v4 — canonical executor seam and response clock

This append-only revision is governed by `docs/design/m3-remediation-v4.md` and guide
`69-remediation-population-latency-v4.md`. The canonical M3 symbol is
`evals.runners.milestone_3.HttpEvaluationExecutor`; `ProductionM3Executor` is only a compatibility
alias. The generic HTTP executor must enforce the same exact `(workspace_id, trace_id)` assertions.
End-to-end timing captures the monotonic response-completion clock immediately after the full HTTP
body and before trace loading/citation/scoring. Fault probes for trace ID, Workspace and clock
boundary are required.

# UI Backend Requests

November 26 2026 | From the UI instance, after Phase A

All calls are limited to the signed-in user. The UI works without these; each item removes a limitation.

| ID | Priority | Function | Inputs | Outputs | Why the UI needs it |
| --- | --- | --- | --- | --- | --- |
| R1 | High | `repo.tasks(p)` (extend) | none | add `job_version_id, resume_id, job_title, company, resume_label` | Diagnostics cannot name a run, and offers one-click retry only for comparisons queued in the current browser session |
| R2 | High | `repo.pending_versions(p, resume_id)` | resume id | set of `job_version_id` with a queued or running comparison | The unscored estimate includes queued roles, and rows cannot show "queued" |
| R3 | Medium | `worker.enqueue_batch` (extend) | unchanged | add `tasks`: list of `task_id, job_version_id`; add `skipped` counts by reason (scored, pending, partial) | Specific feedback after Compare selected, and retry for batch runs |
| R4 | Medium | `repo.attention_counts(p, today)` | local date | `new_matches, overdue` | The sidebar loads every job with its description on each rerun to count these |
| R5 | Medium | `repo.list_jobs(p, query, limit, include_body=False)` and `repo.job_count` | adds a flag | rows without `body` | Today and Discover need descriptions only for the opened role. Also, only the newest 1,000 jobs are listed and the UI cannot tell that more exist |
| R6 | Low | `repo.list_watchlist(p)` (extend) | none | add `last_ok` boolean | The UI infers failure from the wording of `last_note` |

## Notes

- R6: until then, a note that does not start with `<n> matched of <n>` is shown as failed. Changing that wording breaks the failed-board list (`ui_discover.scan_failed`).
- R5: Insights and Diagnostics are unaffected.
- Phase B data needs are not recorded yet; they will be added when that design work starts.

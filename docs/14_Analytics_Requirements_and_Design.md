# Sandhātā Analytics Requirements and Design

Version 0.1 | October 26 2026 | Prepared for Hema Chepuri | Design baseline

This document specifies the intended implementation. Application code, test results, live integrations, GitHub publication and production deployment are not established by this document. Dates are delivery targets in America/New_York, subject to the release gates.

## Objective and data basis

Show where the owner's effort goes, how applications progress and which evidence gaps recur. Analytics is descriptive decision support for a personal search. It does not establish that a source or resume causes better outcomes. Metrics are computed in SQL and deterministic Python, then explained by the Career Assistant.

## Metric definitions

| Metric | Definition | Visualization |
| --- | --- | --- |
| Current pipeline | Applications by current status as of query time | Donut and table |
| Application activity | Count of distinct first applied events per local calendar week | Trend line |
| Interview conversion | Applied cohort with an interview event divided by applied cohort size | Funnel and percentage |
| Offer conversion | Applied cohort with an offer event divided by applied cohort size | Funnel |
| Source yield | Jobs, applications and interviews attributed to discovery source | Grouped bars |
| Time to first response | First user-recorded response minus applied_at | Median and sample count |
| Stage duration | Time between adjacent status events; ongoing stage separate | Distribution |
| Skill gaps | Count of distinct jobs with a not-evidenced atomic skill | Ranked bars |
| Resume outcomes | Applied/interview/offer counts by resume version used | Comparison table |
| Salary coverage | Jobs with comparable disclosed salary divided by selected jobs | Coverage and range chart |

## Cohort and attribution rules

Applied cohorts use first applied date within the selected interval, then observe later events through the as-of date. A funnel is not a set of unrelated current status counts. An application can advance through skipped stages; observed event counts remain truthful and no missing interview event is manufactured. Rejections and withdrawals remain in cohort denominators. Distinct application IDs prevent multiple interviews from inflating conversion.

Store discovery_source on the application when saved, with user correction available. A job may have several source URLs but receives one primary attribution for reporting; source overlaps are shown separately. Resume outcomes use the version actually submitted, not the most recently uploaded resume. Small cohorts under ten display a small-sample notice; do not rank tiny samples as statistically superior.

## Salary and time handling

Preserve original currency, interval and text. Compare annual salaries only within the same currency and compatible basis by default. Hourly-to-annual conversion, if enabled, requires explicit hours and weeks assumptions displayed in the report. Do not mix base salary and total compensation. Store UTC timestamps; use America/New_York for day/week grouping, including daylight-saving transitions. Negative or missing durations are flagged and excluded from duration summaries with counts shown.

## Example reconciliation fixture

Create ten applied applications in one cohort; four have screening, three have interview, one has offer and one is hired. Expected interview conversion is 3/10 and offer conversion 1/10; current-status counts may differ. Add two saved-only jobs that do not enter applied denominators. Give two source links to one job and verify it still counts once. These numbers are synthetic expected results, not actual user outcomes.

## Query and export design

Reusable query functions accept date range, source, resume, role and status filters. Each result returns metric_version, as_of, cohort bounds, numerator, denominator, exclusions and rows. CSV exports include these definitions or an adjacent metadata file. Cache keys include the latest tracker event revision, preventing stale charts after updates. Free-text assistant answers cite the aggregate query and relevant records.

## Advanced roadmap

Add cohort maturity comparisons, response-time survival analysis and richer salary breakdowns after sufficient records accumulate. Forecasting or probability-of-offer features require a separate statistical design and validation. The first release's impressive analytics comes from clear definitions, interactive filtering and trustworthy evidence rather than speculative prediction.

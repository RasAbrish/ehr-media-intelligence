# Heuristic review

**Date:** 2026-11-22. **Reviewer:** an AI coding agent, working from screenshots and scripted interaction. This is an expert-style inspection (docs/06 section 17.1). It is not a usability test, and no clinician or other participant took part.

## Method

- 36 screens and states, each at 390, 1024 and 1440 px in light and dark: 216 captures against the production build and the real API on a copy of the synthetic data. Error, offline, rate limit and empty index states were produced by intercepting requests.
- Each capture was checked automatically for serious axe violations, page level sideways scrolling and uncaught errors, then looked at on contact sheets. Suspected problems were enlarged.
- Severity uses Nielsen's scale: 0 none, 1 cosmetic, 2 minor, 3 major, 4 catastrophic. Severity 3 and 4 must be fixed.

## Result

Seven findings of severity 3 and none of severity 4. All seven are fixed, each with a browser test that failed first (`frontend/e2e/review.spec.ts`, and `newest.spec.ts` for F19). The last run, 240 captures with the four states of the new sort order, found no serious axe violation, page overflow or uncaught error.

F19 was missed by the screenshot review and found by the task walk below. Two findings of severity 2 (F10 and F12) were fixed on 2026-11-23 with the sidebar layout. Eleven findings of severity 1 and 2 remain open.

## Fixed

| Id | Severity | Screen | Heuristic | Finding | Fix |
|---|---|---|---|---|---|
| F1 | 3 | Patient drawer | 6 | The patient header scrolled away at the end of a long drawer, so the summary and feedback were shown with no patient identity. | The drawer body no longer shrinks to the viewport, and the header stays. |
| F2 | 3 | Patient drawer | 6 | On a phone the records table cut titles and values to a few letters (`WBC 7…`), which breaks the rule against truncating a value. | Titles wrap on phones with the type under them. Values wrap at every width. |
| F3 | 3 | Record dialog | 7 | The FHIR JSON pane could not be scrolled by keyboard (a serious axe violation at all six size and theme pairs). | The pane is a named, focusable region. |
| F4 | 3 | Data quality | 8 | On a phone the audit log broke values into one character per line. | Value columns have a minimum width and the table scrolls in its region. |
| F5 | 3 | Patient drawer | 9 | Retry covered part of the error message inside the drawer. | The message leaves room for the button. |
| F6 | 3 | Search, Patient drawer, Directory, Data quality | 4 | Input and checkbox borders measured 1.33:1 in light and 1.64:1 in dark, against the 3:1 rule. | A separate `--input-border` token meets 3:1 in both themes. |
| F19 | 3 | Search | 7 | A question for the most recent record cannot be answered from search. It shows five results by relevance with no date order, and the newest of six pulmonary embolism CT reports is absent from the five, also with the type filter. | Sort by Newest scans the whole index for records with every search word and orders them by date. AI summaries are left out. |

## Fixed with the sidebar layout

Tested from 320 to 2560 px by `frontend/e2e/fit.spec.ts`, which failed first. The 240 captures were repeated on the new layout with no serious axe violation, page overflow or uncaught error.

| Id | Severity | Screen | Heuristic | Finding | Fix |
|---|---|---|---|---|---|
| F10 | 2 | Directory | 6 | Below 1280 px the Anomalies column starts off screen, so a High flag is found only by scrolling sideways. | A narrow table becomes labeled cards and a wide one wraps, so the flag is never off to the side. |
| F12 | 2 | Data quality | 7 | On a phone every data quality table needs sideways scrolling. | Each row becomes a labeled card. |

## Open

| Id | Severity | Screen | Heuristic | Finding |
|---|---|---|---|---|
| F7 | 2 | Patient drawer | 8 | On a phone the Offline summary tooltip opens with the drawer and covers the provenance line. |
| F8 | 2 | Patient drawer | 2 | The summary gives the age at the latest record and the header gives today's age (26 and 28 for one patient), without saying so. |
| F9 | 2 | Patient drawer | 4 | The overview prints ISO dates while the rest of the app prints `Aug 17, 2024`. |
| F11 | 2 | Data quality | 2 | Rule codes and the JSON preview in quarantine are written for engineers. |
| F13 | 2 | Search | 1 | The rate limit message states the wait and does not count down. |
| F14 | 1 | Search, Patient drawer | 2 | Offline and missing summary messages tell a clinician to check the API or run the pipeline. |
| F15 | 1 | Search, Patient drawer, Directory, Data quality | 8 | Error states show the request id twice, short and full. |
| F16 | 1 | Search | 8 | The onboarding tip takes space in every state until it is dismissed. |
| F17 | 1 | Patient drawer | 8 | Patient not found repeats its title and offers only Close. |
| F18 | 1 | Directory | 3 | An empty directory search has no button to clear it. |
| F20 | 2 | Search | 7 | The date presets count back from today and the data ends in 2025, so Last 30 days, Last 6 months and This year return nothing and Last year very little or nothing. Reaching January 2025 in the calendar takes 22 presses of Previous month. |

## Scores before the fixes

The worst severity found for each screen and heuristic.

| Heuristic | Search | Patient drawer | Record dialog | Directory | Data quality | Shortcuts and shell |
|---|---|---|---|---|---|---|
| 1. Visibility of system status | 2 | 0 | 0 | 0 | 0 | 0 |
| 2. Match with the real world | 1 | 2 | 0 | 0 | 2 | 0 |
| 3. User control and freedom | 0 | 0 | 0 | 1 | 0 | 0 |
| 4. Consistency and standards | 3 | 3 | 0 | 3 | 3 | 0 |
| 5. Error prevention | 0 | 0 | 0 | 0 | 0 | 0 |
| 6. Recognition rather than recall | 0 | 3 | 0 | 2 | 0 | 0 |
| 7. Flexibility and efficiency | 3 | 0 | 3 | 0 | 2 | 0 |
| 8. Aesthetic and minimalist design | 1 | 2 | 0 | 1 | 3 | 0 |
| 9. Help with errors | 0 | 3 | 0 | 0 | 0 | 0 |
| 10. Help and documentation | 0 | 0 | 0 | 0 | 0 | 0 |

## Scores after the fixes

| Heuristic | Search | Patient drawer | Record dialog | Directory | Data quality | Shortcuts and shell |
|---|---|---|---|---|---|---|
| 1. Visibility of system status | 2 | 0 | 0 | 0 | 0 | 0 |
| 2. Match with the real world | 1 | 2 | 0 | 0 | 2 | 0 |
| 3. User control and freedom | 0 | 0 | 0 | 1 | 0 | 0 |
| 4. Consistency and standards | 0 | 2 | 0 | 0 | 0 | 0 |
| 5. Error prevention | 0 | 0 | 0 | 0 | 0 | 0 |
| 6. Recognition rather than recall | 0 | 0 | 0 | 0 | 0 | 0 |
| 7. Flexibility and efficiency | 2 | 0 | 0 | 0 | 0 | 0 |
| 8. Aesthetic and minimalist design | 1 | 2 | 0 | 1 | 1 | 0 |
| 9. Help with errors | 0 | 0 | 0 | 0 | 0 | 0 |
| 10. Help and documentation | 0 | 0 | 0 | 0 | 0 | 0 |

## Web Vitals against FR-8.3

Lab measurement on the production build with 4x CPU slowdown, 1280 px, five runs, on a development laptop on battery.

| Metric | Budget | Measured |
|---|---|---|
| LCP, search results | under 2.0 s | 0.63 to 0.76 s |
| Interaction latency, used as a lab proxy for INP | under 200 ms | slowest of 16 kinds of interaction 128 ms (opening the type filter) |
| CLS over the whole scripted session | under 0.1 | 0.002 |
| Initial JS, gzip | under 250 KB | see the performance budget in the README |

## Task walk

The five tasks of docs/06 section 17.2, performed by the agent with a script on a fresh clone. This is not a test with participants.

| Task | Result |
|---|---|
| 1. Most recent imaging report mentioning pulmonary embolism | Failed in the first walk (F19). Pass after the fix: type Diagnostic report and Sort by Newest put the Jan 11, 2025 report first |
| 2. Lab reports of the last 6 months about kidney function | Pass, as the filters are set correctly. The result is empty because the data ends in 2025 (F20) |
| 3. Chief concern and one high severity anomaly of the top patient | Pass |
| 4. Open the record behind a diagnosis | Pass |
| 5. Task 1 by keyboard only | Failed in the first walk for the same reason. Pass after the fix |

## Limits of Newest

Newest matches words, not meaning. Records that use a synonym or an abbreviation are not found ("blood clot in the lung" finds nothing), and a negated mention ("no evidence of pulmonary embolism") still matches. The screen states the rule, and an empty result offers relevance. On 11 held-out queries exact matching had the newest relevant record among its five in 5. A semantic fallback reached 7, but showed five unrelated records as the newest for one query, so it was not used.

## Not covered

Screen readers, touch devices, browsers other than Chromium, zoom to 200 and 400 percent, long real-world names and notes, and real users.

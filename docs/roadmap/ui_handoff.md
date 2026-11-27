# UI Handoff

November 26 2026 | From the UI session (`sandhata-62`) to the main session

The owner wants all updates committed together from the main session. Nothing is committed by the UI session.

## State

- Branch `feature/daily-job-search`, last commit `ef13879`. All UI work is uncommitted in this working folder.
- `scripts/run_tests.py`: 149 passed on November 26 2026 after the last code change.
- Web app restarted on the final code at http://localhost:8605.

## Files to commit

| Files | Change |
| --- | --- |
| `src/sandhata/ui.py` | Shell, resume library, tracker, admin; screens moved out |
| `src/sandhata/ui_common.py`, `ui_today.py`, `ui_discover.py`, `ui_results.py`, `ui_insights.py` (new) | Phase A screens and Insights palette |
| `src/sandhata/assets/theme.css`, `presentation.py`, `.streamlit/config.toml` | Emerald and Gold palette, sidebar tag line, landing text |
| `deploy/keycloak/themes/sandhata/login/` (3 files) | Sign-in palette and rebuilt theme |
| `scripts/build_login_theme.py` | Sign-in colours. **Backend-owned file edited by the UI session** |
| `tests/test_presentation.py`, `tests/test_ui_screens.py` (new) | Palette assertions and screen coverage |
| `docs/roadmap/ui_update_instructions.md` | Colour rule updated |
| `docs/roadmap/ui_backend_requests.md`, `ui_handoff.md` (new) | Backend requests and this note |

## Check before committing

- `deliverables/study-guides/` is untracked and was not created by the UI session. Ask the owner whether to include it.
- `scripts/run_tests.py` and `scripts/backup.py` rewrite tracked files under `deliverables/verification/`. The UI session restored them; restore them again or include them deliberately.
- Rebuild the sign-in theme with `scripts/build_login_theme.py` after any change to `theme.css` or `presentation.py`.
- Never add `runtime/`, `backups/` or `.env`.

## Database and backups

- Local database migrated on November 26 2026 (`watchlists`, `jobs.is_new`); record counts were unchanged.
- Encrypted backups in `backups/`: before migration `sandhata-20261126T232133005494Z.enc`, after `sandhata-20261126T232925450254Z.enc`. Both passed a restore test.
- Full project and Keycloak copy: `C:\Users\Chepuri\AI-Products\Backups\SANDHATA\20261126-182924`. It is unencrypted, contains secrets, and predates the palette, Insights and sidebar changes.
- `scripts/backup.py` fails on a database without the `watchlists` table.

## Open items

- Backend requests R1 to R6 in `ui_backend_requests.md`.
- Phase B design is not started.
- `docs/13_UI_Design_and_User_Guide.md` still describes the old blue palette.
- Not verified: real signed-in session (including the single "Administrator" label), live employer scans, an Ollama comparison, Resume Library and Admin Console appearance, hover states, keyboard focus, reduced motion.
- The last Insights border and date fixes were captured but not inspected by eye.
- Dataframe rows stay white in dark mode.

## Merged

November 26 2026: committed and merged with the document manager on feature/ui-and-documents. The UI files are no longer reserved for a separate session.

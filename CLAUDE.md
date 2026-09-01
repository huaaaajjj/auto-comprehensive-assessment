# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Two Selenium scripts against TJU's peer comprehensive-assessment (综测) web app:

- `auto_fill.py` — walks every page of the classmate list and fills the five subscores (德智体美劳) for each student.
- `record_once.py` — interactive diagnostic. You score one student by hand; it dumps the page structure (URL, dialog count, every input with its nearby label text, buttons, full HTML to `record_*.html`). Run this first whenever the site's markup changes instead of guessing at selectors.

No build, no test suite, no linter, no package manifest. Only dependency is `selenium`.

```shell
pip install selenium
python auto_fill.py
python record_once.py     # when selectors break
```

Verify edits with `python -m py_compile auto_fill.py` — that is the only check runnable without campus network access.

## Cannot be verified locally

The target is `http://172.31.126.2` — reachable only from TJU's network, and it needs a real logged-in student session. You cannot smoke-test changes; the user runs them and pastes the output. Design changes so that **one run yields enough diagnostics to fix the next thing** (print what was found, not just that something failed) — round trips are expensive because each one costs the user a manual login.

## Site facts established by probing (do not re-derive)

- **Auth is CAS SSO.** The router has `{path:"/login", redirect:"/singlelogin"}`; the old password form (`views/login.vue`, `POST /login`, `/captchaImage`) still exists in the bundle but has no route. The README's student-ID-as-password trick is dead. Login is not automated — the script waits for the user to authenticate in the visible browser window. The CAS entry is `/prod-api/casLogin?source=1`, SSO host `sso.tju.edu.cn`.
- **Student list route is `/StudentPage`** (`STUDENT_LIST_URL`). A `?token=…` deep link works while the token is fresh but expires; on expiry the script falls back to navigating to `/StudentPage` after manual login.
- **Pages render blank until refreshed.** Both the list and the scoring page frequently come up empty; one `driver.refresh()` fixes it. This masqueraded as missing selectors for several rounds — `.action` reported 0 elements only because the table had not rendered.
- **Scoring page** is a real route, `/evaluation/list/<planId>/<studentId>?breadNum=2` (planId was 1039). It carries 4–5 hidden `.el-dialog` elements, so input lookups must filter on `is_displayed() and is_enabled()` — that filter is what narrows things to exactly the 5 score boxes. Submit button text is `提交`.
- **The 打分 cell** is `<div class="cell"><div class="action"><span class="iconfont icon-icon_xueshengziping" title="打分"></span></div></div>`. Click the inner `span`, not the wrapper.
- Element Plus table rows are `.el-table__row`; the pager has a jump-to-page input at `.el-pagination__editor input`.

## Invariants that exist for a reason — don't undo them

Submitting a score is **irreversible**, and the script clicks submit in a loop. Every one of these guards protects against a wrong irreversible write:

- `DRY_RUN` (default `True`) fills the form and locates the submit button but never clicks it. Leave it `True`; only the user flips it after reviewing a dry run.
- **Refresh resets pagination to page 1.** So `table_rows()` is strictly read-only and the refresh lives in `wait_for_rows()`, and `fill_one()` must order things: ensure content → `goto_page(page)` → *then* read rows. Getting this backwards silently re-scores page 1 and skips page 2.
- **`wait_for_rows()` must never refresh a login page.** An earlier version put `refresh()` inside a function passed to `WebDriverWait(...).until()`, which polls every 500ms — it reloaded the login page continuously and the user could not finish typing their password. Hence the `on_login_page()` guard.
- `goto_page()` asserts the pager's active page matches the requested one and exits rather than scoring the wrong page.
- The 5 score inputs have **empty placeholders**, so positional filling is a bet on the order being 德智体美劳. `input_label()` reads each input's surrounding text and the script pairs value→input by label; if it cannot uniquely match all five it refuses to submit (positional fill is allowed only under `DRY_RUN`). 德=20 vs 智=50 swapping is a real, silent, unrecoverable error.
- Per-item maximums differ by school and undergrad/grad year, and the server clamps overflow to its own max — a wrong preset silently submits a different score than intended. The user has confirmed `智=50` for their case.

## Configuration lives at the top of `auto_fill.py`

`page_num`, `grades`, `DRY_RUN`, `SCORE_COLUMN`. `grades` is positional over `ITEMS` (`德智体美劳`); keep the commented-out alternative presets, they are documented options. Row count per page is read from the DOM (`len(rows)`), not assumed to be 10 — the last page is usually short (observed: 10 + 8 = 18 students).

Line ~26 hardcodes a `token=` deep link. That token is a **live session credential** for the user's account — it must not be committed. `record_*.html` dumps contain classmates' names and student IDs; also not for committing.

## Docs

README.md is Chinese, aimed at users new to Python. It still documents the dead student-ID login and references line numbers in the script — update it when touching the login flow.

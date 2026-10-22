# Once — Decision Log

Append-only. Each entry: date, question, evidence, choice, reason.
Decisions D1–D10 below are copied verbatim from `AGENTS.md` (they are pre-made and must not be re-litigated; if one is found wrong, flag it in the step report and continue with it).

## 2026-10-22 — Revised product direction and first milestone

- **Question:** How should the file-management-first specification fit the
  clarified workflow automation vision?
- **Choice:** Treat workflow orchestration as the primary product and retain
  file scanning, planning, execution, and recovery as one later integration.
  Preserve the existing safety invariants for that integration.
- **Reason:** This preserves verified prior work while preventing the first
  milestone from becoming a file-organizer GUI that cannot grow into the
  intended orchestration product.
- **Implementation decision:** The first milestone uses immutable declarative
  `REPORT` and `FAIL` steps. They exercise real orchestration state and error
  propagation without pretending to control an external application.
- **Unresolved:** The contracts for desktop automation, browser automation,
  coding-agent coordination, and monitoring integrations require separate
  design and verification before implementation.

## 2026-10-22 — AI-assisted recorder provider and credential policy

- **Question:** How should Once support AI-assisted recording without allowing
  an AI provider to execute actions or expose credentials?
- **Choice:** Add a provider-independent interface, a deterministic fake
  provider for tests, and Gemini as the first real cloud adapter. Cloud AI is
  disabled by default and requires explicit activation and consent.
- **Credential policy:** Use Windows Credential Manager for normal Windows
  operation. Permit environment-variable credentials only for development and
  tests. Never store credentials in ordinary configuration files, workflow
  JSON, recordings, logs, or source control.
- **Reason:** This permits a real demonstrator while preserving local-first
  operation, test determinism, and the rule that AI proposes validated
  workflow data but never executes it.
- **Implementation decision:** The first recorder milestone stores an event log
  plus user-selectable screenshots/keyframes. Continuous video is optional,
  not required for the event-log source of truth. Target application support
  begins with whichever Windows UI metadata can be captured and verified on
  the development machine; unsupported targets must be reported rather than
  implied to work.
- **Unresolved:** Gemini SDK/API compatibility and Windows UI Automation
  capture-library compatibility on Python 3.14.3 require a primary-source
  compatibility spike and real local installation tests before pinning
  dependencies.

## 2026-10-22 — Recorder library compatibility spike

- **Question:** Which libraries can support the first local recorder milestone
  on Windows with Python 3.14.3?
- **Evidence:** PyPI reports `mss 10.2.0` with Python 3.9+ and Windows
  classifiers; `pywin32 312` has a CPython 3.14 Windows wheel and Python 3.14
  classifier; `pywinauto 0.6.9` provides Windows UI Automation support but
  publishes no `Requires-Python` bound; `pynput 1.8.2` imports on this
  interpreter but its PyPI classifiers stop at Python 3.9.
- **Local verification:** Installed `mss==10.2.0`, `pynput==1.8.2`,
  `pywinauto==0.6.9`, and `pywin32==312` into `.venv`. Imports succeeded.
  `mss.MSS().monitors` detected 2 monitors. `pywinauto.Desktop(backend="uia")`
  enumerated a live Windows taskbar window. A probe that printed
  `pynput.__version__` failed because that attribute is not exposed; the
  package import itself succeeded.
- **Choice:** Pin these versions, keep OS capture behind replaceable adapters,
  and treat `pynput` Python 3.14 support as empirically verified for import
  only, not as a formal upstream compatibility guarantee.
- **Reason:** These libraries provide the needed Windows capabilities without
  placing OS APIs in the UI or engine. Automated tests continue to use fake
  event sources and do not send input.

## 2026-10-22 — Gemini request authentication

- **Question:** Where should the Gemini API credential be sent?
- **Evidence:** Official Gemini API documentation at
  `https://ai.google.dev/gemini-api/docs` shows REST requests using the
  `x-goog-api-key` header. The API-key documentation also recommends
  environment variables for local development.
- **Choice:** Send the key only in the `x-goog-api-key` header, never in the
  URL query string. Keep the adapter disabled unless explicitly enabled by the
  caller.
- **Reason:** URLs can be copied into logs, browser history, proxies, or error
  reports. Header transport reduces accidental credential exposure.

---

## 2026-10-21 — Step 0: Pre-flight evidence and toolchain decision

### A. Environment detection (verified locally, commands run 2026-10-21)

| Fact | Evidence (command) | Result |
|---|---|---|
| OS | `cmd //c ver` | Microsoft Windows [version 10.0.26300.9550] (Windows 11, build 26300) |
| Python interpreters | `py -0p` | `-V:3.14 *` `C:\Python314\python.exe` (default); `-V:3.13` `C:\Python313\python.exe`; `-V:3.12` `C:\Users\DELL\AppData\Local\Programs\Python\Python312\python.exe` |
| Default interpreter | `python --version` | Python 3.14.3 |
| 3.13 patch level via launcher | `py -3.13 -c "import sys; print(sys.version)"` | 3.13.5 |
| git | `git --version` | git version 2.55.0.windows.4 |
| Repo state | `git rev-parse --show-toplevel` (after Step 1 `git init`) | New project repo rooted at `C:\Users\DELL\once` (created as a fresh repo outside the parent home repo). |
| `st_birthtime` on Windows | `py -3.14 -c "import os; print(hasattr(os.stat('.'), 'st_birthtime'))"` and same on 3.13 | True on both (3.14.3 and 3.13.5). Creation time IS available on Windows; `FileEntry.birthtime_ns` needs no fallback on the target OS. Fallback `None` remains for non-Windows dev machines. |

### B. Current facts looked up (do not rely on memory) — all fetched 2026-10-21

**1. Python versions currently supported by python.org**  
Source: https://devguide.python.org/versions/

- 3.15 — bugfix — first release 2026-10-09 — EOL 2031-10
- 3.14 — bugfix — first release 2025-10-07 — EOL 2030-10
- 3.13 — security — EOL 2029-10
- 3.12 — security — EOL 2028-10
- 3.11 — security — EOL 2027-10
- main branch = future 3.16 (feature stage; python.org/downloads lists 3.16 as pre-release, planned 2027-10-06)
- 3.10 reached end-of-life 2026-10-01 (no longer supported)

**2. Latest stable PySide6, Requires-Python, Windows x64 wheels**  
Source: https://pypi.org/project/PySide6/ (fetched 2026-10-21)

- Latest release: **PySide6 6.12.0**
- `Requires-Python`: **>=3.10, <3.16**
- Trove classifiers list Python 3.10, 3.11, 3.12, 3.13, 3.14, **3.15**
- Windows x64 wheel exists: `pyside6-6.12.0-cp310-abi3-win_amd64.whl` — an **abi3** wheel built on CPython 3.10, so the same wheel installs on any CPython 3.10–3.15 including 3.14
- **Not concluded unsupported:** the existence of a single cp310-abi3 wheel does not mean 3.14 is unsupported; per the user direction, PySide6 support on 3.14 is treated as plausible and must be verified by a real install + import in Step 1. Until verified, it is marked **NOT VERIFIED** here.
- License: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only (relevant to packaging obligations, Step 15/17).

**3. Dev-tool versions and compatibility**  
Versions obtained via `py -3.14 -m pip index versions <pkg>` (live PyPI query, 2026-10-21); details from PyPI pages where fetched.

| Package | Latest version | Python compatibility (evidence) |
|---|---|---|
| pytest | 9.1.1 | "Python 3.10+ or PyPy3" — https://pypi.org/project/pytest/ |
| pytest-cov | 7.1.0 | no upper bound published; depends on pytest (3.10+) |
| pytest-qt | 4.5.0 | works with PySide6/PyQt6/PyQt5; prefers PySide6 — https://pypi.org/project/pytest-qt/ |
| ruff | 0.17.1 | standalone Rust binary; independent of runtime interpreter version |
| pyinstaller | 6.22.3 | supports 3.8–3.15 (does not work with beta 3.16) — https://pypi.org/project/pyinstaller/ |
| send2trash | 2.1.0 | classifiers list Python 3.8–**3.14** (no 3.15) — https://pypi.org/pypi/send2trash/2.1.0/json |

**send2trash maintenance check (required by D2):**

- Latest release 2.1.0; GitHub release dated **Jan 13, 2026** (https://github.com/arsenetar/send2trash/releases — taken from search-snippet evidence because the raw page was not fetchable from this environment; treat the date as best-evidence, the version itself as verified from PyPI)
- PyPI Development Status: "5 - Production/Stable"
- Windows support: uses native `IFileOperation` (Vista+, with pywin32) falling back to `SHFileOperation`; pure `ctypes`, no compilation needed (PyPI package description)
- Compatibility with the chosen Python on Windows verified locally: `py -3.14 -m pip install --dry-run send2trash==2.1.0` → `Would install Send2Trash-2.1.0` (exit 0)
- Verdict: **approved as the D2 runtime dependency**, pinned in Step 1 after a real install

**4. Microsoft's current reserved names and invalid characters**  
Source: https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file ("Naming Files, Paths, and Namespaces", fetched 2026-10-21)

- Reserved characters: `< > : " / \ | ? *`, the ASCII NUL character (integer zero), and characters with integer values **1 through 31**
- Reserved device names (case-insensitive): **CON, PRN, AUX, NUL, COM0–COM9, LPT0–LPT9**, plus the same names with the superscript-digit variants COM¹ COM² COM³ and LPT¹ LPT² LPT³
- Quote: "Also avoid these names followed immediately by an extension; for example, NUL.txt and NUL.tar.gz are both equivalent to NUL."
- Superscript digits confirmed: Windows treats the ISO/IEC 8859-1 superscript digits ¹ ² ³ as digits in COM#/LPT# device names, making those reserved in every directory
- "Do not end a file or directory name with a space or a period… it is acceptable to specify a period as the first character of a name. For example, '.temp'."
- Names are case-insensitive by default ("consider the names OSCAR, Oscar, and oscar to be the same"); NTFS POSIX case-sensitivity exists but is not the default. This backs D4/collision_key design.

**5. `os.stat_result.st_birthtime` on Windows**  
Verified locally (see table A): available on both installed interpreters (3.14.3, 3.13.5). Fallback if ever absent (non-Windows dev): `birthtime_ns=None`, date rules fall back to modified time with a WARNING (design already required by AGENTS.md InsertDate rule).

### C. Python version choice (the rule: newest version officially supported by PySide6 AND by all dev dependencies)

- PySide6 6.12.0 documents `Requires-Python >=3.10, <3.16`; PyInstaller 6.22.3 supports 3.8–3.15; pytest supports 3.10+.
- **send2trash 2.1.0 publishes support only up to Python 3.14**, and send2trash is the one allowed non-stdlib runtime dependency (D2).
- Chosen: **Python 3.14 (currently installed 3.14.3)**. It is the newest version supported by all known dependencies and is already the default interpreter here.

**NOT VERIFIED:** empirical PySide6 import on 3.14. That must be confirmed in Step 1 by installing PySide6 6.12.0 and importing it successfully. Until then, treat PySide6-on-3.14 as *probable but unverified*.

### D. Pre-made decisions D1–D10 (copied from AGENTS.md — standing, not re-opened here)

- **D1.** Same-volume moves/renames only. A MOVE whose source and destination are on different volumes/drives is an ERROR (`CROSS_VOLUME_MOVE_UNSUPPORTED`) in v1, because it silently becomes copy+delete. COPY across volumes is allowed.
- **D2.** Undo of a COPY must remove the created copy. Because v1 forbids permanent deletion, the copy is sent to the Windows Recycle Bin via `send2trash`, and only after verifying the copy is unchanged (size, mtime_ns, SHA-256 equal to the journal's post-copy record). Fallback if `send2trash` is unavailable/unsuitable: mark COPY operations "not undoable" (explain in UI) — do NOT implement os.remove/unlink for user files.
- **D3.** Undo of CREATE_FOLDER removes the folder only if it was created by that run AND is currently empty (`os.rmdir`, which fails on non-empty). This is not deletion of user data.
- **D4.** Rename cycles (A->B and B->A in one plan) are an ERROR (`CYCLE_DETECTED`) in v1. Chains (A->B, B->C) are allowed and are executed in dependency order. Case-only renames (a.txt -> A.txt) are allowed and executed via a journaled two-step temporary name because Windows paths are case-insensitive.
- **D5.** Extensions are never changed by rename rules (only optional case normalisation such as `.JPG` -> `.jpg`).
- **D6.** Per-operation failure policy: continue with other independent operations; operations depending on a failed one (e.g. move into a folder whose creation failed) are SKIPPED with a reason. A `stop_on_error` flag exists (default False).
- **D7.** A plan containing ERROR issues cannot be executed. The UI offers "Exclude problem files and re-plan", which produces a NEW plan that the user must review and approve again.
- **D8.** Scanning is non-recursive by default; skips directories, symlinks/junctions, and (by default) hidden/system files. The user can opt in to subfolders and to hidden files.
- **D9.** Long paths: any resulting path longer than 259 characters is an ERROR (`PATH_TOO_LONG`). Do not use the `\\?\` prefix in v1.
- **D10.** Inference of rules from examples is deterministic (no ML, no network): enumerate candidate rules, keep only those reproducing ALL examples exactly, then check whether surviving candidates disagree on other files in the folder; if they do, ASK the user instead of guessing.

Standing assessment: none of D1–D10 found wrong at this time. D2's dependency requirement is satisfied (evidence in B.3). D4's case-only-rename premise is backed by Microsoft's case-insensitivity documentation (B.4). D4 reserved-name list extended per user direction to include **COM0 and LPT0**, citing the same Microsoft source.

### E. Pinning policy for Step 1

Availability verified today (B.3); exact pins will be written into `requirements.txt` / `requirements-dev.txt` only after a real, successful install in Step 1, with the `pip list` excerpt pasted into the step report, per AGENTS.md ("Do NOT pin anything you could not verify"). Planned pins: PySide6==6.12.0, send2trash==2.1.0, pytest==9.1.1, pytest-cov==7.1.0, pytest-qt==4.5.0, ruff==0.17.1, pyinstaller==6.22.3 — each still to be confirmed by installation.

### F. Open questions for the human (max 3)

1. **send2trash 2.1.0 release date is best-evidence, not directly verified.** The GitHub release page did not fetch in this environment; the date came from a search snippet. If you require primary-source verification, the human can open https://github.com/arsenetar/send2trash/releases and confirm.
2. **PySide6 6.12.0 on Python 3.14 is marked NOT VERIFIED until Step 1 installs + imports it.** If it fails, the fallback decision (not yet exercised) is to revert to Python 3.13 for the runtime.
3. None other — no blocking questions.

### G. Additional standing decisions from the master plan

- **D11.** A failed copy may leave an app-created `<dest>.once-part-<uuid8>` temporary. Cleanup uses the Recycle Bin only when safe; otherwise the path is reported.
- **D12.** A suffix is the final `Path.suffix`; dotfiles have an empty suffix and their full name as the stem.
- **D13.** Creation time uses `st_birthtime` when available, never `st_ctime`; missing creation time falls back to modified time with a warning.
- **D14.** Byte sizes use integer arithmetic; human-readable size formatting belongs only in the UI.

## 2026-10-22 — Resume check

The repository was confirmed at `C:\Users\DELL\once` and had no commits. `AGENTS.md`,
the Step 1 skeleton, and the pre-existing Phase 0 decision/log files were present.
The repo-local Git identity remains unset in this project. The user may configure it later with a repo-local `git config user.name` and `git config user.email` if desired.
The baseline command showed one fixture failure caused by Windows text newline
translation (`"a\n"` is stored as three bytes), and Ruff reported one unformatted file.

## 2026-10-22 — Step 1: Project foundation

The selected Python 3.14 environment installed all exact pins successfully.
`PySide6 import ok` was confirmed with `.\.venv\Scripts\python.exe -c
"import PySide6.QtWidgets; print('PySide6 import ok')"`. PyInstaller 6.22.3
was added to the development requirements and installed successfully.

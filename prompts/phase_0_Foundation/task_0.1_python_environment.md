# Task 0.1 — Python Environment

You are working inside my SEC RAG repository.

We are executing:

```text
Phase 0 — Build the System Foundation
Task 0.1 — Python Environment
```

Phase 0.0 Git Safety Preflight has passed.

The purpose of this task is to create a **clean, project-local, reproducible Python environment** instead of relying on the globally installed Python environment.

This task is deliberately narrow.

Do NOT begin:

```text
0.2 CUDA / PyTorch / GPU validation
0.3 repository restructuring
0.4 dependency management
0.5 configuration
0.6 logging
0.7 storage abstraction
0.8 tests
0.9 developer commands
0.10 serving spike
```

Some minimal environment verification is allowed, but do not turn this into the CUDA or dependency-installation task.

---

# OBJECTIVES

Complete only these goals:

1. inspect the Python installations available on this machine,
2. select an appropriate Python version for this ML/RAG project,
3. document why that version was chosen,
4. create a project-local `.venv`,
5. verify activation and interpreter isolation,
6. verify `.venv` is ignored by Git,
7. record reproducible setup commands,
8. update `Progress.md`,
9. do not commit or push yet.

---

# IMPORTANT CONTEXT

The pre-Phase-0 audit found that the machine's current global interpreter is approximately:

```text
Python 3.14.x
```

and globally installed packages include several ML/data packages.

Do NOT treat the global environment as the project environment.

A globally working:

```text
torch
sentence-transformers
duckdb
fastapi
```

installation does not make this repository reproducible.

We need a clean project-local environment.

---

# STEP 0 — SAFETY PRECONDITION

Before creating the environment, verify:

```text
.gitignore exists
.venv/ is ignored
data/ remains ignored
.tmp/ remains ignored
```

Also inspect `Progress.md` for any real contact value embedded in historical examples such as:

```text
SEC_USER_AGENT="..."
```

The repository's Git conventions prohibit committing a real contact address in that example.

If a real personal contact string is present, replace only the historical command value with a neutral placeholder such as:

```bash
export SEC_USER_AGENT="Your Name your.email@example.com"
```

Do not alter the surrounding engineering history.

This is a small carry-over Git-safety correction, not a Phase 0.1 feature.

Never print the original contact value in your final response.

---

# STEP 1 — INSPECT THE OPERATING ENVIRONMENT

Determine:

```text
operating system
architecture
default shell
current working directory
```

Then identify available Python interpreters.

On Windows, useful commands may include:

```powershell
py -0p
where python
python --version
```

On Linux/macOS, equivalents may include:

```bash
which -a python
which -a python3
python --version
python3 --version
```

Use the commands appropriate for the actual machine.

Do not assume the operating system from old documentation.

---

# STEP 2 — SELECT THE PROJECT PYTHON VERSION

Choose a Python version appropriate for:

```text
PyTorch
sentence-transformers
transformers
LanceDB
DuckDB
PyArrow
FastAPI
ONNX Runtime
Docling
pytest
```

The priority is ecosystem compatibility and reproducibility, not using the newest interpreter available.

## Preferred policy

Prefer:

```text
Python 3.12.x
```

if a suitable installation is available.

If 3.12 is not available, consider:

```text
Python 3.11.x
```

as the fallback.

Do NOT automatically select Python 3.14 merely because it is the current global interpreter.

If you believe another version is clearly preferable based on the actual environment, explain the evidence before using it.

Do not perform a web research project for this task.

Use installed interpreter availability and known compatibility considerations.

---

# STEP 3 — HANDLE A MISSING SUITABLE PYTHON VERSION

If Python 3.12 or another selected compatible version is already installed:

continue.

If no suitable project interpreter exists:

do not silently create the venv using Python 3.14.

Instead determine whether installing the selected Python version is straightforward.

If installation can be done safely using the normal platform mechanism, install only the Python interpreter.

Examples might include:

```text
official Python installer
Windows py launcher-supported installation
winget
system package manager
pyenv
```

Use the simplest normal mechanism for the actual machine.

Do NOT:

```text
install CUDA
install project ML libraries
modify system Python packages
uninstall the global Python
replace system Python
```

If interpreter installation requires administrator access or an invasive system change, stop and report:

```text
BLOCKED — suitable Python interpreter not available
```

rather than making a risky change.

---

# STEP 4 — RECORD THE PYTHON VERSION

Once selected, record:

```text
major.minor.patch
executable path
architecture
```

For example:

```text
Python: 3.12.x
Architecture: 64-bit
Executable used to create venv: ...
```

Avoid exposing unnecessary personal absolute paths in public documentation.

If an absolute path contains a personal username, sanitize it in `Progress.md`.

---

# STEP 5 — CREATE `.python-version`

Create a root:

```text
.python-version
```

containing the selected major/minor version, for example:

```text
3.12
```

This is a small tracked reproducibility artifact.

Do not put a machine-specific executable path in this file.

Verify:

```bash
git check-ignore -v .python-version
```

shows that it is trackable.

---

# STEP 6 — CREATE PROJECT-LOCAL VIRTUAL ENVIRONMENT

Create:

```text
.venv/
```

at repository root using the selected interpreter.

Use the platform-appropriate command.

Conceptually:

```bash
python3.12 -m venv .venv
```

or Windows equivalent.

Do not create:

```text
venv/
env/
project_env/
```

Use exactly:

```text
.venv/
```

---

# STEP 7 — VERIFY `.venv` IS GIT-IGNORED

Run:

```bash
git check-ignore -v .venv/
```

and inspect:

```bash
git status --short
```

The virtual environment must never appear as a trackable project artifact.

If `.venv/` is not ignored:

fix `.gitignore` minimally and verify again.

---

# STEP 8 — ACTIVATE THE ENVIRONMENT

Activate `.venv` using the correct command for the current shell.

Examples:

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Windows CMD:

```cmd
.venv\Scripts\activate.bat
```

bash/zsh:

```bash
source .venv/bin/activate
```

Do not assume which one applies.

Verify activation by checking:

```text
python executable
python version
pip executable
```

The Python executable must resolve inside:

```text
<repo>/.venv/
```

rather than the global interpreter.

---

# STEP 9 — VERIFY ENVIRONMENT ISOLATION

Inside the activated environment, run checks equivalent to:

```bash
python --version
python -c "import sys; print(sys.executable)"
python -c "import sys; print(sys.prefix)"
python -m pip --version
```

Confirm:

```text
sys.executable belongs to .venv
sys.prefix belongs to .venv
Python version is the selected version
pip belongs to .venv
```

Do not depend on shell prompt decoration alone.

---

# STEP 10 — BOOTSTRAP PACKAGING TOOLS ONLY

Inside `.venv`, ensure the environment has usable packaging tooling.

It is acceptable to update:

```text
pip
setuptools
wheel
```

if necessary.

Do NOT install project dependencies yet.

Specifically do not install:

```text
torch
sentence-transformers
transformers
lancedb
duckdb
pyarrow
fastapi
onnxruntime
docling
```

as part of this task.

Those belong to later Phase 0 tasks.

The purpose here is to establish the interpreter and environment, not the dependency graph.

---

# STEP 11 — VERIFY GLOBAL PACKAGES ARE NOT BEING INHERITED

Run a lightweight check.

The environment should not be configured with:

```text
--system-site-packages
```

unless explicitly documented and justified.

Inspect:

```text
pyvenv.cfg
```

and verify conceptually:

```text
include-system-site-packages = false
```

If the new `.venv` can import arbitrary globally installed project packages despite none being installed locally, investigate.

We want an isolated environment.

---

# STEP 12 — CAPTURE A MINIMAL ENVIRONMENT SNAPSHOT

Record:

```bash
python --version
python -m pip --version
python -m pip list
```

At this stage `pip list` should be very small because project dependencies have not yet been installed.

Do NOT create the final:

```text
requirements.txt
```

yet.

That belongs to:

```text
Task 0.4 — Dependency Management
```

Do not freeze bootstrap-only packages into the future runtime dependency list.

---

# STEP 13 — DOCUMENT ENVIRONMENT SETUP

Create:

```text
project_plan/ENVIRONMENT.md
```

if no equivalent environment/setup document already exists.

If an equivalent file already exists, update it instead of creating duplicate documentation.

Keep this document concise.

At this stage it should contain:

```markdown
# Development Environment

## Python

Selected version: Python X.Y

Reason:
...

## Create the environment

### Windows PowerShell
...

### bash/zsh
...

## Activate

...

## Verify

python --version
python -c "import sys; print(sys.executable)"

## Notes

Project dependencies are intentionally not installed in Task 0.1.
Dependency installation is defined in Task 0.4.
CUDA/PyTorch validation is defined in Task 0.2.
```

Only document commands that are valid for the actual project setup.

You may include both Windows and Unix activation commands for educational value, but clearly identify which environment was actually tested.

Do not claim commands were tested on operating systems you did not use.

---

# STEP 14 — CHECK REPRODUCIBILITY FROM A FRESH SHELL

The important test is not that the environment works in the shell that created it.

Open or simulate a fresh shell/process where practical.

From repository root:

1. activate `.venv`,
2. run `python --version`,
3. print `sys.executable`.

Verify the environment can be entered without relying on temporary shell state from its creation command.

If practical, deactivate first:

```text
deactivate
```

then reactivate and verify again.

---

# STEP 15 — GIT SAFETY CHECK

After creating the environment and documentation run:

```bash
git status --short
git status --ignored --short
git count-objects -vH
```

Expected:

```text
.venv/ ignored
.python-version trackable
project_plan/ENVIRONMENT.md trackable
Progress.md trackable
```

No `.venv` content should appear in the stageable file set.

Do NOT use:

```bash
git add .
```

Do NOT commit.

Do NOT push.

---

# STEP 16 — UPDATE `Progress.md`

Preserve all existing history.

Append a new dated section:

```markdown
## YYYY-MM-DD — Phase 0.1 Python Environment
```

Use the current local date.

Include the following.

## Objective

Explain that the project moved from an ad hoc global Python environment to a reproducible project-local environment.

## Initial State

Summarize:

```text
no project-local venv
global Python version
selected Python version
why global environment was insufficient
```

Do not include unnecessary personal paths.

## Python Version Decision

Record:

```text
selected version
other versions considered
reason for selection
```

Be specific.

Example reasoning:

```text
Selected Python 3.12 rather than the machine's newer global interpreter to favor broad ML/data-library compatibility and reproducibility.
```

Only use this wording if that is what actually happened.

## Environment Created

Record:

```text
.venv location
creation command
activation command
```

Use repository-relative paths.

## Verification

Record:

```text
python version
sys.executable resolves inside .venv
pip resolves inside .venv
include-system-site-packages = false
fresh activation test
```

## Files Created / Modified

Likely:

```text
.python-version
project_plan/ENVIRONMENT.md
Progress.md
```

And possibly:

```text
.gitignore
```

only if a small correction was required.

Do NOT list `.venv` as a tracked repository file.

You may state:

```text
.venv/ created locally and ignored by Git
```

## Phase Result

Use exactly one:

```text
PASS — reproducible project-local Python environment established
WARN — environment works but one non-blocking issue remains
BLOCKED — project-local Python environment could not be established safely
```

## Phase Status

If PASS:

```text
Data Preparation             — COMPLETE
Phase 0                      — IN PROGRESS
  0.0 Git Safety Preflight   — COMPLETE
  0.1 Python Environment     — COMPLETE
  0.2 CUDA/GPU Validation    — NEXT
```

Do not mark 0.2 complete merely because the global machine previously detected the GPU.

---

# STEP 17 — DO NOT VALIDATE CUDA YET

The historical audit already found:

```text
torch.cuda.is_available() = True
RTX 5060 Laptop GPU detected
compute capability sm_120
```

but that check occurred in the global environment.

Do NOT copy the global PyTorch installation into `.venv` merely to reproduce it.

Do NOT install PyTorch during this task just to test CUDA.

That belongs to:

```text
task_0.2_cuda_gpu_validation.md
```

The correct state after this task may therefore be:

```text
Python environment: verified
CUDA inside .venv: not yet tested
```

That is intentional.

---

# ACCEPTANCE CRITERIA

Task 0.1 is complete only if:

```text
[ ] suitable Python version selected deliberately
[ ] selection rationale documented
[ ] .python-version exists
[ ] .venv created at repository root
[ ] .venv created with selected interpreter
[ ] .venv is isolated from global site-packages
[ ] .venv is ignored by Git
[ ] environment activates successfully
[ ] python resolves inside .venv
[ ] pip resolves inside .venv
[ ] Python version inside .venv is correct
[ ] deactivate/reactivate or fresh-shell check succeeds
[ ] setup commands documented
[ ] project dependencies were NOT installed
[ ] requirements.txt was NOT prematurely created
[ ] CUDA/PyTorch validation was NOT started
[ ] Progress.md updated
[ ] no Git commit created
[ ] no Git push performed
```

---

# STOP CONDITIONS

Stop and report instead of forcing success if:

```text
no suitable Python interpreter can be installed safely
venv creation fails
the environment unexpectedly inherits global packages
Git does not ignore .venv
selected Python version creates an obvious compatibility blocker
```

Do not work around these by using the global environment.

---

# FINAL RESPONSE TO ME

After completing the task, return:

## Task

```text
task_0.1_python_environment.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Python

Report:

```text
selected Python version
reason
```

## Virtual Environment

Report:

```text
.venv created: yes/no
activation verified: yes/no
isolated from global site-packages: yes/no
```

## Files Modified

List each tracked/project file created or modified.

Do not enumerate `.venv` internals.

## Git Safety

Confirm:

```text
.venv ignored
no large files staged
```

## Progress.md

Confirm the Phase 0.1 entry was appended.

## Next Task

If PASS:

```text
task_0.2_cuda_gpu_validation.md
```

Finally state explicitly:

```text
No Git commit created.
No Git push performed.
No Phase 0.2 work started.
```

Stop and wait for my approval.
# Task 0.2 — CUDA / GPU Validation

You are working inside my SEC RAG repository.

We are executing:

```text
Phase 0 — Build the System Foundation
Task 0.2 — CUDA / GPU Validation
```

Previous status:

```text
0.0 Git Safety Preflight — COMPLETE
0.1 Python Environment   — COMPLETE
```

Task 0.1 established:

```text
Python:          3.11.9
Environment:     .venv/
Isolation:       verified
Global packages: not inherited
Project deps:    intentionally not installed yet
```

The machine previously showed, from the old global environment:

```text
GPU:                NVIDIA GeForce RTX 5060 Laptop GPU
Compute capability: (12, 0) / sm_120
CUDA available:     True
```

Those observations are encouraging but **do not count as Task 0.2 completion**.

This task must prove that GPU acceleration works correctly **inside the new project-local `.venv`**.

---

# OBJECTIVE

Establish and document a working PyTorch/CUDA environment for this project.

We need to prove:

```text
.venv
  ↓
PyTorch
  ↓
CUDA runtime
  ↓
NVIDIA driver
  ↓
RTX 5060 Laptop GPU / Blackwell
  ↓
real GPU kernel execution
  ↓
sentence-transformers
  ↓
bge-small-en-v1.5 embedding on GPU
```

This is a **compatibility and smoke-validation task**, not a performance-optimization task.

Do NOT begin:

```text
0.3 Repository Structure
0.4 Dependency Management
0.5 Configuration
0.6 Logging
0.7 Storage Abstraction
0.8 Automated Tests
0.9 Developer Commands
0.10 Serving Feasibility Spike
```

---

# IMPORTANT RULES

Do not assume CUDA works merely because:

```python
torch.cuda.is_available()
```

returns `True`.

Actual CUDA kernels must execute successfully.

Do not assume that `nvidia-smi`'s displayed CUDA version is the same as the CUDA runtime bundled with PyTorch.

Record these separately:

```text
NVIDIA driver version
driver-supported CUDA version from nvidia-smi
PyTorch version
torch.version.cuda
cuDNN version
GPU compute capability
```

Do not install the full NVIDIA CUDA Toolkit or cuDNN separately unless there is a demonstrated need.

A standard PyTorch binary normally bundles the CUDA runtime libraries needed for ordinary PyTorch execution.

`nvcc` is not required for this project at this stage unless we later compile custom CUDA extensions.

---

# STEP 1 — VERIFY TASK 0.1 ENVIRONMENT

From repository root, activate:

```text
.venv/
```

using the correct command for the actual shell.

Verify:

```bash
python --version
python -c "import sys; print(sys.executable)"
```

Expected:

```text
Python 3.11.9
Python executable inside <repo>/.venv/
```

If the active interpreter is not `.venv`, stop.

Do not install anything into global Python.

---

# STEP 2 — INSPECT NVIDIA DRIVER / GPU

Run:

```bash
nvidia-smi
```

Record:

```text
GPU model
NVIDIA driver version
driver-reported CUDA compatibility version
total VRAM
current VRAM usage
```

Do not interpret the `CUDA Version` shown by `nvidia-smi` as the exact runtime PyTorch will use.

Document it as:

```text
driver-supported CUDA version
```

If `nvidia-smi` fails or the GPU is absent:

stop and report:

```text
BLOCKED — NVIDIA GPU/driver not available
```

Do not attempt invasive driver repair automatically.

---

# STEP 3 — DETERMINE THE CORRECT PYTORCH BUILD

We need a PyTorch build that:

```text
supports Python 3.11
supports the installed NVIDIA driver
can execute on RTX 5060 / Blackwell
```

Do not blindly copy the package version from the old global Python environment.

If internet access is available, consult the **official PyTorch installation guidance** for the current stable build.

Use official PyTorch sources rather than random forum posts or third-party wheel mirrors.

Prefer a current stable CUDA-enabled build.

Record:

```text
PyTorch version selected
CUDA wheel/runtime variant selected
reason for selecting it
```

Do not use nightly builds unless the stable build demonstrably fails to execute on `sm_120`.

If stable fails because Blackwell support is genuinely absent and an official nightly is required, stop first and clearly report the evidence before changing channels/builds.

---

# STEP 4 — INSTALL PYTORCH INTO `.venv`

Install PyTorch only into the activated:

```text
.venv
```

Use the official installation command appropriate for the selected build.

At minimum install what is necessary for our workload.

Avoid unnecessary packages.

Do not install:

```text
CUDA Toolkit
Visual Studio CUDA build tools
system-wide CUDA packages
random CUDA DLL bundles
```

unless required by an actual failure.

After installation verify:

```bash
python -m pip show torch
```

and:

```python
import torch
print(torch.__version__)
print(torch.version.cuda)
```

---

# STEP 5 — BASIC CUDA DISCOVERY CHECK

Inside `.venv`, run a Python diagnostic that records:

```python
torch.__version__
torch.version.cuda
torch.cuda.is_available()
torch.cuda.device_count()
torch.cuda.get_device_name(0)
torch.cuda.get_device_capability(0)
torch.cuda.get_arch_list()
torch.backends.cudnn.version()
```

Also record:

```python
torch.cuda.get_device_properties(0).total_memory
```

Report total VRAM in GB.

Expected GPU:

```text
NVIDIA GeForce RTX 5060 Laptop GPU
```

Expected compute capability should be consistent with:

```text
(12, 0)
```

Do not fail solely because `sm_120` is absent from `torch.cuda.get_arch_list()` if real kernels execute correctly; PTX/JIT compatibility may still permit execution.

Actual kernel execution is the authoritative check.

---

# STEP 6 — CHECK FOR CUDA COMPATIBILITY WARNINGS

Pay attention to warnings containing terms such as:

```text
compute capability
sm_120
not compatible
CUDA capability
kernel image
no kernel image available
```

Do not suppress these warnings.

Capture their meaning in `Progress.md`.

If PyTorch explicitly says the GPU architecture is unsupported, investigate before proceeding.

---

# STEP 7 — REAL GPU TENSOR TEST

Do not stop at device detection.

Run actual computation on CUDA.

For example, create moderate matrices such as:

```text
2048 x 2048
```

and execute:

```python
a = torch.randn(..., device="cuda")
b = torch.randn(..., device="cuda")
c = a @ b
torch.cuda.synchronize()
```

Verify:

```text
tensor device = cuda
operation completes
result finite
no kernel error
```

Also transfer a result back to CPU.

Do not allocate unnecessarily huge tensors.

This is a smoke test, not a GPU stress test.

---

# STEP 8 — CPU VS GPU CORRECTNESS SANITY CHECK

Run one deterministic small operation on both CPU and GPU.

For example:

```text
matrix multiplication
```

or another straightforward numerical operation.

Use a fixed seed.

Compare results with an appropriate tolerance using something equivalent to:

```python
torch.allclose(...)
```

Record:

```text
CPU/GPU numerical sanity check: PASS / FAIL
```

This helps catch execution problems that device detection alone would miss.

---

# STEP 9 — MIXED-PRECISION CAPABILITY CHECK

Our later embedding/reranking work may use reduced precision.

Test lightweight operations using:

```text
float32
float16
bfloat16
```

where supported.

For each:

```text
allocation succeeds?
computation succeeds?
result finite?
```

Do not treat a missing optional precision mode as a total project blocker unless it prevents our expected model workload.

Record capabilities accurately.

---

# STEP 10 — RECORD GPU MEMORY BEHAVIOR

Before a test:

```python
torch.cuda.empty_cache()
torch.cuda.reset_peak_memory_stats()
```

After computation record:

```python
torch.cuda.memory_allocated()
torch.cuda.memory_reserved()
torch.cuda.max_memory_allocated()
```

Convert to MB/GB for readability.

This establishes a first reproducible GPU baseline.

Do not infer production memory requirements from this tiny smoke test.

---

# STEP 11 — INSTALL SENTENCE-TRANSFORMERS FOR THE GPU SMOKE TEST

This task's Phase 0 acceptance criteria require a real embedding model to execute on GPU.

Install:

```text
sentence-transformers
```

inside `.venv`.

Allow its required transitive dependencies such as:

```text
transformers
huggingface-hub
tokenizers
```

to install normally.

Do NOT create `requirements.txt` yet.

Final dependency organization belongs to:

```text
task_0.4_dependency_management.md
```

Record the installed versions needed to reproduce this Task 0.2 environment later.

---

# STEP 12 — MODEL CACHE SAFETY

Before downloading the model, inspect:

```text
HF_HOME
HUGGINGFACE_HUB_CACHE
TRANSFORMERS_CACHE
```

if defined.

Make sure model weights will not become trackable Git content.

Preferred behavior:

```text
normal Hugging Face user cache outside repository
```

If a cache is configured inside the repository:

- ensure it is already ignored,
- or select a safe ignored cache location.

Do not commit model files.

Do not modify the frozen `data/` corpus.

---

# STEP 13 — LOAD `bge-small-en-v1.5`

Load:

```text
BAAI/bge-small-en-v1.5
```

with sentence-transformers.

Explicitly request:

```text
device="cuda"
```

or equivalent.

Do not allow silent CPU fallback.

After loading, verify the model parameters/device actually reside on CUDA.

Record:

```text
model
device
embedding dimension
model-load success
```

Expected embedding dimension is approximately:

```text
384
```

Verify rather than assume.

---

# STEP 14 — RUN REAL GPU EMBEDDING INFERENCE

Encode a small batch of representative SEC-style text.

For example:

```text
"The company reported total revenue for fiscal year 2024."

"Item 1A discusses material risks affecting the business."

"Net income increased compared with the previous fiscal year."
```

Use a batch large enough to prove batched execution but small enough to remain a smoke test.

Example:

```text
16–64 short sentences
```

Run on CUDA.

Synchronize before/after timing:

```python
torch.cuda.synchronize()
```

Verify:

```text
embeddings produced
expected shape
all values finite
GPU device used
```

Record peak GPU memory.

---

# STEP 15 — LIGHTWEIGHT EMBEDDING THROUGHPUT MEASUREMENT

This is not our Phase 3 embedding benchmark.

Still, record a basic smoke measurement such as:

```text
number of texts
batch size
elapsed seconds
texts / second
peak VRAM
```

Warm the model once before timing.

Run a few repetitions if inexpensive and report a representative value.

Clearly label the result:

```text
GPU smoke benchmark — NOT production benchmark
```

Do not use it later as a headline system-performance number.

---

# STEP 16 — VERIFY NO CPU FALLBACK

Confirm the embedding model did not silently execute on CPU.

Use multiple signals where possible:

```text
model/device inspection
CUDA memory increase
successful CUDA tensors
```

Do not rely only on elapsed time.

Record:

```text
sentence-transformers GPU execution: VERIFIED
```

only if supported by evidence.

---

# STEP 17 — OPTIONAL CUDA MEMORY CLEANUP CHECK

After model inference:

```python
del model
torch.cuda.empty_cache()
```

where practical.

Observe reserved/allocated memory.

This is informational only.

Do not attempt aggressive driver-level cleanup.

---

# STEP 18 — DOCUMENT THE ENVIRONMENT

Update:

```text
project_plan/ENVIRONMENT.md
```

Add a clearly scoped section such as:

```markdown
## GPU / CUDA

Tested hardware:
- GPU: ...
- VRAM: ...
- Compute capability: ...

Driver:
- NVIDIA driver: ...
- Driver-supported CUDA: ...

PyTorch:
- Version: ...
- CUDA runtime: ...
- cuDNN: ...

Validation:
- CUDA available: yes
- Real CUDA tensor operation: pass
- CPU/GPU numerical check: pass
- FP16: ...
- BF16: ...
- bge-small GPU inference: pass

Important:
`nvidia-smi` CUDA version represents driver compatibility.
`torch.version.cuda` records the runtime used by PyTorch.

The full system CUDA Toolkit was not required for this environment.
```

Only include statements verified during this task.

---

# STEP 19 — DO NOT CREATE FINAL DEPENDENCY FILES

Although this task installs:

```text
torch
sentence-transformers
```

and their transitive dependencies, do NOT yet create or freeze:

```text
requirements.txt
requirements-dev.txt
pyproject.toml dependency lists
environment.yml
```

That belongs to Task 0.4.

However, capture enough package-version information in `Progress.md` / `ENVIRONMENT.md` that Task 0.4 can reproduce the working GPU stack.

It is acceptable to record:

```bash
python -m pip list
```

for diagnostic purposes.

Do not commit a giant raw package dump unless there is a clear reason.

---

# STEP 20 — GIT SAFETY CHECK

Run:

```bash
git status --short
git status --ignored --short
git count-objects -vH
```

Verify:

```text
.venv remains ignored
model cache is not trackable
no model weights appear
no CUDA binaries appear
no large generated files appear
```

Check any newly created cache locations if needed.

Do NOT run:

```text
git add .
git commit
git push
git tag
```

---

# STEP 21 — UPDATE `Progress.md`

Preserve all existing history.

Append:

```markdown
## YYYY-MM-DD — Phase 0.2 CUDA / GPU Validation
```

using the current local date.

Include the following sections.

## Objective

Explain that this task formalized GPU support inside the project-local `.venv`, replacing the earlier ad hoc global-environment observation.

## Initial State

Record:

```text
Python 3.11.9
.venv working
PyTorch absent from .venv before task
previous global GPU observation only
```

## NVIDIA Environment

Record:

```text
GPU model
VRAM
driver version
driver-supported CUDA version
compute capability
```

## PyTorch Decision

Record:

```text
PyTorch version
selected CUDA build/runtime
reason
installation source/method
```

Explicitly distinguish:

```text
nvidia-smi CUDA
vs
torch.version.cuda
```

## CUDA Verification

Record:

```text
torch.cuda.is_available
device count
device name
compute capability
cuDNN version
real tensor kernel result
CPU/GPU numerical comparison
FP16 result
BF16 result
```

## Embedding Verification

Record:

```text
model: BAAI/bge-small-en-v1.5
device
embedding dimension
texts encoded
batch size
elapsed time
approximate throughput
peak VRAM
```

Label timing:

```text
smoke measurement only
```

## Files Created / Modified

Likely:

```text
project_plan/ENVIRONMENT.md
Progress.md
```

Possibly another small documentation file only if clearly necessary.

Do not list `.venv` internals.

## Packages Added Locally

Briefly record the important packages installed into `.venv`:

```text
torch
sentence-transformers
```

plus their relevant versions.

Do not paste the entire transitive dependency graph.

## Result

Use exactly one:

```text
PASS — CUDA and GPU embedding inference validated inside project .venv

WARN — GPU works but a non-blocking compatibility issue remains

BLOCKED — project-local CUDA/PyTorch environment is not reliable
```

## Phase Status

If PASS:

```text
Data Preparation              — COMPLETE
Phase 0                       — IN PROGRESS
  0.0 Git Safety Preflight    — COMPLETE
  0.1 Python Environment      — COMPLETE
  0.2 CUDA/GPU Validation     — COMPLETE
  0.3 Repository Structure    — NEXT
```

---

# ACCEPTANCE CRITERIA

Task 0.2 is complete only if:

```text
[ ] .venv Python 3.11.9 is active
[ ] NVIDIA GPU visible
[ ] driver version recorded
[ ] driver-supported CUDA version recorded
[ ] CUDA-enabled PyTorch installed in .venv
[ ] PyTorch version recorded
[ ] torch.version.cuda recorded
[ ] cuDNN version recorded
[ ] torch.cuda.is_available() == True
[ ] expected RTX 5060 GPU detected
[ ] compute capability recorded
[ ] actual CUDA tensor kernel executes
[ ] CPU/GPU numerical sanity check passes
[ ] FP16 behavior tested
[ ] BF16 behavior tested
[ ] GPU memory statistics recorded
[ ] sentence-transformers installed in .venv
[ ] BAAI/bge-small-en-v1.5 loads
[ ] model executes explicitly on CUDA
[ ] embedding shape validated
[ ] embeddings contain finite values
[ ] basic GPU throughput recorded
[ ] model cache does not enter Git
[ ] ENVIRONMENT.md updated
[ ] Progress.md updated
[ ] requirements files NOT created yet
[ ] CUDA Toolkit NOT installed unnecessarily
[ ] no Git commit created
[ ] no Git push performed
[ ] Phase 0.3 work NOT started
```

---

# STOP CONDITIONS

Stop instead of forcing success if:

```text
GPU not visible to nvidia-smi
PyTorch cannot detect CUDA
real CUDA kernel execution fails
PyTorch reports RTX 5060 / sm_120 unsupported
stable PyTorch build cannot execute on this GPU
sentence-transformers silently falls back to CPU
model inference produces CUDA/kernel errors
required fix would involve invasive driver/system modification
```

If the stable PyTorch build fails because of Blackwell support:

1. preserve the exact error,
2. identify the likely compatibility cause,
3. report the official supported options,
4. stop before replacing the environment with nightly/system-level changes unless explicitly authorized.

Do not hide a compatibility problem by falling back to CPU.

---

# IMPORTANT NON-GOALS

This task does NOT decide:

```text
final embedding model
final batch size
production embedding throughput
quantization
full-corpus embedding strategy
reranker
ONNX deployment
Lambda/Fargate
production CUDA tuning
```

`bge-small-en-v1.5` is being used here because it is the Phase 1 baseline and provides a convenient real GPU inference test.

Model selection happens later.

---

# FINAL RESPONSE TO ME

After completing the task, return:

## Task

```text
task_0.2_cuda_gpu_validation.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Hardware

Report:

```text
GPU
VRAM
compute capability
driver
driver-supported CUDA version
```

## PyTorch

Report:

```text
PyTorch version
torch.version.cuda
cuDNN version
CUDA available
```

## Kernel Validation

Report:

```text
real GPU operation: PASS/FAIL
CPU/GPU numerical sanity: PASS/FAIL
FP16: PASS/FAIL
BF16: PASS/FAIL/UNSUPPORTED
```

## Embedding Validation

Report:

```text
model
device
embedding dimension
batch size / sample size
approximate smoke throughput
peak VRAM
```

## Files Modified

List tracked/project files only.

## Git Safety

Confirm:

```text
.venv ignored
model cache not staged
no large binaries staged
```

## Progress.md

Confirm the Phase 0.2 entry was appended.

## Next Task

If PASS:

```text
task_0.3_repository_structure.md
```

Finally state explicitly:

```text
No Git commit created.
No Git push performed.
No Phase 0.3 work started.
```

Stop and wait for my approval.
# Development Environment

## Python

Selected version: **Python 3.11** (3.11.9 installed)

Reason: `PROJECT_EXECUTION.md` Task 0.1 prefers Python 3.12.x for broad
ML/data-library compatibility, falling back to 3.11.x if 3.12 is not
available. This machine's global interpreter is Python 3.14.3 (newest
available), which was deliberately **not** selected — the newest interpreter
maximizes reproducibility risk for a stack this dependent on prebuilt wheels
(PyTorch, sentence-transformers, LanceDB, ONNX Runtime, Docling), several of
which lag behind the newest CPython release for wheel availability. Only
Python 3.14 and Python 3.11 were available via the `py` launcher on this
machine (`py -0p`); 3.12 was not installed. Python 3.11.9 was already present
(`C:\...\AppData\Local\Programs\Python\Python311\python.exe`), so it was used
directly — no interpreter installation was necessary.

## Create the environment

### Windows PowerShell (tested on this machine)

```powershell
py -3.11 -m venv .venv
```

### bash/zsh (untested on this machine — standard equivalent)

```bash
python3.11 -m venv .venv
```

## Activate

### Windows PowerShell (tested)

```powershell
.\.venv\Scripts\Activate.ps1
```

### Windows CMD (untested — standard equivalent)

```cmd
.venv\Scripts\activate.bat
```

### bash/zsh (untested — standard equivalent)

```bash
source .venv/bin/activate
```

## Verify

```powershell
python --version
python -c "import sys; print(sys.executable)"
python -c "import sys; print(sys.prefix)"
python -m pip --version
```

Expected: `python --version` reports `Python 3.11.9`; `sys.executable` and
`sys.prefix` both resolve inside `<repo>\.venv\`; pip reports itself as
installed under `.venv\Lib\site-packages\pip`.

`.venv\pyvenv.cfg` should read `include-system-site-packages = false`.
Isolation was directly verified on this machine (not just the config flag):
`duckdb` — installed globally, not installed in `.venv` — fails to import
from inside the activated venv with `ModuleNotFoundError`.

After activation, a faster all-in-one check (Task 0.9):

```bash
python scripts/dev.py doctor
```

See `project_plan/DEVELOPER_COMMANDS.md`.

## Notes

Project dependencies were intentionally not installed in Task 0.1 — only
packaging tooling was bootstrapped (`pip`, `setuptools`, `wheel`, and their
`packaging` dependency), upgraded to their latest versions inside `.venv`.

CUDA/PyTorch validation was the global environment's observation only until
Task 0.2 (below) re-verified it inside `.venv` itself.

Full runtime/dev dependency installation (Task 0.4) is complete — see
`project_plan/DEPENDENCIES.md` for the three-file `pip install` sequence,
the direct-dependency table, and the fresh-environment reproducibility
verification. This file stays scoped to machine/Python/GPU setup;
`DEPENDENCIES.md` owns package management.

## GPU / CUDA

Tested hardware:
- GPU: NVIDIA GeForce RTX 5060 Laptop GPU
- VRAM: 8.55 GB (`torch`-reported); 8151 MiB (`nvidia-smi`-reported)
- Compute capability: (12, 0) — `sm_120` (Blackwell)

Driver:
- NVIDIA driver: 610.74 (WDDM)
- Driver-supported CUDA (`nvidia-smi` "CUDA UMD Version"): 13.3

PyTorch:
- Version: 2.13.0+cu130
- CUDA runtime (`torch.version.cuda`): 13.0
- cuDNN: 92000 (9.2.0)
- Install source: official PyTorch wheel index,
  `https://download.pytorch.org/whl/cu130`

Build selection reasoning: queried `pip index versions torch` against the
`cu128`, `cu129`, and `cu130` official indices rather than reusing whatever
the global environment happened to have. `cu128`'s newest was `2.11.0+cu128`
(one generation behind, though known-good from the pre-Phase-0 global-env
observation), `cu129`'s newest was a stale `2.9.0+cu129`, and `cu130`'s
newest was `2.13.0+cu130` — the current, actively-maintained channel, and
the closest match to this driver's reported CUDA 13.3 support. `sm_120`
appears directly in `torch.cuda.get_arch_list()` under `cu130` (compiled
kernels, not just PTX JIT fallback), which `cu128` could not confirm at
install time. `torchvision`/`torchaudio` were not installed — not required
for this workload (embeddings only).

Important: `nvidia-smi`'s "CUDA UMD Version" (13.3) is the *driver's*
maximum supported CUDA version, not the runtime PyTorch actually uses.
`torch.version.cuda` (13.0) is the runtime bundled with the installed wheel.
These were recorded separately, as required — they are not the same number
and should not be conflated. The full NVIDIA CUDA Toolkit (`nvcc`) was not
installed; the standard PyTorch wheel bundles the CUDA runtime libraries
needed for ordinary execution, and nothing in this project compiles custom
CUDA extensions.

Validation (all run inside the activated `.venv`, not the global environment):
- CUDA available: yes (`torch.cuda.is_available() == True`)
- Device detected: `NVIDIA GeForce RTX 5060 Laptop GPU`, 1 device
- Real CUDA tensor operation: pass — 2048×2048 matmul on `cuda:0`, finite
  result, transferred back to CPU successfully
- CPU/GPU numerical sanity check: pass — 512×512 matmul, fixed seed,
  `torch.allclose(atol=1e-3, rtol=1e-3)` true, max abs diff ≈ 4.6e-5
- FP16: pass — allocation + compute + finite result on `cuda`
- BF16: pass — allocation + compute + finite result on `cuda`
- Compatibility warnings: none observed (no "no kernel image available" /
  "not compatible" warnings from PyTorch)
- GPU memory baseline (informational, tiny smoke test only): a single
  2048×2048 matmul allocated/reserved ~83.9 MB
- `bge-small-en-v1.5` GPU inference: pass — loaded with
  `device="cuda"` explicitly, model parameters confirmed on `cuda:0`,
  embedding dimension 384 (verified, not assumed)
- No-CPU-fallback evidence (three independent signals): embeddings tensor
  reported `device=cuda:0`; peak GPU memory allocated rose to ~171.8 MB
  during encoding; computation completed via real CUDA tensors with no
  CPU-path exceptions

GPU embedding smoke benchmark (**NOT a production benchmark** — do not cite
as a system-performance number):
- 40 short SEC-style sentences, batch size 16, one warm-up batch excluded
  from timing
- elapsed: 0.061 s → **~652 texts/sec**
- peak GPU memory allocated during the timed run: 171.78 MB

Model cache: no `HF_HOME` / `HUGGINGFACE_HUB_CACHE` / `TRANSFORMERS_CACHE`
were set, so Hugging Face used its default user-level cache
(`~/.cache/huggingface/`) — outside the repository, not trackable by Git,
not committed.

Packages added to `.venv` for this task (exact versions, for Task 0.4 to
reproduce): `torch==2.13.0+cu130`, `sentence-transformers==6.0.0`,
`transformers==5.16.1`, `huggingface-hub==1.28.0`, `tokenizers==0.23.1`,
`numpy==2.4.6`, `safetensors==0.8.0` (plus each package's own transitive
dependencies, installed normally via pip — not enumerated here).

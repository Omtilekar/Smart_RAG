"""gpu smoke test: real CUDA kernel execution, not just device detection.
Skips if no CUDA-capable GPU is present (any GPU, not specifically this
machine's RTX 5060 - "if CUDA is available, real CUDA execution works").
If CUDA reports available but the kernel fails, that is a FAIL, not a
skip - a broken-but-detected GPU is exactly the case this test exists to
catch."""

import pytest
import torch


@pytest.mark.gpu
def test_cuda_matmul_kernel_executes():
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available on this machine")

    a = torch.randn(512, 512, device="cuda")
    b = torch.randn(512, 512, device="cuda")
    c = a @ b
    torch.cuda.synchronize()

    assert c.device.type == "cuda"
    assert torch.isfinite(c).all().item()

"""Task 4.11 - portable static checks over the deployment artifacts
(Dockerfile, .dockerignore, infra/terraform/*). No Docker daemon, no AWS
credentials, no network - pure text/content assertions, so these run in
`scripts/dev.py test --portable` on every machine, including a public
clone with none of the frozen data present.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_SECRET_PATTERNS = (
    "OPENROUTER_API_KEY=sk-",
    "AKIA",  # AWS access key id prefix
    "-----BEGIN",  # PEM-shaped private key/cert material
)

_DANGEROUS_WINDOWS_PATH_MARKERS = (
    "C:\\Om\\Codes\\RAG",
    "C:/Om/Codes/RAG",
    "C:\\Users\\",
)


def _read(relative_path: str) -> str:
    path = REPO_ROOT / relative_path
    assert path.is_file(), f"expected deployment artifact not found: {path}"
    return path.read_text(encoding="utf-8")


def test_dockerfile_has_no_secret_values():
    text = _read("Dockerfile")
    for pattern in _SECRET_PATTERNS:
        assert pattern not in text, f"Dockerfile contains a secret-shaped value: {pattern!r}"


def test_dockerfile_never_copies_env_file():
    text = _read("Dockerfile")
    assert "COPY .env" not in text
    assert "ADD .env" not in text


def test_dockerfile_targets_the_real_app_factory():
    text = _read("Dockerfile")
    assert "src.api.app:create_app" in text
    assert "--factory" in text


def test_dockerfile_never_uses_reload():
    text = _read("Dockerfile")
    entrypoint_line = next(line for line in text.splitlines() if line.startswith("ENTRYPOINT"))
    assert "--reload" not in entrypoint_line


def test_dockerfile_exposes_the_documented_port_only():
    text = _read("Dockerfile")
    assert "EXPOSE 8000" in text
    # No second EXPOSE line for a debug/admin port.
    assert text.count("EXPOSE") == 1


def test_dockerfile_runs_as_non_root():
    text = _read("Dockerfile")
    assert "USER appuser" in text


def test_dockerfile_pins_the_dev_index_identity_not_full_corpus():
    text = _read("Dockerfile")
    # The known Task 4.10 limitation (dense route -> dev index) must stay
    # visible in the container's own documentation, never silently implied
    # to be the 10,487,096-row full-corpus index.
    assert "162,357" in text
    assert "10,487,096" in text


def test_dockerignore_excludes_frozen_and_generated_data():
    text = _read(".dockerignore")
    for required in ("data/", "artifacts/", ".venv/", ".env", ".git/", "*.tfstate", ".terraform/"):
        assert required in text, f".dockerignore is missing required exclusion: {required!r}"


def test_requirements_cpu_never_pulls_cuda_wheels():
    text = _read("requirements-cpu.txt")
    assert "cu1" not in text.lower()  # no cuNNN CUDA wheel tag
    assert "download.pytorch.org/whl/cpu" in text


def test_terraform_files_have_no_hardcoded_secrets_or_account_ids():
    for relative in ("infra/terraform/main.tf", "infra/terraform/variables.tf"):
        text = _read(relative)
        for pattern in _SECRET_PATTERNS:
            assert pattern not in text, f"{relative} contains a secret-shaped value: {pattern!r}"
        # No literal 12-digit AWS account id embedded in an ARN-shaped string.
        import re
        assert not re.search(r"arn:aws:[a-z0-9-]+:[a-z0-9-]*:\d{12}:", text), (
            f"{relative} appears to embed a real AWS account id"
        )


def test_terraform_variables_have_no_invented_account_defaults():
    text = _read("infra/terraform/variables.tf")
    # Account-specific inputs must not have a default value - Terraform
    # should refuse to plan/apply until a real one is supplied.
    account_specific = ("vpc_id", "subnet_ids", "ecs_cluster_name", "container_image",
                         "openrouter_api_key_secret_arn", "task_execution_role_arn", "task_role_arn")
    blocks = text.split("variable \"")[1:]
    for block in blocks:
        name = block.split("\"", 1)[0]
        if name in account_specific:
            body = block.split("{", 1)[1].rsplit("}", 1)[0]
            assert "default" not in body, f"variable {name!r} must not have an invented default"


def test_no_dangerous_absolute_windows_paths_in_deployment_artifacts():
    for relative in ("Dockerfile", ".dockerignore", "infra/terraform/main.tf",
                      "infra/terraform/variables.tf", "requirements-cpu.txt"):
        text = _read(relative)
        for marker in _DANGEROUS_WINDOWS_PATH_MARKERS:
            assert marker not in text, f"{relative} embeds a local absolute Windows path: {marker!r}"


def test_deployment_artifacts_never_reference_protected_test():
    for relative in ("Dockerfile", ".dockerignore", "infra/terraform/main.tf",
                      "infra/terraform/variables.tf", "infra/terraform/README.md"):
        text = _read(relative).lower()
        assert "test_access" not in text
        assert "protected test" not in text or "never" in text or "not" in text

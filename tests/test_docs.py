import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def test_project_metadata_points_at_github_repository():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()

    assert "https://github.com/Jesssullivan/DarwinNicUtil" in pyproject
    assert 'Documentation = "https://jesssullivan.github.io/DarwinNicUtil"' in pyproject
    assert 'Changelog = "https://github.com/Jesssullivan/DarwinNicUtil/blob/main/CHANGELOG.md"' in pyproject
    assert 'Releases = "https://github.com/Jesssullivan/DarwinNicUtil/releases"' in pyproject
    assert 'FlakeHub = "https://flakehub.com/f/Jesssullivan/DarwinNicUtil"' in pyproject
    assert "gitlab.com/tinyland/projects/darwin-mgmt-nic-configurator" not in pyproject


def test_operator_docs_do_not_point_at_retired_gitlab_repository():
    docs = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "artifacts.md",
        REPO_ROOT / "docs" / "bastion.md",
        REPO_ROOT / "docs" / "cli.md",
        REPO_ROOT / "docs" / "development.md",
        REPO_ROOT / "docs" / "index.md",
        REPO_ROOT / "docs" / "project-spec.md",
        REPO_ROOT / "docs" / "quickstart.md",
        REPO_ROOT / "docs" / "llms.txt",
        REPO_ROOT / "mkdocs.yml",
    ]

    stale = [
        str(path.relative_to(REPO_ROOT))
        for path in docs
        if "gitlab.com/tinyland/projects/darwin-mgmt-nic-configurator" in path.read_text()
    ]

    assert stale == []


def test_clone_instructions_match_github_repo_directory():
    development = (REPO_ROOT / "docs" / "development.md").read_text()
    quickstart = (REPO_ROOT / "docs" / "quickstart.md").read_text()
    mkdocs = (REPO_ROOT / "mkdocs.yml").read_text()

    assert "git clone https://github.com/Jesssullivan/DarwinNicUtil.git\ncd DarwinNicUtil" in development
    assert "git clone https://github.com/Jesssullivan/DarwinNicUtil.git\n    cd DarwinNicUtil" in quickstart
    assert "repo_name: Jesssullivan/DarwinNicUtil" in mkdocs
    assert "cd darwin-mgmt-nic-configurator" not in development
    assert "cd darwin-mgmt-nic-configurator" not in quickstart
    assert "repo_name: tinyland/darwin-mgmt-nic-configurator" not in mkdocs


def test_agents_file_keeps_crs_policy_out_of_darwin_tool():
    agents = (REPO_ROOT / "AGENTS.md").read_text()

    assert "generic `darwin-nic` USB management NIC tool" in agents
    assert "Do not embed switch secrets" in agents
    assert "Use the `github` remote" in agents
    assert "crs309-main" not in agents
    assert "vault_mikrotik_password" not in agents


def test_agent_surface_documents_no_repo_local_mcp_config():
    agents = (REPO_ROOT / "AGENTS.md").read_text()
    llms = (REPO_ROOT / "docs" / "llms.txt").read_text()

    assert not (REPO_ROOT / ".mcp.json").exists()
    assert "does not ship a `.mcp.json` today" in agents
    assert "There is no repo-local `.mcp.json` at this time" in llms
    assert "sibling-repo control-plane details" in agents


def test_bastion_docs_keep_device_specific_policy_out_of_darwin_tool():
    bastion = (REPO_ROOT / "docs" / "bastion.md").read_text()
    llms = (REPO_ROOT / "docs" / "llms.txt").read_text()

    assert "tailnet -> bastion host -> USB OOB NIC -> managed network device" in bastion
    assert "darwin-nic configure --profile homelab --preserve-wifi" in bastion
    assert "Device-specific hostnames" in bastion
    assert "Device-specific topology" in llms
    assert "crs309-main" not in bastion
    assert "vault_mikrotik_password" not in bastion
    assert "crs309-main" not in llms
    assert "vault_mikrotik_password" not in llms


def test_public_docs_stay_generic_and_release_accurate():
    public_docs = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "artifacts.md",
        REPO_ROOT / "docs" / "cli.md",
        REPO_ROOT / "docs" / "development.md",
        REPO_ROOT / "docs" / "index.md",
        REPO_ROOT / "docs" / "project-spec.md",
        REPO_ROOT / "docs" / "quickstart.md",
        REPO_ROOT / "docs" / "superpowers" / "release-sprint-plan.md",
        REPO_ROOT / "examples" / "config.toml",
        REPO_ROOT / "nix" / "modules" / "home-manager.nix",
    ]
    combined = "\n".join(path.read_text() for path in public_docs)

    stale_or_too_specific = [
        "random networky",
        "yucky fruit",
        "os noes",
        "CRS309 Bastion",
        "tinyland darwin pkg artifactory",
        "Single Binary",
        "No Python environment required",
        "GitLab CI only",
        "76 passing tests",
        "21 percent",
        "CRS310 Secondary",
        "BiDi backhaul",
    ]

    for phrase in stale_or_too_specific:
        assert phrase not in combined


def test_artifacts_docs_match_current_release_policy():
    artifacts = (REPO_ROOT / "docs" / "artifacts.md").read_text()
    readme = (REPO_ROOT / "README.md").read_text()
    flakehub_workflow_path = REPO_ROOT / ".github" / "workflows" / "flakehub-publish.yml"

    assert "wheel/source distributions" in artifacts
    assert "Nix packages" in artifacts
    assert "Standalone binary" in artifacts
    assert "not validated yet" in artifacts
    assert "Standalone binaries are not supported release artifacts yet" in artifacts
    assert "just build-binary" in artifacts
    assert "signing/notarization policy" in artifacts
    assert "Homebrew | Deferred" in artifacts
    assert "no active DarwinNicUtil tap/formula path" in artifacts
    assert "DarwinNicUtil does not ship a Bazel or Bzlmod module today" in artifacts
    assert "does not show a downstream" in artifacts
    assert "`MODULE.bazel` or `BUILD.bazel` consumer" in artifacts
    assert "Do not introduce Bazel as a default local build" in artifacts
    assert "FlakeHub releases" in artifacts
    assert "https://flakehub.com/f/Jesssullivan/DarwinNicUtil/v2.1.0" in artifacts
    assert "current public" in artifacts
    assert "FlakeHub releases are `v2.1.0`" in artifacts
    assert "nix run github:Jesssullivan/DarwinNicUtil -- status" in artifacts
    assert "https://flakehub.com/f/Jesssullivan/DarwinNicUtil/v2.1.0" in readme
    assert "PyPI distribution for `darwin-mgmt-nic-configurator`" in readme
    assert "GitHub Release, PyPI, FlakeHub, and docs workflows" in readme

    if flakehub_workflow_path.exists():
        flakehub_workflow = flakehub_workflow_path.read_text()
        assert "DeterminateSystems/flakehub-push@main" in flakehub_workflow


def test_pypi_publish_surface_is_live_and_documented():
    artifacts = (REPO_ROOT / "docs" / "artifacts.md").read_text()
    release_workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text()
    readme = (REPO_ROOT / "README.md").read_text()
    quickstart = (REPO_ROOT / "docs" / "quickstart.md").read_text()

    assert "## PyPI" in artifacts
    assert "darwin-mgmt-nic-configurator" in artifacts
    assert "PyPI publication is live" in artifacts
    assert "uv tool install darwin-mgmt-nic-configurator" in artifacts
    assert "latest validated upload is `2.1.1`" in artifacts
    assert "The completed cutover path was" in artifacts
    assert "Verify the GitHub repository environment is named `pypi`" in artifacts
    assert "Do not move or reuse the existing `v2.1.0` tag" in artifacts
    assert "predates the PyPI publishing job" in artifacts
    assert "curl -fsS https://pypi.org/pypi/darwin-mgmt-nic-configurator/json" in artifacts
    assert "release.yml" in artifacts
    assert "`pypi`" in artifacts
    assert "pypa/gh-action-pypi-publish@release/v1" in release_workflow
    assert "id-token: write" in release_workflow
    assert "environment:" in release_workflow
    assert "name: pypi" in release_workflow
    assert "username:" not in release_workflow
    assert "password:" not in release_workflow
    assert "uv tool install darwin-mgmt-nic-configurator" in readme
    assert "uv tool install darwin-mgmt-nic-configurator" in quickstart
    assert "PyPI trusted-publishing workflow is staged" not in readme
    assert "until the first upload is validated" not in readme
    assert "install docs remain pending" not in artifacts


def test_coverage_gate_is_ratchet_to_fifty_percent():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()
    development = (REPO_ROOT / "docs" / "development.md").read_text()
    release_plan = (REPO_ROOT / "docs" / "superpowers" / "release-sprint-plan.md").read_text()

    assert "fail_under = 50" in pyproject
    assert "current coverage gate is 50 percent" in development
    assert "configured 50 percent gate" in release_plan
    assert "configured 40 percent gate" not in release_plan


def test_project_spec_is_public_and_generic():
    readme = (REPO_ROOT / "README.md").read_text()
    index = (REPO_ROOT / "docs" / "index.md").read_text()
    mkdocs = (REPO_ROOT / "mkdocs.yml").read_text()
    llms = (REPO_ROOT / "docs" / "llms.txt").read_text()
    spec = (REPO_ROOT / "docs" / "project-spec.md").read_text()

    assert "[`docs/project-spec.md`](docs/project-spec.md)" in readme
    assert "[project spec](project-spec.md)" in index
    assert "Project Spec: project-spec.md" in mkdocs
    assert "docs/project-spec.md" in llms
    assert "Productionization Results" in spec
    assert "PyPI trusted publishing and validated `2.1.1` upload" in spec
    assert "Coverage gate ratcheted to 50 percent" in spec
    assert "Consumers own their own device names, secrets, and recovery policy" in spec
    assert "Boundary Decisions" in spec
    assert "ABR-style approval keepalives and scripted approvers are out of scope" in spec
    assert "Sophos, ZTNA, CryptoGuard" in spec
    assert "should not ship adversarial compliance modules" in spec

    forbidden = [
        "crs309-main",
        "vault_mikrotik_password",
        "sops-nix/secrets",
        "100.111.",
        "100.124.",
    ]
    for phrase in forbidden:
        assert phrase not in spec


def test_root_entrypoint_uses_package_app_version():
    script = (REPO_ROOT / "darwin-nic").read_text()
    backend_cli = (REPO_ROOT / "src" / "darwin_mgmt_nic" / "cli.py").read_text()

    assert "darwin_mgmt_nic.app" in script
    assert "2.0.0" not in script
    assert "USB NIC Configurator 2.0.0" not in backend_cli

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "darwin-nic"), "--version"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "darwin-nic 2.1.1"


def test_binary_build_script_is_local_smoke_test_only():
    build_script = (REPO_ROOT / "scripts" / "build.sh").read_text()

    assert "uv run --with pyinstaller --with setuptools pyinstaller" in build_script
    assert "shasum -a 256 dist/darwin-nic" in build_script
    assert "local smoke-test artifact" in build_script
    assert "pip install -r build-requirements.txt" not in build_script


def test_example_profile_networks_are_internally_consistent():
    example = (REPO_ROOT / "examples" / "config.toml").read_text()

    assert 'device_ip = "192.168.88.1"' in example
    assert 'laptop_ip = "192.168.88.100"' in example
    assert 'mgmt_network = "192.168.88.0/24"' in example
    assert 'mgmt_network = "192.168.10.0/24"' not in example

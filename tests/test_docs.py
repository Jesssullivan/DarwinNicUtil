from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def test_project_metadata_points_at_github_repository():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()

    assert "https://github.com/Jesssullivan/DarwinNicUtil" in pyproject
    assert "gitlab.com/tinyland/projects/darwin-mgmt-nic-configurator" not in pyproject


def test_operator_docs_do_not_point_at_retired_gitlab_repository():
    docs = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "artifacts.md",
        REPO_ROOT / "docs" / "bastion.md",
        REPO_ROOT / "docs" / "cli.md",
        REPO_ROOT / "docs" / "development.md",
        REPO_ROOT / "docs" / "index.md",
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
    assert "Homebrew | Deferred" in artifacts
    assert "no active DarwinNicUtil tap/formula path" in artifacts
    assert "FlakeHub | Publish workflow is staged" in artifacts
    assert "Do not add FlakeHub" in artifacts
    assert "install instructions to the README" in artifacts
    assert "nix run github:Jesssullivan/DarwinNicUtil -- status" in artifacts
    assert "flakehub.com/f/" not in readme.lower()
    assert "PyPI publishing and standalone binary distribution remain tracked release" in readme

    if flakehub_workflow_path.exists():
        flakehub_workflow = flakehub_workflow_path.read_text()
        assert "DeterminateSystems/flakehub-push@main" in flakehub_workflow


def test_example_profile_networks_are_internally_consistent():
    example = (REPO_ROOT / "examples" / "config.toml").read_text()

    assert 'device_ip = "192.168.88.1"' in example
    assert 'laptop_ip = "192.168.88.100"' in example
    assert 'mgmt_network = "192.168.88.0/24"' in example
    assert 'mgmt_network = "192.168.10.0/24"' not in example

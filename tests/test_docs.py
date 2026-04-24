from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent


def test_project_metadata_points_at_github_repository():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()

    assert "https://github.com/Jesssullivan/DarwinNicUtil" in pyproject
    assert "gitlab.com/tinyland/projects/darwin-mgmt-nic-configurator" not in pyproject


def test_operator_docs_do_not_point_at_retired_gitlab_repository():
    docs = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "development.md",
        REPO_ROOT / "docs" / "quickstart.md",
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

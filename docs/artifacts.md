# Artifacts

This project currently treats wheel/source distributions, Nix packages,
FlakeHub releases, and the MkDocs site as release artifacts.

## Python Packages

Build locally with:

```bash
uv build
```

Expected outputs:

```text
dist/darwin_mgmt_nic_configurator-*.whl
dist/darwin_mgmt_nic_configurator-*.tar.gz
```

Smoke-test a built wheel before publishing:

```bash
uv venv --python 3.14 .release-venv
uv pip install --python .release-venv dist/*.whl
.release-venv/bin/darwin-nic --version
.release-venv/bin/darwin-nic --help
rm -rf .release-venv
```

## Nix Packages

Build the default CLI package:

```bash
nix build .#darwin-nic -L
```

The optional network-tools bundle is separate:

```bash
nix build .#net-utils -L
```

Downstream Home Manager users should consume the flake input and install
`packages.${system}.darwin-nic`.

The stable FlakeHub release reference is:

```bash
nix run "https://flakehub.com/f/Jesssullivan/DarwinNicUtil/v2.1.0" -- status
```

The direct GitHub flake reference remains supported:

```bash
nix run github:Jesssullivan/DarwinNicUtil -- status
```

FlakeHub publication runs through the `Publish to FlakeHub` GitHub Actions
workflow. Tagged releases publish from `v*.*.*` tags, and maintainers can run a
manual rolling validation from the workflow dispatch form. The current public
FlakeHub releases are `v2.1.0` and the rolling `*` channel.

## Documentation Site

Build locally with:

```bash
uv run --extra dev mkdocs build --strict
```

The GitHub Pages workflow builds the same MkDocs site and publishes it as a
Pages artifact.

## GitHub Release

The release workflow runs on tags matching `v*.*.*`. It builds the Python
distribution files and attaches only the wheel and source distribution to the
GitHub Release.

## PyPI Trusted Publishing

PyPI publication is staged in the release workflow, but it is not a supported
install path until the first trusted-publishing upload succeeds.

The package name planned for PyPI is `darwin-mgmt-nic-configurator`. Configure
a PyPI pending publisher before pushing the first PyPI-enabled release tag:

| Field | Value |
|-------|-------|
| Owner | `Jesssullivan` |
| Repository | `DarwinNicUtil` |
| Workflow | `release.yml` |
| Environment | `pypi` |

The release workflow uses GitHub OIDC with `pypa/gh-action-pypi-publish` and
does not use a stored PyPI API token. Keep README and quickstart install
commands focused on Nix, FlakeHub, wheel/source, and source checkout paths
until a real PyPI upload is validated.

## Not Yet Primary Artifacts

| Surface | Current status |
|---------|----------------|
| PyPI | Trusted-publishing workflow is staged; install docs remain pending until first upload is validated, tracked in [GitHub #11](https://github.com/Jesssullivan/DarwinNicUtil/issues/11) |
| Standalone binary | PyInstaller spec exists, but binary releases are not validated yet; tracked in [GitHub #9](https://github.com/Jesssullivan/DarwinNicUtil/issues/9) |
| Homebrew | Deferred; there is no active DarwinNicUtil tap/formula path until PyPI or standalone artifacts are proven, with the decision recorded in [GitHub #10](https://github.com/Jesssullivan/DarwinNicUtil/issues/10) |
| Bazel / BCR | Not a primary install path; evaluate only if a real downstream Bazel/Bzlmod consumer needs it, tracked in [GitHub #17](https://github.com/Jesssullivan/DarwinNicUtil/issues/17) |
| Container image | Not applicable for the CLI today |

## Bazel / BCR Decision

DarwinNicUtil does not ship a Bazel or Bzlmod module today. The validated
distribution paths are Python wheel/source distributions, GitHub Releases, Nix
flake references, and FlakeHub releases.

Do not introduce Bazel as a default local build, test, or install path for this
repo. Current repo and sibling-repo evidence does not show a downstream
`MODULE.bazel` or `BUILD.bazel` consumer for DarwinNicUtil.

If a real downstream Bazel consumer appears, keep the surface minimal:

- add only the `MODULE.bazel` metadata and targets needed by that consumer;
- prefer consuming an existing wheel, source distribution, or FlakeHub/GitHub
  source archive over recreating the primary packaging pipeline in Bazel;
- align any BCR work with Tinyland's existing cache-backed conventions;
- keep README and quickstart docs focused on uv, wheel/source, Nix, and
  FlakeHub unless the Bazel path becomes a validated public artifact.

Bazel/BCR work should stay aligned with the broader Tinyland distribution
substrate. Homebrew should be reconsidered only after a supported PyPI or
standalone artifact exists. This repo should only document public, validated
install paths.

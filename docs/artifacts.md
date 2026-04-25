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

## Not Yet Primary Artifacts

| Surface | Current status |
|---------|----------------|
| PyPI | Planned through trusted publishing; tracked in [GitHub #11](https://github.com/Jesssullivan/DarwinNicUtil/issues/11) |
| Standalone binary | PyInstaller spec exists, but binary releases are not validated yet; tracked in [GitHub #9](https://github.com/Jesssullivan/DarwinNicUtil/issues/9) |
| Homebrew | Deferred; there is no active DarwinNicUtil tap/formula path until PyPI or standalone artifacts are proven, with the decision recorded in [GitHub #10](https://github.com/Jesssullivan/DarwinNicUtil/issues/10) |
| Bazel / BCR | Not a primary install path; evaluate only if a real downstream Bazel/Bzlmod consumer needs it, tracked in [GitHub #17](https://github.com/Jesssullivan/DarwinNicUtil/issues/17) |
| Container image | Not applicable for the CLI today |

Bazel/BCR work should stay aligned with the broader Tinyland distribution
substrate. Homebrew should be reconsidered only after a supported PyPI or
standalone artifact exists. This repo should only document public, validated
install paths.

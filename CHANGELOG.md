# Changelog

All notable changes to DarwinNicUtil are recorded here.

## Unreleased

- No unreleased changes.

## 2.1.2 - 2026-04-25

- Fix the MkDocs deployment workflow so GitHub Pages can be enabled and
  deployed from Actions.
- Point docs metadata at the canonical public docs URL.
- Tighten README and MkDocs install/download tables for PyPI, FlakeHub,
  GitHub Releases, source checkout, and integration surfaces.
- Refresh public install and artifact docs around the validated `v2.1.2` PyPI
  and FlakeHub release surfaces.
- Move PyPI out of the deferred artifact policy after the trusted-publishing
  upload succeeded.

## 2.1.1 - 2026-04-25

- Stage the post-v2.1.0 PyPI cutover release.
- Add PyPI project metadata links for documentation, changelog, releases, and
  FlakeHub.
- Document the PyPI trusted-publishing cutover checklist.
- Keep PyPI install commands out of README and quickstart until the first
  upload is validated.

## 2.1.0 - 2026-04-25

- Restrict future release workflow uploads to wheel and source distribution
  artifacts only.
- Clarify release artifact docs so they describe only wheel and source
  distribution uploads.
- Track post-v2.1 distribution follow-ups for PyPI, standalone binaries,
  Homebrew, FlakeHub, and Bazel/BCR without advertising unproven install paths.
- Mark Homebrew as deferred until a supported PyPI or standalone artifact exists.

### CI/CD

- Add GitHub Actions CI, docs deployment, secret scanning, and release workflow scaffolding.
- Add repo-local gitleaks configuration.
- Add git-cliff changelog configuration.

### Documentation

- Add a release sprint plan for the v2.1.0 readiness push.
- Include the release sprint plan in the MkDocs navigation.
- Refresh the quickstart around current Nix, uv, and source-based startup flows.
- Add a generic bastion/OOB operator guide and `llms.txt` repo summary.
- Add artifact policy documentation for wheel/source distributions, Nix packages, MkDocs, and non-primary binary/PyPI surfaces.
- Tighten README and MkDocs wording for accuracy, brevity, and generic repository boundaries.
- Correct stale architecture references to removed or nonexistent entry points.
- Scope Sophos and ABR feature ideas as deferred spikes outside the v2.1.0 release readiness lane.

### Testing

- Add focused settings tests for TOML schema serialization, merge precedence, env overrides, profile selection, malformed config handling, and `init-config`.
- Add app-level command tests for status, dashboard, test, restore, config display, profile listing, init-config, and main subcommand dispatch.
- Add CLI backend tests for parser defaults, config/profile display, profile-driven configuration, platform failure, VPN repair, and error return paths.
- Add Linux placeholder and network-manager tests covering carrier status, ping handling, service-order parsing, Wi-Fi metrics, interface scoring, route helpers, and interference heuristics.
- Add an initial 40% coverage gate.

### Fixed

- Ensure app-level `configure` propagates backend exit codes.
- Keep dry-run mode from applying Wi-Fi service-order preservation before interface validation.

### Maintenance

- Add MkDocs packages to the development dependency extra so docs commands run through `uv run --extra dev`.
- Update the Nix package homepage from the retired GitLab URL to the GitHub repository.

## 2.0.0 - 2026-01-16

### Features

- Initial Darwin USB management NIC configurator release.

### Subsequent Changes Since v2.0.0

- Added Nix flake packaging, a Just task surface, and Home Manager / System Manager modules.
- Updated README guidance for Just, Nix packaging, and Linux support.
- Added bastion diagnostics for USB OOB, `scutil --nwi`, Tailscale system extension state, and macOS NECP drops.

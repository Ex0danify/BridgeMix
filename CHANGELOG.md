# Changelog

All notable changes to BridgeMix are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Add entries under **[Unreleased]** as you work, grouped under the headings
below (drop any you don't need). The release workflow moves this section under a
versioned heading, dates it, and starts a fresh empty **[Unreleased]** — so this
file always stays in lockstep with the published releases.

## [Unreleased]

### Added

- Plugin SDK and documentation (`doc/PLUGINS.md`): the Extras tab is now a
  plugin host with discovery, enable toggles, and dependency installation.
- In-app update check: the About dialog (footer ⓘ button) reports whether a
  newer release is available and links to the download, and the button is
  tinted when an update exists. Dependency-free (no git required) and cached
  for a day so it checks at most once daily.
- Optional manual release pipeline (`.github/workflows/release.yml`) that bumps
  the version, tags it, and publishes a GitHub Release with notes taken from
  this changelog.

### Changed

- Moved the REST API into a built-in plugin, along with its tests.

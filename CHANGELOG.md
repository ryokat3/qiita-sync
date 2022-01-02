<!--
# Change Log

Tags:

- Added          for new features.
- Changed        for changes in existing functionality.
- Deprecated     for soon-to-be removed features.
- Fixed          for any bug fixes.
- Security       in case of vulnerabilities.


Policy:

- Keep an Unreleased section at the top to track upcoming changes.
- YYYY-MM-DD for date format


# Semantic Versioning

- MAJOR version     when you make incompatible API changes,
- MINOR version     when you add functionality in a backwards compatible manner, and
- PATCH version     when you make backwards compatible bug fixes.

-->

# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased]

### Added

- Added "workflow_dispatch" event tigger for github actions
- Added "[tool.poetry.scripts]" to pyproject.toml

### Changed

- Changed Python version to 3.6 and 3.10.1 in GitHub Actions
- Changed project information in pyproject.toml
- Changed .gitignore to exlucde dist directory
- Removed \_\_version_\_ from \_\_init_\_.py 

### Fixed

- Fixed get double-underscores to display in CHANGELOG.md

## 1.0.0 - 2021-12-31

### Added

- qiita_sync/qiita_sync.py
- qiita_sync/\_\_init_\_.py
- tests/test_qiita_sync.py
- tests/\_\_init_\_.py
- github_actions/qiita_sync.yml
- github_actions/qiita_sync_check.yml
- README.md
- CHANGELOG.md
- LICENSE
- poetry.lock
- pyproject.toml
- .github/workflows/pytest.yml
- .gitignore
- .vscode/settings.json

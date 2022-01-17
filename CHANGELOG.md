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

## 1.3.3 - 2022-01-16

### Changed

- README

## 1.3.2 - 2022-01-16

### Added

- Added command line tests
- Added PyPI badge
- Added multiple pages to download (for many articles)
- Added handling for http status 404 when aritcle is not found
- Added logic to find if running on github actions or local (replaced timestamp arguments)
- Added SyncStatus class
- Added sub functions used when checking the diff
- Added qsync_foreach, qsync_do_sync, qsync_do_check, qsync_do_purge
- Added purge sub command (for test purpose)
- Added test cases

### Changed

- Changed the logic to get timestamp (git on github actions, file mtime on local)
- Removed handling for http status 429 (Too much request)
- Removed old comand handler functions

### Fixed

- Fixed CHANGELOG.md

## 1.2.0 - 2022-01-11

### Added

- Added to show timestamps when checking the diffs
- Added test cases

### Changed

- Changed the command line option from git-timestamp to file-timestamp

### Fixed

- Fixed the way to get branch name changed in 1.1.1 
- Fixed the default timestamp from file-timestamp to git-timestamp

## 1.1.1 - 2022-01-10

### Added

- Added test cases

### Changed

- Changed pytest command options in pytest.yml
- Changed the way to get branch name when HEAD is detached
- Changed the branch name from develop to dev

## 1.1.0 - 2022-01-09

### Added

- Added "workflow_dispatch" event tigger for github actions
- Added "[tool.poetry.scripts]" to pyproject.toml
- Added code coverage to github actions
- Added CODECOV_TOKEN to github repository
- Added coverage badge in README.md
- Added various badge from shields.io in README.md
- Added doc/command_usage.md
- Added some PNG files under img directory

### Changed

- Changed to use pip when installing qiita-sync in GitHub Actions
- Changed Python version to 3.7 and 3.10.1 in GitHub Actions
- Changed project information in pyproject.toml
- Changed .gitignore to exlucde dist directory
- Removed \_\_version_\_ from \_\_init_\_.py 
- Changed QiitaArticle.fromFile not to return dict even if title is not defined
- Changed the setup of markdown test files to be smarter
- Changed strtobool to be removed because it wll be deprecated in python 3.12

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

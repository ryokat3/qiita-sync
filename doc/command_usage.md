# Qiita-Sync Command Usage

![pytest](https://github.com/ryokat3/Qiita-Sync/actions/workflows/pytest.yml/badge.svg)
![GitHub Workflow Status (branch)](https://img.shields.io/github/workflow/status/ryokat3/Qiita-Sync/Python%20Test/main)
![Codecov branch](https://img.shields.io/codecov/c/github/ryokat3/Qiita-Sync/main)
![GitHub](https://img.shields.io/github/license/ryokat3/Qiita-Sync)

Qiita-Sync is a python command line tool that can synchronize your local markdown files with Qiita articles.

# Requirement

- Qiita Account
- GitHub repository
- Python (v3.7 or higher)
- Qiita-Sync

# Installation

## Qiita Access Token

1. Generate your access token

   1. Open [Qiita Account Applications](https://qiita.com/settings/applications)
   2. Click "Generate new token"
   3. Copy the access token displayed.

2. Make your access token available as environment variable QIITA_ACCESS_TOKEN

   Your access token must be availble as environment varialbe **QIITA_ACCESS_TOKEN** whenever
   you execute Qiita-Sync. You need to make the access token secret, not to make it available in public.

3. Check if your access token is valid
 
   Your qiita account information will be displayed with the command below.

   ```bash
   curl -sH "Authorization: Bearer $(echo ${QIITA_ACCESS_TOKEN})" https://qiita.com/api/v2/authenticated_user | python -m json.tool
   ```

## Install Qiita-Sync

1. Check the python version

   Check if the Python version is 3.7 or higher with the command below

   ```bash
   python --version
   ```

2. Install Qiita-Sync

   ```bash
   pip install qiita-sync
   ```

3. Check if Qiita-Sync is successfully installed

   ```bash
   qiita_sync --help
   ```

## Download articles

Change the directory to your git repository, and execute the command below to download your Qiita articles.

```bash
qiita_sync sync .
```

# Usage

## Synchronize all articles

Synchronize all articles after wrting new articles and/or updating existing articles.

```bash
qiita_sync sync <git-directory-path>
```

## Upload an article

Upload a newly created article or updated article to Qiita site

```bash
qiita_sync upload <updated-file>
```

## Download an article

Update an article that was updated by Qiita Web Application (So, not locally updated yet)

```bash
qiita_sync download <not-updated-file>
```

## Check differences

Check the difference between Qiita site and local files

```bash
qiita_sync check <git-directory-path>
```

## Delete an article from Qiita

Remove an article from Qiita site (not remove from git repository)

```bash
qiita_sync delete <deleting-file>
```

# Note

- Supported Python version is 3.7 or higher because "future feature annotations is not defined" as of 3.6

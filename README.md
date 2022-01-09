# Qiita-Sync

![pytest](https://github.com/ryokat3/Qiita-Sync/actions/workflows/pytest.yml/badge.svg)
![GitHub Workflow Status (branch)](https://img.shields.io/github/workflow/status/ryokat3/Qiita-Sync/Python%20Test/main)
![Codecov branch](https://img.shields.io/codecov/c/github/ryokat3/Qiita-Sync/main)
![GitHub](https://img.shields.io/github/license/ryokat3/Qiita-Sync)

Qiita-Sync is a GitHub Actions that can synchronize your markdown files in GitHub repository with Qiita articles.

It can be also used as a command line tool.
See more details [Qiita-Sync Command Usage](https://github.com/ryokat3/qiita-sync/blob/main/doc/command_usage.md) for command usage.

# Installation

## Qiita Access Token

1. Generate your access token

   1. Open [Qiita Account Applications](https://qiita.com/settings/applications)
   2. Click "Generate new token"
   3. Copy the access token displayed.

2. Save the access token to GitHub

   1. Open your GitHub repository
   2. Go "Settings" >> "Secrets"
   3. Click "New repository secrets"
   4. Save the access token with the name QIITA_ACCESS_TOKEN

## GitHub Actions

1. Download 2 YAML files of GitHub Actions

   - [qiita_sync.yml](https://raw.githubusercontent.com/ryokat3/qiita-sync/main/github_actions/qiita_sync.yml)
   - [qiita_sync_check.yml](https://raw.githubusercontent.com/ryokat3/qiita-sync/main/github_actions/qiita_sync_check.yml)

2. Save them in your repository as:

   - `.github/workflow/qiita_sync.yml`
   - `.github/workflow/qiita_sync_check.yml`

   **NOTE**: Change the cron time `cron: "29 17 * * *"` of `qiita_sync_check.yml` which is the time when this action is sheduled to be executed.
             `29 17 * * *` indicates that this action is executed every day at 17:29 UTC, which is kind of inactive time for me who is living in Japan.
             Please adjust it to your convenience.

3. Push them to GitHub

## Badge

You can add the link to badge below in your README file to show if it is successfully synchronized or not.
Please replaece `<Your-ID>` and `<Your-Respository>` as your own.

```markdown
![Qiita Sync](https://github.com/<Your-ID>/<Your-Repository>/actions/workflows/qiita_sync_check.yml/badge.svg)
```

Then, the badge will be displayed in your README file.

- synchronized badge:

  ![Passing Badge](https://raw.githubusercontent.com/ryokat3/qiita-sync/main/img/qiita_sync_badge_passing.png)

- unsynchronized badge:

  ![Failing Badge](https://raw.githubusercontent.com/ryokat3/qiita-sync/main/img/qiita_sync_badge_failing.png)

# Synchronization

When you find the failure of synchronization with the badge in README or e-mail notification from GitHub,
you can manually invoke Qiita-Sync GitHub Actions to synchronize them.

1. Open your GitHub repository
2. Go "Actions" >> "Qiita Sync" (in left pane)
3. Click "Run workflow" (in right pane)

# Writing Articles

Please note some features of Qiita-Sync when writing articles.

## File Name

When downloading Qiita articles at first, their file names are like `a5b5328c93bad615c5b2.md` whose naming convention is "\<Qiita-Article-ID\>.md".
However you can rename those files as you like and can move to any subdirectories within the git repository directory.

## Article Header

Each downloaded articles has a header. This header is automatically generated when downloaded from Qiita site.
And, it is automatically removed when uploaded to Qiita site.

You can cange `title` and `tags` as you like. However **you must not remove `id`**.
It's a key information for synchronization with Qiita site.

```markdown
<!--
title: This header is automatically generated by Qiita-Sync when downloading Qiita articles
tags:  Qiita-Sync
id:    a5b5328c93bad615c5b2
-->
```

But, you don't need `id` in the header when you create new articles.

```markdown
<!--
title: No id is necessary in the header when writing new articles
tags:  Qiita-Sync
-->
```

The `id` will be automatically added to the header after uploaded to Qiita site.

## Links to Qiita article

You can write a link to another your Qiita article as a relative file path like below.

```markdown
<!-- An example of link to another Qiita article when writing -->
[My Article](../my-article.md)
```

This link will be automatically changed to the URL when uploaded to Qiita site.

```markdown
<!-- An example of link to another Qiita article when published to Qiita site -->
[My Article](https://qiita.com/ryokat3/items/a5b5328c93bad615c5b2)
```

And, it will be automatically changed to the relative file path when downloaded from Qiita site.

## Links to image file

You can write a link to an image file as a relative file path like below.

```markdown
<!-- An example of link to image file 'earth.png' when writing-->
![My Image](../image/earth.png)
```

This link will be automatically changed to the URL when uploaded to Qiita site.

```markdown
<!-- An example of link to image file 'earth.png' when published to Qiita site -->
![My Image](https://raw.githubusercontent.com/ryokat3/qiita-articles/main/image/earth.png)
```

And, it will be automatically changed to the relative file path when downloaded from Qiita site.
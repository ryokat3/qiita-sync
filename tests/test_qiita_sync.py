import random
import string
import pytest
from pathlib import Path
from typing import Generator, List

from qiita_sync.qiita_sync import QiitaArticle
from qiita_sync.qiita_sync import DEFAULT_ACCESS_TOKEN_FILE, DEFAULT_INCLUDE_GLOB, DEFAULT_EXCLUDE_GLOB
from qiita_sync.qiita_sync import qsync_init, qsync_argparse
from qiita_sync.qiita_sync import markdown_code_block_split, markdown_code_inline_split, markdown_replace_text
from qiita_sync.qiita_sync import markdown_replace_link, markdown_replace_image

from pytest_mock.plugin import MockerFixture

########################################################################
# Test Utils
########################################################################


def markdown_find_line(text: str, keyword: str) -> List[str]:
    return [line[len(keyword):].strip() for line in text.splitlines() if line.startswith(keyword)]


def generate_random_name(length: int) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def generate_file_fixture(content: str, filename: str):

    @pytest.fixture
    def _() -> Generator[str, None, None]:
        filepath = Path(filename)

        try:
            filepath.write_text(content)
            yield str(filename)
        finally:
            filepath.unlink()

    return _


########################################################################
# Test Data
########################################################################

TEST_QIITA_ID = "qiita-id"
TEST_GITHUB_ID = "github-id"
TEST_GITHUB_REPO = "github-repo"
TEST_GITHUB_BRANCH = "master"

TEST_GITHUB_SSH_URL = f"git@github.com:{TEST_GITHUB_ID}/{TEST_GITHUB_REPO}.git"

markdown_1 = """
# section

LinkTest1: [dlink](markdown_2.md)
LinkTest2: [dlink](https://example.com/markdown/markdown_2.md)

`````shell
Short sequence of backticks
```
#LinkTest   [LinkTest](LintTest.md)
#ImageTest ![ImageTest](image/ImageTest.png)
`````

## sub-section

ImageTest1: ![ImageTest](img/ImageTest.png)
ImageTest2: ![ImageTest](img/ImageTest.png description)
ImageTest3: ![ImageTest](http://example.com/img/ImageTest.png img/ImageTest.png)

"""

TEST_ARTICLE_ID1 = "1234567890ABCDEFG"

markdown_2 = f"""
<!--
title: test
tags:  test
id:    {TEST_ARTICLE_ID1}
-->

# test
"""

markdown_3 = f"""
# section

LinkTest1: [dlink](https://qiita.com/{TEST_QIITA_ID}/items/{TEST_ARTICLE_ID1})
LinkTest2: [dlink](https://example.com/markdown/markdown_2.md)

`````shell
Short sequence of backticks
```
#LinkTest   [LinkTest](LintTest.md)
#ImageTest ![ImageTest](image/ImageTest.png)
`````

## sub-section

ImageTest1: ![ImageTest](https://raw.githubusercontent.com/{TEST_GITHUB_ID}/{TEST_GITHUB_REPO}/{TEST_GITHUB_BRANCH}/img/ImageTest.png)
ImageTest2: ![ImageTest](HTTPS://raw.githubusercontent.com/{TEST_GITHUB_ID}/{TEST_GITHUB_REPO}/{TEST_GITHUB_BRANCH}/img/ImageTest.png description)
ImageTest3: ![ImageTest](http://example.com/img/ImageTest.png img/ImageTest.png)
"""

markdown_4 = """
<!--
private: true
-->

LinkTest1: [dlink](markdown_2.md)

ImageTest1: ![ImageTest](img/ImageTest.png)

"""

markdown_1_fixture = generate_file_fixture(markdown_1, "markdown_1.md")
markdown_2_fixture = generate_file_fixture(markdown_2, "markdown_2.md")
markdown_3_fixture = generate_file_fixture(markdown_3, "markdown_3.md")
markdown_4_fixture = generate_file_fixture(markdown_3, "markdown_4.md")

QSYNC_MODULE_PATH = "qiita_sync.qiita_sync."


def setup_mocker(mocker: MockerFixture):
    mocker.patch(f'{QSYNC_MODULE_PATH}qiita_get_authenticated_user_id', return_value=TEST_QIITA_ID)
    mocker.patch(f'{QSYNC_MODULE_PATH}git_get_remote_url', return_value=TEST_GITHUB_SSH_URL)
    mocker.patch(f'{QSYNC_MODULE_PATH}git_get_default_branch', return_value=TEST_GITHUB_BRANCH)


########################################################################
# CLI Test
########################################################################


def test_qsync_argparse():
    args = qsync_argparse().parse_args("download .".split())

    assert args.target == "."
    assert args.include == DEFAULT_INCLUDE_GLOB
    assert args.exclude == DEFAULT_EXCLUDE_GLOB
    assert args.token == DEFAULT_ACCESS_TOKEN_FILE


def test_QiitaSync_instance(mocker: MockerFixture):

    setup_mocker(mocker)

    args = qsync_argparse().parse_args("download .".split())
    qsync = qsync_init(args)

    assert qsync.qiita_id == TEST_QIITA_ID
    assert qsync.git_user == TEST_GITHUB_ID
    assert qsync.git_repository == TEST_GITHUB_REPO
    assert qsync.git_branch == TEST_GITHUB_BRANCH


########################################################################
# Git Test
########################################################################

########################################################################
# Markdown Parser Test
########################################################################


def test_QiitaArticle_fromFile(markdown_1_fixture):
    doc = QiitaArticle.fromFile(Path(markdown_1_fixture))
    assert doc.data.title == markdown_find_line(markdown_1, '# ')[0]


def test_markdown_code_block_split():
    assert ''.join(markdown_code_block_split(markdown_1)) == markdown_1


########################################################################
# Link Converter Test
########################################################################


@pytest.mark.parametrize(
    "text, num, idx, item",
    [
        (r"Hey `aaa` hoho", 3, 1, '`aaa`'),  # normal
        (r"Hey ``aa`a`bb`` hoho", 3, 0, 'Hey '),  # backtick
        (r"Hey ```aa`a``bb\```` hoho ````bb`日本語````", 4, 1, r"```aa`a``bb\```"),  # CJK character
        (r"```aa\`日本語\``bb``` hoho `bbbb` ccc", 4, 1, " hoho ")
    ])
def test_markdown_code_inline_split(text, num, idx, item):
    assert len(markdown_code_inline_split(text)) == num
    assert markdown_code_inline_split(text)[idx] == item


def test_markdown_replace_text():
    assert markdown_replace_text(lambda x: "x", markdown_1)[1] != "x"


@pytest.mark.parametrize("text, func, replaced", [(r"[](hello)", lambda x: x + x, r"[](hellohello)"),
                                                  (r"[日本語](hello world)", lambda x: x + x, r"[日本語](hellohello world)"),
                                                  (r"![日本語](hello world)", lambda x: x + x, r"![日本語](hello world)")])
def test_markdown_replace_link(text, func, replaced):
    assert markdown_replace_link(func, text) == replaced


@pytest.mark.parametrize("text, func, replaced",
                         [(r"![](hello)", lambda x: x + x, r"![](hellohello)"),
                          (r"aaa [日本語](hello world)", lambda x: x + x, r"aaa [日本語](hello world)"),
                          (r"aaa![日本語](hello world)", lambda x: x + x, r"aaa![日本語](hellohello world)")])
def test_markdown_replace_image(text, func, replaced):
    assert markdown_replace_image(func, text) == replaced


########################################################################
# Markdown Converter Test
########################################################################


def test_QiitaSync_toGlobalFormat(markdown_1_fixture, markdown_2_fixture, mocker: MockerFixture):

    setup_mocker(mocker)

    markdown_1_article = QiitaArticle.fromFile(Path(markdown_1_fixture))
    QiitaArticle.fromFile(Path(markdown_2_fixture))

    args = qsync_argparse().parse_args("download .".split())
    qsync = qsync_init(args)
    converted = qsync.toGlobalFormat(markdown_1_article)

    assert markdown_find_line(converted.body, 'LinkTest1:')[0] == f'[dlink](https://qiita.com/{TEST_QIITA_ID}/items/{TEST_ARTICLE_ID1})'
    assert markdown_find_line(converted.body, 'LinkTest2:')[0] == '[dlink](https://example.com/markdown/markdown_2.md)'
    assert markdown_find_line(converted.body, 'ImageTest1:')[0] == f'![ImageTest](https://raw.githubusercontent.com/{TEST_GITHUB_ID}/{TEST_GITHUB_REPO}/{TEST_GITHUB_BRANCH}/img/ImageTest.png)'
    assert markdown_find_line(converted.body, 'ImageTest2:')[0] == f'![ImageTest](https://raw.githubusercontent.com/{TEST_GITHUB_ID}/{TEST_GITHUB_REPO}/{TEST_GITHUB_BRANCH}/img/ImageTest.png description)'
    assert markdown_find_line(converted.body, 'ImageTest3:')[0] == '![ImageTest](http://example.com/img/ImageTest.png img/ImageTest.png)'


def test_QiitaSync_toLocalFormat(markdown_3_fixture, markdown_2_fixture, mocker: MockerFixture):

    setup_mocker(mocker)

    markdown_3_article = QiitaArticle.fromFile(Path(markdown_3_fixture))
    QiitaArticle.fromFile(Path(markdown_2_fixture))

    args = qsync_argparse().parse_args("download .".split())
    qsync = qsync_init(args)
    converted = qsync.toLocalFormat(markdown_3_article)

    assert markdown_find_line(converted.body, 'LinkTest1:')[0] == f'[dlink]({markdown_2_fixture})'
    assert markdown_find_line(converted.body, 'LinkTest2:')[0] == '[dlink](https://example.com/markdown/markdown_2.md)'
    assert markdown_find_line(converted.body, 'ImageTest1:')[0] == f'![ImageTest](img/ImageTest.png)'
    assert markdown_find_line(converted.body, 'ImageTest2:')[0] == f'![ImageTest](img/ImageTest.png description)'
    assert markdown_find_line(converted.body, 'ImageTest3:')[0] == '![ImageTest](http://example.com/img/ImageTest.png img/ImageTest.png)'
    
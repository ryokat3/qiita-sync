import os
import random
import string
import pytest
import datetime
from pathlib import Path
from typing import Generator, List, Optional, NamedTuple, Dict

from qiita_sync.qiita_sync import QiitaArticle, QiitaSync
from qiita_sync.qiita_sync import DEFAULT_ACCESS_TOKEN_FILE, DEFAULT_INCLUDE_GLOB, DEFAULT_EXCLUDE_GLOB
from qiita_sync.qiita_sync import qsync_init, qsync_argparse
from qiita_sync.qiita_sync import rel_path, add_path, url_add_path, get_utc
from qiita_sync.qiita_sync import git_get_committer_datetime, git_get_committer_date, git_get_topdir
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
QSYNC_MODULE_PATH = "qiita_sync.qiita_sync."

TEST_ARTICLE_ID1 = "1234567890ABCDEFG"


def mkpath(p: Optional[str]):
    return f"{p}/" if p is not None and p != "." else ""


def markdown1(md: Optional[str] = None, img: Optional[str] = "img"):
    return f"""
# section

LinkTest1: [dlink]({mkpath(md)}markdown_2.md)
LinkTest2: [dlink](https://example.com/markdown/markdown_2.md)

`````shell
Short sequence of backticks
```
#LinkTest   [LinkTest](LintTest.md)
#ImageTest ![ImageTest](image/ImageTest.png)
`````

## sub-section

ImageTest1: ![ImageTest]({mkpath(img)}ImageTest.png)
ImageTest2: ![ImageTest]({mkpath(img)}ImageTest.png description)
ImageTest3: ![ImageTest](http://example.com/img/ImageTest.png img/ImageTest.png)
"""


def markdown2():
    return f"""
<!--
title: test
tags:  test
id:    {TEST_ARTICLE_ID1}
-->

# test
"""


def markdown3(md: Optional[str] = None, img: Optional[str] = "img"):
    return f"""
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

ImageTest1: ![ImageTest](https://raw.githubusercontent.com/{TEST_GITHUB_ID}/{TEST_GITHUB_REPO}/{TEST_GITHUB_BRANCH}/{mkpath(img)}ImageTest.png)
ImageTest2: ![ImageTest](HTTPS://raw.githubusercontent.com/{TEST_GITHUB_ID}/{TEST_GITHUB_REPO}/{TEST_GITHUB_BRANCH}/{mkpath(img)}ImageTest.png description)
ImageTest3: ![ImageTest](http://example.com/img/ImageTest.png img/ImageTest.png)
"""


def markdown4():
    return """
<!--
private: true
-->

LinkTest1: [dlink](markdown_2.md)

ImageTest1: ![ImageTest](img/ImageTest.png)

"""


@pytest.fixture
def topdir_fx(mocker: MockerFixture, tmpdir) -> Generator[Path, None, None]:
    topdir = Path(tmpdir)

    mocker.patch(f'{QSYNC_MODULE_PATH}qiita_get_authenticated_user_id', return_value=TEST_QIITA_ID)
    mocker.patch(f'{QSYNC_MODULE_PATH}git_get_remote_url', return_value=TEST_GITHUB_SSH_URL)
    mocker.patch(f'{QSYNC_MODULE_PATH}git_get_default_branch', return_value=TEST_GITHUB_BRANCH)
    mocker.patch(f'{QSYNC_MODULE_PATH}git_get_topdir', return_value=str(topdir))
    mocker.patch(f'{QSYNC_MODULE_PATH}git_get_committer_datetime', return_value=datetime.datetime.now())

    yield topdir


class MarkdownFile(NamedTuple):
    filepath: Path
    body: str
    id: str


class MarkdownRepo(NamedTuple):
    qsync: QiitaSync
    file_dict: Dict[str, MarkdownFile]

    @staticmethod
    def getInstance(cls, qsync: QiitaSync, file_list: List[MarkdownFile]):
        return MarkdownRepo(qsync, dict([(mf.filepath.name, mf) for mf in file_list]))
            
########################################################################
# CLI Test
########################################################################


def test_qsync_argparse():
    args = qsync_argparse().parse_args("download .".split())

    assert args.target == "."
    assert args.include == DEFAULT_INCLUDE_GLOB
    assert args.exclude == DEFAULT_EXCLUDE_GLOB
    assert args.token == DEFAULT_ACCESS_TOKEN_FILE


def test_QiitaSync_instance(topdir_fx: Path):

    args = qsync_argparse().parse_args("download .".split())
    qsync = qsync_init(args)

    assert qsync.qiita_id == TEST_QIITA_ID
    assert qsync.git_user == TEST_GITHUB_ID
    assert qsync.git_repository == TEST_GITHUB_REPO
    assert qsync.git_branch == TEST_GITHUB_BRANCH
    assert qsync.git_dir == str(topdir_fx)


########################################################################
# Util Test
########################################################################


@pytest.mark.parametrize("to_path, from_path, relpath", [
    ("/h1", "/h2", "../h1"),
    ("/h1", "/", "h1"),
    ("/", "/h2", ".."),
    ("/h1", "/h1", "."),
])
def test_rel_path(to_path, from_path, relpath):
    assert rel_path(Path(to_path), Path(from_path)) == Path(relpath)


@pytest.mark.parametrize("path, subpath, expected", [("/h1", "../h2", "/h2"), ("/h1", "h2", "/h1/h2"),
                                                     ("/h1", ".", "/h1"), ("/h1", "..", "/"), ("/h1/h2", "..", "/h1")])
def test_add_path(path, subpath, expected):
    assert add_path(Path(path), Path(subpath)) == Path(expected)


@pytest.mark.parametrize("url, subpath, expected",
                         [("https://www.exapmle.com/main/doc", "../img/", "https://www.exapmle.com/main/img"),
                          ("https://www.exapmle.com/main/doc", "hehe", "https://www.exapmle.com/main/doc/hehe"),
                          ("https://www.exapmle.com/main", "..", "https://www.exapmle.com/"),
                          ("https://www.exapmle.com/main/", "..", "https://www.exapmle.com/")])
def test_url_add_path(url, subpath, expected):
    assert url_add_path(url, Path(subpath)) == expected


def test_get_utc():
    assert str(get_utc('2021-12-27T00:40:01+09:00')).endswith("+00:00")


########################################################################
# Git Test
########################################################################


########################################################################
# Markdown Parser Test
########################################################################


def test_QiitaArticle_fromFile(topdir_fx: Path):
    topdir_fx.joinpath("markdown_1.md").write_text(markdown1())

    doc = QiitaArticle.fromFile(topdir_fx.joinpath("markdown_1.md"))
    assert doc.data.title == markdown_find_line(markdown1(), '# ')[0]


def test_markdown_code_block_split():
    assert ''.join(markdown_code_block_split(markdown1())) == markdown1()


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
    assert markdown_replace_text(lambda x: "x", markdown1())[1] != "x"


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


@pytest.mark.parametrize("md1, md2, img", [(None, None, 'img'), (None, 'doc', 'img'), ('doc', None, 'img'),
                                           ('doc/more', None, None)])
def test_QiitaSync_toGlobalFormat(md1, md2, img, topdir_fx: Path):
    md1dir = topdir_fx.joinpath(md1) if md1 is not None else topdir_fx
    md2dir = topdir_fx.joinpath(md2) if md2 is not None else topdir_fx
    imgdir = topdir_fx.joinpath(img) if img is not None else topdir_fx

    mdrel = os.path.relpath(md2dir, md1dir)
    imgrel = os.path.relpath(imgdir, md1dir)
    imgrel2 = os.path.relpath(imgdir, topdir_fx)

    md1dir.mkdir(parents=True, exist_ok=True)
    md1dir.joinpath('markdown_1.md').write_text(markdown1(md=mdrel, img=imgrel))

    md2dir.mkdir(parents=True, exist_ok=True)
    md2dir.joinpath('markdown_2.md').write_text(markdown2())

    markdown_1_article = QiitaArticle.fromFile(md1dir.joinpath('markdown_1.md'))

    args = qsync_argparse().parse_args("download .".split())
    qsync = qsync_init(args)
    converted = qsync.toGlobalFormat(markdown_1_article)

    assert markdown_find_line(
        converted.body, 'LinkTest1:')[0] == f'[dlink](https://qiita.com/{TEST_QIITA_ID}/items/{TEST_ARTICLE_ID1})'
    assert markdown_find_line(converted.body, 'LinkTest2:')[0] == '[dlink](https://example.com/markdown/markdown_2.md)'
    assert markdown_find_line(
        converted.body, 'ImageTest1:'
    )[0] == f'![ImageTest](https://raw.githubusercontent.com/{TEST_GITHUB_ID}/{TEST_GITHUB_REPO}/{TEST_GITHUB_BRANCH}/{mkpath(imgrel2)}ImageTest.png)'
    assert markdown_find_line(
        converted.body, 'ImageTest2:'
    )[0] == f'![ImageTest](https://raw.githubusercontent.com/{TEST_GITHUB_ID}/{TEST_GITHUB_REPO}/{TEST_GITHUB_BRANCH}/{mkpath(imgrel2)}ImageTest.png description)'
    assert markdown_find_line(
        converted.body, 'ImageTest3:')[0] == '![ImageTest](http://example.com/img/ImageTest.png img/ImageTest.png)'


def test_QiitaSync_toLocalFormat(topdir_fx: Path):

    topdir_fx.joinpath('markdown_2.md').write_text(markdown2())
    topdir_fx.joinpath('markdown_3.md').write_text(markdown3())

    markdown_3_article = QiitaArticle.fromFile(topdir_fx.joinpath('markdown_3.md'))

    args = qsync_argparse().parse_args("download .".split())
    qsync = qsync_init(args)
    converted = qsync.toLocalFormat(markdown_3_article)

    assert markdown_find_line(converted.body, 'LinkTest1:')[0] == '[dlink](markdown_2.md)'
    assert markdown_find_line(converted.body, 'LinkTest2:')[0] == '[dlink](https://example.com/markdown/markdown_2.md)'
    assert markdown_find_line(converted.body, 'ImageTest1:')[0] == '![ImageTest](img/ImageTest.png)'
    assert markdown_find_line(converted.body, 'ImageTest2:')[0] == '![ImageTest](img/ImageTest.png description)'
    assert markdown_find_line(
        converted.body, 'ImageTest3:')[0] == '![ImageTest](http://example.com/img/ImageTest.png img/ImageTest.png)'


def test_QiitaSync_format_conversion(topdir_fx: Path):

    topdir_fx.joinpath('markdown_1.md').write_text(markdown1())
    topdir_fx.joinpath('markdown_2.md').write_text(markdown2())
    topdir_fx.joinpath('markdown_3.md').write_text(markdown3())

    markdown1_article = QiitaArticle.fromFile(topdir_fx.joinpath('markdown_1.md'))
    markdown3_article = QiitaArticle.fromFile(topdir_fx.joinpath('markdown_3.md'))

    args = qsync_argparse().parse_args("download .".split())
    qsync = qsync_init(args)

    assert qsync.toLocalFormat(
        qsync.toGlobalFormat(markdown1_article)).body.lower() == qsync.toLocalFormat(markdown1_article).body.lower()
    assert qsync.toGlobalFormat(
        qsync.toLocalFormat(markdown3_article)).body.lower() == qsync.toGlobalFormat(markdown3_article).body.lower()

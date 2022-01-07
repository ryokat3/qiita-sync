import os
import random
import string
import pytest
import datetime
from pathlib import Path
from typing import Generator, List, Optional, NamedTuple, Dict, Callable
from dataclasses import dataclass

from qiita_sync.qiita_sync import QiitaArticle, QiitaSync
from qiita_sync.qiita_sync import DEFAULT_ACCESS_TOKEN_FILE, DEFAULT_INCLUDE_GLOB, DEFAULT_EXCLUDE_GLOB
from qiita_sync.qiita_sync import qsync_init, qsync_argparse, Maybe
from qiita_sync.qiita_sync import rel_path, add_path, url_add_path, get_utc
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


@pytest.fixture
def topdir_fx(mocker: MockerFixture, tmpdir) -> Generator[Path, None, None]:
    topdir = Path(tmpdir)

    mocker.patch(f'{QSYNC_MODULE_PATH}qiita_get_authenticated_user_id', return_value=TEST_QIITA_ID)
    mocker.patch(f'{QSYNC_MODULE_PATH}git_get_remote_url', return_value=TEST_GITHUB_SSH_URL)
    mocker.patch(f'{QSYNC_MODULE_PATH}git_get_default_branch', return_value=TEST_GITHUB_BRANCH)
    mocker.patch(f'{QSYNC_MODULE_PATH}git_get_topdir', return_value=str(topdir))
    mocker.patch(f'{QSYNC_MODULE_PATH}git_get_committer_datetime', return_value=datetime.datetime.now())

    yield topdir


# @dataclass(frozen=True)
@dataclass
class Asset:
    filepath: str


# @dataclass(frozen=True)
@dataclass
class MarkdownAsset(Asset):
    body: Callable[[Callable[[str], str], Callable[[str], str]], str]

    def getBody(self, mdlink: Callable[[str], str], imglink: Callable[[str], str]) -> str:
        # NOTE:
        #
        # Call 'body' attribute cause mypy error (Invalid self argument "MarkdownAsset" to attribute function "body")
        # Workaround is to remove (frozen=True)
        #
        # reference: https://github.com/python/mypy/issues/5485
        #
        return self.body(mdlink, imglink)


def filterMarkdownAsset(asset: Asset) -> Optional[MarkdownAsset]:
    return asset if isinstance(asset, MarkdownAsset) else None


class Repository(NamedTuple):
    qsync: QiitaSync
    asset_dict: Dict[str, Asset]

    @classmethod
    def getInstance(cls, qsync: QiitaSync, asset_list: List[Asset]):
        return Repository(qsync, dict([(Path(mf.filepath).name, mf) for mf in asset_list]))

    def writeMarkdown(self):
        for asset in self.asset_dict.values():
            if isinstance(asset, MarkdownAsset):
                target = Path(self.qsync.git_dir).joinpath(asset.filepath)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("w") as fp:
                    fp.write(self.getLocalMarkdown(target.name))

    def genGetLocalLink(self, source: str) -> Callable[[str], str]:
        return lambda target: Maybe(self.asset_dict.get(target)).map(
            lambda asset: os.path.relpath(asset.filepath, os.path.dirname(source))).getOrElse(target)

    def getGlobalMarkdownLink(self, _target: str):
        return Maybe(self.asset_dict.get(_target)).optionalMap(
            lambda target: QiitaArticle.fromFile(Path(self.qsync.git_dir).joinpath(target.filepath)).data.id).map(
                self.qsync.getQiitaUrl).getOrElse(_target)

    def getGlobalImageLink(self, filename: str):
        return Maybe(self.asset_dict.get(filename)).map(
            lambda asset: f"{self.qsync.github_url}{asset.filepath}").getOrElse(filename)

    def getLocalMarkdown(self, filename: str):
        return Maybe(self.asset_dict.get(filename)).optionalMap(filterMarkdownAsset).map(
            lambda md: md.getBody(self.genGetLocalLink(md.filepath), self.genGetLocalLink(md.filepath))).get()

    def getGlobalMarkdown(self, filename: str):
        return Maybe(self.asset_dict.get(filename)).optionalMap(filterMarkdownAsset).map(
            lambda md: md.getBody(self.getGlobalMarkdownLink, self.getGlobalImageLink)).get()


def get_qsync(asset_list: List[Asset]):
    args = qsync_argparse().parse_args("download .".split())
    repo = Repository.getInstance(qsync_init(args), asset_list)
    repo.writeMarkdown()
    return qsync_init(args)


def identity(x: str) -> str:
    return x


def gen_md1(mdlink: Callable[[str], str], imglink: Callable[[str], str]):
    return f"""
# section

LinkTest1: [dlink]({mdlink("md2.md")})
LinkTest2: [dlink](https://example.com/markdown/md2.md)

`````shell
Short sequence of backticks
```
#LinkTest   [LinkTest](md2.md)
#ImageTest ![ImageTest](img1.png)
`````

## sub-section

ImageTest1: ![ImageTest]({imglink("img1.png")})
ImageTest2: ![ImageTest]({imglink("img1.png")} description)
ImageTest3: ![ImageTest](http://example.com/img/img1.png img/img1.png)
"""


def gen_md2(mdlink: Callable[[str], str], imglink: Callable[[str], str]):
    return f"""
<!--
title:  Hello
tags:   python
id:     {TEST_ARTICLE_ID1}
-->
[md1]({mdlink('md1.md')})
![img1]({imglink("img1.png")})
"""

    
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
    get_qsync([MarkdownAsset("md1.md", gen_md1), MarkdownAsset("md2.md", gen_md2), Asset("img1.png")])
    doc = QiitaArticle.fromFile(topdir_fx.joinpath("md1.md"))

    assert doc.data.title == markdown_find_line(doc.body, '# ')[0]


def test_markdown_code_block_split():
    md = gen_md1(identity, identity)
    assert ''.join(markdown_code_block_split(md)) == md


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
    md = gen_md1(identity, identity)
    assert markdown_replace_text(lambda x: "x", md)[1] != "x"


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


@pytest.mark.parametrize("md1, md2, img1", [
    ("md1.md", "md2.md", 'img1.png'),
    ("md1.md", "doc/md2.md", 'img1.png'),
    ("doc/md1.md", "md2.md", 'img1.png'),
    ("doc/md1.md", "doc2/md2.md", 'images/img1.png')
])
def test_QiitaSync_toGlobalFormat(md1, md2, img1, topdir_fx: Path):
    qsync = get_qsync([MarkdownAsset(md1, gen_md1), MarkdownAsset(md2, gen_md2), Asset(img1)])
    article = qsync.toGlobalFormat(QiitaArticle.fromFile(topdir_fx.joinpath(md1)))

    assert markdown_find_line(
        article.body, 'LinkTest1:')[0] == f'[dlink](https://qiita.com/{qsync.qiita_id}/items/{TEST_ARTICLE_ID1})'
    assert markdown_find_line(article.body, 'LinkTest2:')[0] == '[dlink](https://example.com/markdown/md2.md)'
    assert markdown_find_line(article.body, 'ImageTest1:')[0] ==\
        f"![ImageTest](https://raw.githubusercontent.com/{qsync.git_user}/{qsync.git_repository}/{qsync.git_branch}/{img1})"
    assert markdown_find_line(article.body, 'ImageTest2:')[0] ==\
        f"![ImageTest](https://raw.githubusercontent.com/{qsync.git_user}/{qsync.git_repository}/{qsync.git_branch}/{img1} description)"
    assert markdown_find_line(article.body, 'ImageTest3:')[0] ==\
        '![ImageTest](http://example.com/img/img1.png img/img1.png)'


@pytest.mark.parametrize("md1, md2, img1", [
    ("md1.md", "md2.md", 'img1.png'),
    ("md1.md", "doc/md2.md", 'img1.png'),
    ("doc/md1.md", "md2.md", 'img1.png'),
    ("doc/md1.md", "doc2/md2.md", 'images/img1.png')
])
def test_QiitaSync_toLocalFormat(md1, md2, img1, topdir_fx: Path):
    qsync = get_qsync([MarkdownAsset(md1, gen_md1), MarkdownAsset(md2, gen_md2), Asset(img1)])
    article = qsync.toLocalFormat(QiitaArticle.fromFile(topdir_fx.joinpath(md1)))

    assert markdown_find_line(article.body, 'LinkTest1:')[0] ==\
        f'[dlink]({os.path.relpath(md2, os.path.dirname(md1))})'
    assert markdown_find_line(article.body, 'LinkTest2:')[0] ==\
        '[dlink](https://example.com/markdown/md2.md)'
    assert markdown_find_line(article.body, 'ImageTest1:')[0] ==\
        f'![ImageTest]({os.path.relpath(img1, os.path.dirname(md1))})'
    assert markdown_find_line(article.body, 'ImageTest2:')[0] ==\
        f'![ImageTest]({os.path.relpath(img1, os.path.dirname(md1))} description)'
    assert markdown_find_line(article.body, 'ImageTest3:')[0] ==\
        '![ImageTest](http://example.com/img/img1.png img/img1.png)'


@pytest.mark.parametrize("md1, md2, img1", [
    ("md1.md", "md2.md", 'img1.png'),
    ("md1.md", "doc/md2.md", 'img1.png'),
    ("doc/md1.md", "md2.md", 'img1.png'),
    ("doc/md1.md", "doc2/md2.md", 'images/img1.png')
])
def test_QiitaSync_format_conversion(md1, md2, img1, topdir_fx: Path):
    qsync = get_qsync([MarkdownAsset(md1, gen_md1), MarkdownAsset(md2, gen_md2), Asset(img1)])
    article = qsync.toLocalFormat(QiitaArticle.fromFile(topdir_fx.joinpath(md1)))

    assert qsync.toLocalFormat(
        qsync.toGlobalFormat(article)).body.lower() == qsync.toLocalFormat(article).body.lower()
    assert qsync.toGlobalFormat(
        qsync.toLocalFormat(article)).body.lower() == qsync.toGlobalFormat(article).body.lower()

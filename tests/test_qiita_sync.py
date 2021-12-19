import random
import string

import pytest
from qiita_sync import __version__
from qiita_sync.qiita_sync import (
    QiitaDoc,
    GitHubRepository,
    git_get_default_branch,
    git_get_topdir,
    markdown_code_block_split,
    markdown_code_inline_split,
    markdown_replace_text,
    markdown_replace_link,
    markdown_replace_image,
    qsync_convert_doc
)

import os
from pathlib import Path
from typing import Optional


markdown_1 = """
Hello, world

# 日本語

Link to [test2](test2.md)

`````shell
echo "hehe"
```
echo "hello, world"
![hello](img/hehe.png description)
`````

## その後で

![hello](img/hehe.png description)

"""

markdown_2 = """
<!--
title: テスト
tags:  テスト
id:    123457689
-->

Hello, world

# 日本語


`````shell
echo "hehe"
```
echo "hello, world"
![hello](img/hehe.png description)
`````

## その後で

![hello](img/hehe.png description)

"""


def generate_random_name(length: int) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def generate_tmpfile_fixture(content: str):
    filename = generate_random_name(16)    

    @pytest.fixture
    def _(tmpdir) -> str:
        tmpfile = tmpdir.join(filename)

        try:
            with tmpfile.open("w") as f:
                f.write(content)
            yield str(tmpfile)
        finally:
            tmpfile.remove()

    return _


def generate_file_fixture(content: str, filename: str):

    @pytest.fixture
    def _() -> str:
        filepath = Path(filename)

        try:
            filepath.write_text(content)
            yield str(filename)
        finally:
            filepath.unlink()

    return _

markdown_1_fixture = generate_file_fixture(markdown_1, "test.md")
markdown_2_fixture = generate_file_fixture(markdown_2, "test2.md")

markdown_1_tmp_fixture = generate_tmpfile_fixture(markdown_1)


def test_version():
    assert __version__ == "0.1.0"


def test_git_get_default_branch():
    assert git_get_default_branch() == "main"


def test_QiitaDoc_fromFile(markdown_1_tmp_fixture):
    doc = QiitaDoc.fromFile(Path(markdown_1_tmp_fixture))
    assert doc.data.title == "日本語"


def test_GitHubRepository_get_instance():
    instance = GitHubRepository.getInstance()
    assert instance is not None
    assert instance.user == "wak109"
    assert instance.repository == "qiita-sync"
    assert instance.default_branch == "main"


def test_GitHubRepository_getGitHubUrl():    
    print(GitHubRepository.getInstance().getGitHubUrl(os.path.join(git_get_topdir(), "hehe/hehe.png")))


def test_markdown_code_block_split():
    assert ''.join(markdown_code_block_split(markdown_1)) == markdown_1


@pytest.mark.parametrize(
    "text, num, idx, item", [
        (r"Hey `aaa` hoho", 3, 1, '`aaa`'),  # normal
        (r"Hey ``aa`a`bb`` hoho", 3, 0, 'Hey '),  # backtick
        (r"Hey ```aa`a``bb\```` hoho ````bb`日本語````", 4, 1, r"```aa`a``bb\```"),  # CJK character
        (r"```aa\`日本語\``bb``` hoho `bbbb` ccc", 4, 1, " hoho ")
    ]
)
def test_markdown_code_inline_split(text, num, idx, item):
    assert len(markdown_code_inline_split(text)) == num
    assert markdown_code_inline_split(text)[idx] == item


def test_markdown_replace_text():
    assert markdown_replace_text(lambda x: "x", markdown_1)[1] != "x"


@pytest.mark.parametrize(
    "text, func, replaced", [
        (r"[](hello)", lambda x:x+x, r"[](hellohello)"),
        (r"[日本語](hello world)", lambda x:x+x, r"[日本語](hellohello world)"),
        (r"![日本語](hello world)", lambda x:x+x, r"![日本語](hello world)")
    ]
)
def test_markdown_replace_link(text, func, replaced):
    assert markdown_replace_link(func, text) == replaced


@pytest.mark.parametrize(
    "text, func, replaced", [
        (r"![](hello)", lambda x:x+x, r"![](hellohello)"),
        (r"aaa [日本語](hello world)", lambda x:x+x, r"aaa [日本語](hello world)"),
        (r"aaa![日本語](hello world)", lambda x:x+x, r"aaa![日本語](hellohello world)")
    ]
)
def test_markdown_replace_image(text, func, replaced):
    assert markdown_replace_image(func, text) == replaced


def test_qsync_convert_doc(markdown_1_fixture, markdown_2_fixture):
    doc1 = QiitaDoc.fromFile(Path(markdown_1_fixture))
    doc2 = QiitaDoc.fromFile(Path(markdown_2_fixture))
    print(qsync_convert_doc(markdown_1_fixture, doc1.body, "hehe"))
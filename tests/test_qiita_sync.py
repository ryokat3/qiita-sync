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
    markdown_replace_image
)

import os
from pathlib import Path


markdown_1 = """
Hello, world

# 日本語

`````shell
echo "hehe"
```
echo "hello, world"
`````

## その後で

"""


def generate_random_name(length: int) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def generate_file_fixture(content: str):
    filename = generate_random_name(16)

    @pytest.fixture
    def _(tmpdir) -> str:
        tmpfile = tmpdir.join(filename)

        with tmpfile.open("w") as f:
            f.write(content)
        yield str(tmpfile)

        tmpfile.remove()

    return _


markdown_1_fixture = generate_file_fixture(markdown_1)


def test_version():
    assert __version__ == "0.1.0"


def test_git_get_default_branch():
    assert git_get_default_branch() == "main"


def test_QiitaDoc_fromFile(markdown_1_fixture):
    doc = QiitaDoc.fromFile(Path(markdown_1_fixture))
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
        (r" [日本語](hello world)", lambda x:x+x, r" [日本語](hello world)"),
        (r"![日本語](hello world)", lambda x:x+x, r"![日本語](hellohello world)")
    ]
)
def test_markdown_replace_image(text, func, replaced):
    assert markdown_replace_image(func, text) == replaced  
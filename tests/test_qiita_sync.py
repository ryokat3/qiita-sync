import random
import string

import pytest
from qiita_sync import __version__
from qiita_sync.qiita_sync import (
    QiitaDoc,
    markdown_code_block_split,
    markdown_code_inline_split,
    markdown_replace_text
)

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


def test_QiitaDoc_fromFile(markdown_1_fixture):
    doc = QiitaDoc.fromFile(Path(markdown_1_fixture))
    assert doc.data.title == "日本語"


def test_markdown_code_block_split():
    assert ''.join(markdown_code_block_split(markdown_1)) == markdown_1


@pytest.mark.parametrize(
    "text, num, idx, item", [
        (r"Hey `aaa` hoho", 3, 1, '`aaa`'),
        (r"Hey `aa\`a\`bb` hoho", 3, 0, 'Hey '),
        (r"Hey `aa\`a\`bb` hoho `bb\`日本語`", 4, 1, r"`aa\`a\`bb`"),
        (r"`aa\`日本語\`bb` hoho `bb\`bb` ccc", 4, 1, " hoho ")
    ]
)
def test_markdown_code_inline_split(text, num, idx, item):
    assert len(markdown_code_inline_split(text)) == num
    assert markdown_code_inline_split(text)[idx] == item


def test_markdown_replace_text():
    assert markdown_replace_text(lambda x: "x", markdown_1)[1] != "x"

import random
import string

import pytest
from qiita_sync import __version__
from qiita_sync.qiita_sync import QiitaDoc

from pathlib import Path


markdown_1 = """
Hello, world

# 日本語

```shell
echo "hello, world"
```
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

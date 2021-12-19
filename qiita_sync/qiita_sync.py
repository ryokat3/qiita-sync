#!/usr/bin/env python
#
from __future__ import annotations

import functools
import json
import os
import subprocess
import re
from argparse import ArgumentParser
from itertools import dropwhile
from pathlib import Path
from datetime import datetime, timezone

from urllib import request
from urllib.parse import urlparse
from urllib.error import HTTPError
from http.client import HTTPResponse
from urllib.request import OpenerDirector
from http import cookiejar

from typing import (
    Callable,
    Optional,
    TypeVar,
    NamedTuple,
    Tuple,
    Union,
    Dict,
    Any,
    List,
)

T = TypeVar("T")

########################################################################
# Const
########################################################################

DEFAULT_ACCESS_TOKEN_FILE = "access_token.txt"
DEFAULT_MARKDOWN_DIR = "qiita"

########################################################################
# Util
########################################################################


def convert_json_to_bytes(x):
    return bytes(json.dumps(x), "utf-8")


def exec_command(cmdarglist: List[str]) -> Optional[str]:
    result = subprocess.run(cmdarglist, stdout=subprocess.PIPE)
    return result.stdout.decode("utf-8").rstrip() if result.returncode == 0 else None


def update_mtime(filepath: str, t: datetime):
    os.utime(filepath, (t.timestamp(), t.timestamp()))


def is_url(text: str) -> bool:
    try:
        urlparse(text)
        return True
    except Exception:
        return False


########################################################################
# Git
########################################################################


@functools.lru_cache(maxsize=1)
def git_get_topdir() -> Optional[str]:
    return exec_command("git rev-parse --show-toplevel".split())


@functools.lru_cache(maxsize=1)
def git_get_remote_url() -> Optional[str]:
    return exec_command("git config --get remote.origin.url".split())


def git_get_committer_date(filename: str) -> Optional[str]:
    # "%cI", committer date, strict ISO 8601 format
    return exec_command("git log -1 --pretty='%cI'".split() + [filename])


@functools.lru_cache(maxsize=1)
def git_get_default_branch() -> Optional[str]:
    return exec_command("git rev-parse --abbrev-ref HEAD".split())
    

########################################################################
# Rest API
########################################################################


class RestApiResponse(NamedTuple):
    header: HTTPResponse
    data: bytes


RESTAPI_CALLER_TYPE = Callable[[str, str, Optional[T]], RestApiResponse]


def reastapi_add_content_type(
    _headers: Optional[Dict[str, str]],
    content_type: Optional[str],
    content: Optional[bytes],
) -> Dict[str, str]:
    """Add 'Content-Type' header if exists"""
    headers = _headers.copy() if _headers is not None else {}
    if content_type is not None and content is not None and len(content) != 0:
        headers["Content-Type"] = content_type
    return headers


def restapi_create_request(
    url: str,
    method: str,
    headers: Optional[Dict[str, str]],
    content_type: Optional[str],
    content: Optional[bytes],
) -> request.Request:
    """Create Request instance including content if exists"""
    return request.Request(
        url,
        data=content if content is not None and len(content) > 0 else None,
        method=method,
        headers=reastapi_add_content_type(headers, content_type, content),
    )


def restapi_call(
    opener: OpenerDirector,
    url: str,
    method: str,
    headers: Optional[Dict[str, str]],
    content_type: Optional[str] = None,
    content: Optional[bytes] = None,
) -> RestApiResponse:
    """Execute HTTP Request with OpenerDirector"""
    with opener.open(
        restapi_create_request(url, method, headers, content_type, content)
    ) as response:
        return RestApiResponse(response, response.read())


def restapi_build_opener() -> OpenerDirector:
    """Create OpenerDirector instance with cookie processor"""
    return request.build_opener(
        request.BaseHandler(), request.HTTPCookieProcessor(cookiejar.CookieJar())
    )


def restapi_json_response(resp: RestApiResponse):
    return json.loads(resp.data.decode("utf-8"))


########################################################################
# Qiita API
########################################################################

QIITA_API_ENDPOINT = "https://qiita.com/api/v2"


def qiita_build_caller(
    opener: OpenerDirector,
    content_type: str,
    headers: Optional[Dict[str, str]] = None,
    content_decoder=lambda x: x,
) -> RESTAPI_CALLER_TYPE:
    def _(url: str, method: str, content: Optional[T] = None) -> RestApiResponse:
        try:
            return restapi_call(
                opener,
                url,
                method,
                headers,
                content_type,
                content_decoder(content) if content is not None else None,
            )
        except HTTPError as http_error:
            if http_error.code == 429:  # Too much Request
                return _(url, method, content)
            else:
                raise http_error

    return _


def qiita_create_caller(auth_token: str):
    return qiita_build_caller(
        restapi_build_opener(),
        "application/json",
        {
            "Cache-Control": "no-cache, no-store",
            "Authorization": f"Bearer {auth_token}",
        },
        convert_json_to_bytes,
    )


def qiita_get_item_list(caller: RESTAPI_CALLER_TYPE):
    return restapi_json_response(
        caller(f"{QIITA_API_ENDPOINT}/authenticated_user/items", "GET", None)
    )


def qiita_get_item(caller: RESTAPI_CALLER_TYPE, id: str):
    return restapi_json_response(
        caller(f"{QIITA_API_ENDPOINT}/items/{id}", "GET", None)
    )


def qiita_post_item(caller: RESTAPI_CALLER_TYPE, data):
    return restapi_json_response(caller(f"{QIITA_API_ENDPOINT}/items", "POST", data))


def qiita_patch_item(caller: RESTAPI_CALLER_TYPE, id: str, data):
    return restapi_json_response(
        caller(f"{QIITA_API_ENDPOINT}/items/{id}", "PATCH", data)
    )


def qiita_delete_item(caller: RESTAPI_CALLER_TYPE, id: str):
    return restapi_json_response(
        caller(f"{QIITA_API_ENDPOINT}/items/{id}", "DELETE", None)
    )


########################################################################
# Qiita Data
########################################################################


def qiita_get_first_section(body: str) -> Optional[str]:
    m = next(
        dropwhile(
            lambda m: m is None,
            map(lambda line: re.match(r"^#+\s+(.*)$", line), body.splitlines()),
        ),
        None,
    )
    return m.group(1).strip() if m is not None else None


def qiita_get_first_line(body: str) -> Optional[str]:
    m = next(
        dropwhile(
            lambda m: m is None,
            map(lambda line: re.match(r"(\S+)", line), body.splitlines()),
        ),
        None,
    )
    return m.group(1).strip() if m is not None else None


def qiita_get_temporary_title(body: str) -> str:
    return qiita_get_first_section(body) or qiita_get_first_line(body) or "No Title"


class QiitaTag(NamedTuple):
    name: str
    versions: List[str]

    def __str__(self) -> str:
        return (
            f"{self.name}={'|'.join(self.versions)}"
            if len(self.versions) > 0
            else self.name
        )

    def toApi(self) -> Dict[str, Any]:
        return {"name": self.name, "versions": self.versions}

    @classmethod
    def fromString(cls, text: str) -> QiitaTag:
        tpl = text.split("=", 1)
        return cls(tpl[0], tpl[1].split("|")) if len(tpl) == 2 else cls(tpl[0], [])


class QiitaTags(List[QiitaTag]):
    def __str__(self) -> str:
        return ",".join(map(str, self))

    def toApi(self) -> List[Dict[str, Any]]:
        return [tag.toApi() for tag in self]

    @classmethod
    def fromString(cls, text: str) -> QiitaTags:
        return cls(map(lambda s: QiitaTag.fromString(s), text.split(",")))

    @classmethod
    def fromApi(cls, value) -> QiitaTags:
        return cls(map(lambda data: QiitaTag(data["name"], data["versions"]), value))


class QiitaData(NamedTuple):
    title: str
    tags: QiitaTags
    id: Optional[str]

    def __str__(self) -> str:
        return os.linesep.join(
            filter(
                None,
                [
                    f"title: {self.title}",
                    f"tags:  {str(self.tags)}",
                    f"id:    {self.id}" if self.id is not None else None,
                ],
            )
        )

    @classmethod
    def fromString(cls, text: str) -> Union[QiitaData, Dict[str, str]]:
        data = (
            dict(
                map(
                    lambda tpl: (tpl[0].strip(), tpl[1].strip()),
                    map(
                        lambda line: line.split(":", 1),
                        filter(
                            lambda line: re.match(r"^\s*\w+\s*:.*\S", line) is not None,
                            text.splitlines(),
                        ),
                    ),
                )
            )
            if text is not None
            else {}
        )

        return (
            cls(
                data["title"],
                QiitaTags.fromString(data["tags"]),
                data["id"] if "id" in data else None,
            )
            if "title" in data and "tags" in data
            else data
        )

    @classmethod
    def fromApi(cls, item) -> QiitaData:
        return cls(
            title=item["title"], tags=QiitaTags.fromApi(item["tags"]), id=item["id"]
        )


class QiitaDoc(NamedTuple):
    data: QiitaData
    body: str
    timestamp: datetime

    def toText(self) -> str:
        return (
            f"{os.linesep.join(['<!--', str(self.data), '-->'])}{os.linesep}{self.body}"
        )

    def toApi(self) -> Dict[str, Any]:
        return {
            "body": self.body,
            "tags": self.data.tags.toApi(),
            "title": self.data.title,
        }

    @classmethod
    def fromFile(cls, file: Path) -> QiitaDoc:
        text = file.read_text()
        timestamp = datetime.fromtimestamp(file.stat().st_mtime, timezone.utc)
        m = re.match(
            r"^\s*\<\!\-\-\s(.*?)\s\-\-\>(.*)$", text, re.MULTILINE | re.DOTALL
        )
        qiita_data = QiitaData.fromString(m.group(1)) if m is not None else {}
        return (
            cls(
                data=qiita_data,
                body=m.group(2) if m is not None else "",
                timestamp=timestamp,
            )
            if isinstance(qiita_data, QiitaData)
            else cls(
                data=QiitaData(
                    qiita_data["title"]
                    if "title" in qiita_data
                    else qiita_get_temporary_title(text),
                    QiitaTags.fromString(
                        qiita_data["tags"] if "tags" in qiita_data else "NoTag"
                    ),
                    None,
                ),
                body=text,
                timestamp=timestamp,
            )
        )

    @classmethod
    def fromApi(cls, item) -> QiitaDoc:
        return cls(
            data=QiitaData.fromApi(item),
            body=item["body"],
            timestamp=datetime.strptime(
                item["updated_at"], "%Y-%m-%dT%H:%M:%S%z"
            ).astimezone(timezone.utc),
        )


#######################################################################
# GitHub
#######################################################################

GITHUB_SSH_URL_REGEX = re.compile(r"^git@github.com:(.*)/(.*)\.git")
GITHUB_HTTPS_URL_REGEX = re.compile(r"^https://github.com/(.*)/(.*)\.git")


class GitHubRepository(NamedTuple):
    user: str
    repository: str
    default_branch: str
    top_dir: str

    def getGitHubUrl(self, pathname: str) -> Optional[str]:
        try:
            relative_path = Path(pathname).relative_to(self.top_dir).as_posix()
            return f"https://raw.githubusercontent.com/{self.user}/{self.repository}/{self.default_branch}/{relative_path}"
        except Exception:
            return None

    @classmethod
    def getInstance(cls) -> Optional[GitHubRepository]:
        url = git_get_remote_url()
        print(url)
        branch = git_get_default_branch()
        print(branch)
        user_repo = (
            match_github_https_url(url) or match_github_ssh_url(url)
            if url is not None
            else None
        )
        print(user_repo)
        top_dir = git_get_topdir()
        print(top_dir)
        return (
            GitHubRepository(user_repo[0], user_repo[1], branch, top_dir)
            if user_repo is not None and branch is not None and top_dir is not None
            else None
        )


def match_github_ssh_url(text: str) -> Optional[Tuple[str, str]]:
    m = re.match(GITHUB_SSH_URL_REGEX, text)
    return (m.group(1), m.group(2)) if m is not None else None


def match_github_https_url(text: str) -> Optional[Tuple[str, str]]:
    m = re.match(GITHUB_HTTPS_URL_REGEX, text)
    return (m.group(1), m.group(2)) if m is not None else None


#######################################################################
# Markdown
#######################################################################

CODE_BLOCK_REGEX = re.compile(
    r"([\r\n]+\s*[\r\n]+(?P<CB>````*).*?[\r\n](?P=CB)\s*[\r\n]+)",
    re.MULTILINE | re.DOTALL,
)
CODE_INLINE_REGEX = re.compile(
    r"((?P<BT>``*)[^\r\n]*?(?P=BT))", re.MULTILINE | re.DOTALL
)
MARKDOWN_LINK_REGEX = re.compile(
    r"(?<!\!)(\[[^\]]*\]\()([^\ \)]*)(.*\))", re.MULTILINE | re.DOTALL
)
MARKDOWN_IMAGE_REGEX = re.compile(
    r"(\!\[[^\]]*\]\()([^\ \)]*)(.*\))", re.MULTILINE | re.DOTALL
)


def markdown_code_block_split(text: str) -> List[str]:
    return list(
        filter(
            lambda elm: elm is not None and re.match(r"^````*$", elm) is None,
            re.split(CODE_BLOCK_REGEX, text),
        )
    )


def markdown_code_inline_split(text: str) -> List[str]:
    return list(
        filter(
            None,
            filter(
                lambda elm: elm is not None and re.match(r"^``*$", elm) is None,
                re.split(CODE_INLINE_REGEX, text),
            ),
        )
    )


def markdown_replace_block_text(func: Callable[[str], str], text: str):
    return "".join(
        [
            func(block) if CODE_BLOCK_REGEX.match(block) is None else block
            for block in markdown_code_block_split(text)
        ]
    )


def markdown_replace_text(func: Callable[[str], str], text: str):
    return markdown_replace_block_text(
        lambda block: "".join(
            [
                func(x) if CODE_INLINE_REGEX.match(x) is None else x
                for x in markdown_code_inline_split(block)
            ]
        ),
        text,
    )


def markdown_replace_link(func: Callable[[str], str], text: str):
    return re.sub(
        MARKDOWN_LINK_REGEX,
        lambda m: "".join([m.group(1), func(m.group(2)), m.group(3)]),
        text,
    )


def markdown_replace_image(func: Callable[[str], str], text: str):
    return re.sub(
        MARKDOWN_IMAGE_REGEX,
        lambda m: "".join([m.group(1), func(m.group(2)), m.group(3)]),
        text,
    )


########################################################################
# Qiita Sync
########################################################################


def qsync_get_topdir() -> str:
    return git_get_topdir() or "."


def qsync_get_access_token(token_file: str) -> str:
    with open(os.path.join(qsync_get_topdir(), token_file), "r") as fp:
        return fp.read().strip()


def qsync_get_local_docs(docdir: str):
    return dict(
        [
            (fp.name, QiitaDoc.fromFile(fp))
            for fp in Path(docdir).glob("*.md")
            if fp.is_file()
        ]
    )


def qsync_get_doc(docs: Dict[str, QiitaDoc], id: str) -> Optional[Tuple[str, QiitaDoc]]:
    return next(
        dropwhile(lambda tpl: tpl is not None and tpl[1].data.id != id, docs.items()),
        None,
    )


def qsync_get_remote_docs(caller: RESTAPI_CALLER_TYPE):
    return dict(
        [(item["id"], QiitaDoc.fromApi(item)) for item in qiita_get_item_list(caller)]
    )


def qsync_save_doc(doc: QiitaDoc, filepath: str):
    with open(filepath, "w") as fp:
        fp.write(doc.toText())


def qsync_download_all(caller: RESTAPI_CALLER_TYPE, docdir: str):
    Path(docdir).mkdir(parents=True, exist_ok=True)
    local_docs = qsync_get_local_docs(docdir)
    for item in qiita_get_item_list(caller):
        doc = QiitaDoc.fromApi(item)
        if doc.data.id is not None:
            tpl = qsync_get_doc(local_docs, doc.data.id)
            qsync_save_doc(
                QiitaDoc.fromApi(item),
                os.path.join(
                    docdir, tpl[0] if tpl is not None else f"{doc.data.id}.md"
                ),
            )


def qsync_upload_doc(caller: RESTAPI_CALLER_TYPE, filepath: str):
    doc = QiitaDoc.fromFile(Path(filepath))
    if doc.data.id is not None:
        response = qiita_patch_item(caller, doc.data.id, doc.toApi())
        if response is not None:
            update_mtime(filepath, QiitaDoc.fromApi(response).timestamp)
    else:
        response = qiita_post_item(caller, doc.toApi())
        if response is not None:
            newdoc = QiitaDoc.fromApi(response)
            qsync_save_doc(
                QiitaDoc(body=doc.body, data=newdoc.data, timestamp=newdoc.timestamp),
                filepath,
            )
            update_mtime(filepath, newdoc.timestamp)


def qsync_gen_convert_image(pathname: str) -> Callable[[str], str]:
    def _(link: str) -> str:
        instance = GitHubRepository.getInstance()
        if instance is not None and is_url(link) is False:
            url = instance.getGitHubUrl(link)
            return url if url is not None else link
        else:
            return link

    return _


# TODO: not implemented !!!
def qsync_gen_convert_link(pathname: str):
    return pathname


def qsync_convert_doc(pathname: str, content: str) -> str:
    return markdown_replace_text(
        lambda text: markdown_replace_image(
            qsync_gen_convert_image(pathname),
            markdown_replace_image(qsync_gen_convert_link(pathname), text),
        ),
        content,
    )


########################################################################
# Qiita Sync CLI
########################################################################


def qsync_subcommand_download(args):
    caller = qiita_create_caller(qsync_get_access_token(args.token))
    qsync_download_all(caller, os.path.join(qsync_get_topdir(), args.dir))


def qsync_subcommand_upload(args):
    caller = qiita_create_caller(qsync_get_access_token(args.token))
    if args.file is not None:
        qsync_upload_doc(caller, args.file)
    else:
        pass


def qsync_subcommand_check(args):
    caller = qiita_create_caller(qsync_get_access_token(args.token))
    local_docs = qsync_get_local_docs(os.path.join(qsync_get_topdir(), args.dir))
    remote_docs = qsync_get_remote_docs(caller)
    for name, doc in local_docs.items():
        print(name)
        print(doc.timestamp.strftime("%Y-%m-%d %H:%M:%S%z"))
        print(
            remote_docs[doc.data.id].timestamp.strftime("%Y-%m-%d %H:%M:%S%z")
            if doc.data.id in remote_docs
            else "New"
        )


def qsync_argparse_download(parser: ArgumentParser):
    parser.set_defaults(func=qsync_subcommand_download)


def qsync_argparse_upload(parser: ArgumentParser):
    parser.add_argument("file", type=str, default=None)
    parser.set_defaults(func=qsync_subcommand_upload)


def qsync_argparse_check(parser: ArgumentParser):
    parser.set_defaults(func=qsync_subcommand_check)


def qsync_argparse() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument("--dir", type=str, default=DEFAULT_MARKDOWN_DIR)
    parser.add_argument("--token", type=str, default=DEFAULT_ACCESS_TOKEN_FILE)
    parser.set_defaults(func=qsync_subcommand_download)

    subparsers = parser.add_subparsers(help="sub-command help")
    qsync_argparse_download(subparsers.add_parser("download", help="download help"))
    qsync_argparse_upload(subparsers.add_parser("upload", help="upload help"))
    qsync_argparse_check(subparsers.add_parser("check", help="check help"))

    return parser


if __name__ == "__main__":
    args = qsync_argparse().parse_args()
    args.func(args)

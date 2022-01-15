#!/usr/bin/env python
#

#
# Git Command Result on GitHub
# ============================
#
# On PR to 'dev' branch
# ---------------------
#
# git rev-parse --show-toplevel
#     /home/runner/work/qiita-sync-test/qiita-sync-test
# git config --get remote.origin.url
#     https://github.com/ryokat3/qiita-sync-test
# git rev-parse --abbrev-ref HEAD
#     HEAD
# git branch --all
#     * (HEAD detached at pull/2/merge)
#       remotes/pull/2/merge
# echo ${GITHUB_REF}
#     refs/pull/2/merge
# git log pull/2/merge -1 --pretty=%cI README.md
#     2022-01-10T23:08:24+00:00
#
#
# On push to 'main'
# -----------------
#
# git rev-parse --show-toplevel
#     /home/runner/work/qiita-sync-test/qiita-sync-test
# git config --get remote.origin.url
#     https://github.com/ryokat3/qiita-sync-test
# git rev-parse --abbrev-ref HEAD
#     main
# git branch --all
#     * main
#       remotes/origin/main
# echo ${GITHUB_REF}
#     refs/heads/main
# git log heads/main -1 --pretty=%cI README.md
#     2022-01-11T07:50:58+09:00
#
#
# NOTE:
#
# How to get branch name (2022-01-11)
# -----------------------------------
#
# When invoked on pull request, the command "git rev-parse --abbrev-ref HEAD"
# return "HEAD", which is not a branch name (HEAD is detached).
#
# Instead, in GitHub Actions, environment variable "GITHUB_REF" has
# "refs/pull/11/merge". "pull/11/merg" seems to be used as branch name.
#
# So, at first try "git rev-parse --abbrev-ref HEAD", and if it's 'HEAD', then get "GITHUB_REF"
#

from __future__ import annotations

import functools
import json
import os
import subprocess
import re
import logging
import sys
import difflib
from argparse import ArgumentParser
from itertools import dropwhile, count, takewhile
from functools import reduce
from pathlib import Path
from datetime import datetime, timezone
from urllib import request
from urllib.parse import urlparse, urlunparse
from urllib.error import HTTPError
from http.client import HTTPResponse
from urllib.request import OpenerDirector
from http import cookiejar
from enum import Enum

from typing import (
    Callable,
    Generic,
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
U = TypeVar("U")

########################################################################
# Const
########################################################################

DEFAULT_ACCESS_TOKEN_FILE = "access_token.txt"
DEFAULT_INCLUDE_GLOB = ['**/*.md']
DEFAULT_EXCLUDE_GLOB = ['**/README.md', '.*/**/*.md']

ACCESS_TOKEN_ENV = "QIITA_ACCESS_TOKEN"

DEFAULT_TITLE = "No Title"
DEFAULT_TAGS = "No Tag"

GITHUB_REF = "GITHUB_REF"

########################################################################
# Logger
########################################################################

logging.basicConfig(
    format='%(asctime)s [%(filename)s:%(lineno)d] %(levelname)-8s :: %(message)s',
    datefmt='%y-%m-%d %H:%M:%S',
    stream=sys.stdout)

logger = logging.getLogger(__name__)

########################################################################
# Exception
########################################################################


class CommandError(Exception):

    def __init__(self, cmd: List[str], result: subprocess.CompletedProcess[bytes]):
        self.cmd = cmd
        self.result = result

    def __str__(self):
        return f"{' '.join(self.cmd)} => {self.result.returncode} ({self.result.stderr})"


class ApplicationError(Exception):
    pass


class ApplicationFileError(Exception):
    pass


########################################################################
# Util
########################################################################


def convert_json_to_bytes(x):
    logger.debug(x)
    return bytes(json.dumps(x), "utf-8")


def exec_command(cmdarglist: List[str]) -> str:
    result = subprocess.run(cmdarglist, stdout=subprocess.PIPE)
    if result.returncode == 0:
        return result.stdout.decode("utf-8").rstrip()
    else:
        raise CommandError(cmdarglist, result)


def update_mtime(filepath: str, t: datetime):
    os.utime(filepath, (t.timestamp(), t.timestamp()))


def is_url(text: str) -> bool:
    try:
        parts = urlparse(text)
        return parts.scheme != '' and parts.netloc != ''
    except Exception:
        return False


def diff_url(target: str, pre: str) -> str:
    return target if len(target) < len(pre) or target[:len(pre)].lower() != pre.lower() else target[len(pre):]


def rel_path(to_path: Path, from_path: Path) -> Path:
    return Path(os.path.relpath(to_path, from_path))


def add_path(path: Path, sub: Path) -> Path:
    return path.joinpath(sub).resolve()


def url_add_path(url: str, sub: Path) -> str:
    parts = urlparse(url)
    return urlunparse(parts._replace(path=str(add_path(Path(parts.path), sub))))


def get_utc(iso8601: str) -> datetime:
    return datetime.strptime(iso8601, "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone.utc)


def to_normalize_body(content: str, linesep: str = os.linesep) -> str:
    return linesep.join(
        reversed(
            list(
                dropwhile(lambda line: line.strip() == '',
                          reversed(list(dropwhile(lambda line: line.strip() == '', content.splitlines())))))))


def str2bool(value: Any) -> bool:
    if not value:
        return False
    return str(value).lower() in ("y", "yes", "t", "true", "on", "1")


def add_indent(value: str, num: int) -> str:
    return num * ' ' + value


########################################################################
# Maybe
########################################################################


class Maybe(Generic[T]):
    _value: Optional[T]

    def __init__(self, value: Optional[T]):
        self._value = value

    def map(self, f: Callable[[T], U]) -> Maybe[U]:
        return Maybe(f(self._value)) if self._value is not None else Maybe(None)

    def flatMap(self, f: Callable[[T], Maybe[U]]) -> Maybe[U]:
        return f(self._value) if self._value is not None else Maybe(None)

    def optionalMap(self, f: Callable[[T], Optional[U]]) -> Maybe[U]:
        return Maybe(f(self._value)) if self._value is not None else Maybe(None)

    def tryCatch(self, f: Callable[[T], U]) -> Maybe[U]:
        try:
            return Maybe(f(self._value)) if self._value is not None else Maybe(None)
        except Exception:
            return Maybe(None)

    def filter(self, p: Callable[[T], bool]) -> Maybe[T]:
        return self if self._value is not None and p(self._value) else Maybe(None)

    def filterNot(self, p: Callable[[T], bool]) -> Maybe[T]:
        return Maybe(None) if self._value is None else Maybe(None) if p(self._value) else self

    def fold(self, on_none: Callable[[], U], on_some: Callable[[T], U]) -> U:
        return on_some(self._value) if self._value is not None else on_none()

    def get(self) -> Optional[T]:
        return self._value

    def getOrElse(self, else_value: T) -> T:
        return self._value if self._value is not None else else_value


########################################################################
# Git
########################################################################


@functools.lru_cache(maxsize=1)
def git_get_topdir() -> str:
    return exec_command("git rev-parse --show-toplevel".split())


@functools.lru_cache(maxsize=1)
def git_get_remote_url() -> str:
    return exec_command("git config --get remote.origin.url".split())


def git_get_committer_date(filename: str) -> str:
    # "%cI", committer date, strict ISO 8601 format
    head = git_get_HEAD()
    branch = f"origin/{head}" if head != "HEAD" else head
    result = exec_command(f"git log {branch} --pretty=%cI".split() + [filename]).splitlines()
    return result[0]


def git_get_committer_datetime(filename: str) -> datetime:
    return get_utc(git_get_committer_date(filename))


@functools.lru_cache(maxsize=1)
def git_get_default_branch() -> str:
    head = git_get_HEAD()
    if head == "HEAD":
        github_ref = os.environ.get(GITHUB_REF)
        if github_ref is None:
            raise ApplicationError("Failed to get Git branch name")
        else:
            return github_ref.replace('refs/', '', 1)
    else:
        return head


@functools.lru_cache(maxsize=1)
def git_get_HEAD() -> str:
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
    with opener.open(restapi_create_request(url, method, headers, content_type, content)) as response:
        return RestApiResponse(response, response.read())


def restapi_build_opener() -> OpenerDirector:
    """Create OpenerDirector instance with cookie processor"""
    return request.build_opener(request.BaseHandler(), request.HTTPCookieProcessor(cookiejar.CookieJar()))


def restapi_json_response(resp: RestApiResponse):
    try:
        return json.loads(resp.data.decode("utf-8")) if resp.data is not None and len(resp.data) > 0 else None
    except json.decoder.JSONDecodeError:
        logger.error(f'JSON Error: {resp.data.decode("utf-8")}')
        return


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
        return restapi_call(
            opener,
            url,
            method,
            headers,
            content_type,
            content_decoder(content) if content is not None else None,
        )

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


def qiita_get_item_page(caller: RESTAPI_CALLER_TYPE, page: int, per_page: int):
    return restapi_json_response(caller(f"{QIITA_API_ENDPOINT}/authenticated_user/items?page={page}&per_page={per_page}", "GET", None))


def qiita_get_item_list(caller: RESTAPI_CALLER_TYPE, per_page: int = 10):
    return reduce(lambda a, b: a + b, filter(None, takewhile(lambda resp: resp is not None and len(resp) != 0,
        map(lambda page: qiita_get_item_page(caller, page, per_page), count(1)))), [])    


def qiita_get_item(caller: RESTAPI_CALLER_TYPE, id: str):
    try:
        return restapi_json_response(caller(f"{QIITA_API_ENDPOINT}/items/{id}", "GET", None))
    except HTTPError as http_error:
        if http_error.code == 404:  # No id in Qiita site
            raise ApplicationFileError(f"{id} not found in Qiita")
        else:
            raise http_error


def qiita_get_authenticated_user(caller: RESTAPI_CALLER_TYPE):
    return restapi_json_response(caller(f"{QIITA_API_ENDPOINT}/authenticated_user", "GET", None))


@functools.lru_cache(maxsize=1)
def qiita_get_authenticated_user_id(caller: RESTAPI_CALLER_TYPE) -> str:
    info = qiita_get_authenticated_user(caller)
    if info is not None and 'id' in info:
        return info['id']
    else:
        raise ApplicationError("Failed to get Qiita ID")


def qiita_post_item(caller: RESTAPI_CALLER_TYPE, data):
    return restapi_json_response(caller(f"{QIITA_API_ENDPOINT}/items", "POST", data))


def qiita_patch_item(caller: RESTAPI_CALLER_TYPE, id: str, data):
    try:
        return restapi_json_response(caller(f"{QIITA_API_ENDPOINT}/items/{id}", "PATCH", data))
    except HTTPError as http_error:
        if http_error.code == 404:  # No id in Qiita site
            raise ApplicationFileError(f"{id} not found in Qiita")
        else:
            raise http_error


def qiita_delete_item(caller: RESTAPI_CALLER_TYPE, id: str):
    try:
        return restapi_json_response(caller(f"{QIITA_API_ENDPOINT}/items/{id}", "DELETE", None))
    except HTTPError as http_error:
        if http_error.code == 404:  # No id in Qiita site
            raise ApplicationFileError(f"{id} not found in Qiita")
        else:
            raise http_error


########################################################################
# Qiita Data
########################################################################


def qiita_get_first_section(body: str) -> Optional[str]:
    m = next(dropwhile(lambda m: m is None, map(lambda line: re.match(r"^#+\s+(.*)$", line), body.splitlines())), None)
    return m.group(1).strip() if m is not None else None


def qiita_get_first_line(body: str) -> Optional[str]:
    m = next(dropwhile(lambda m: m is None, map(lambda line: re.match(r"(\S+)", line), body.splitlines())), None)
    return m.group(1).strip() if m is not None else None


def qiita_get_temporary_title(body: str) -> str:
    # TODO: smarter implementation if exists
    return qiita_get_first_section(body) or qiita_get_first_line(body) or DEFAULT_TITLE


def qiita_get_temporary_tags(_: str) -> str:
    # TODO: smarter implementation if exists
    return DEFAULT_TAGS


class QiitaTag(NamedTuple):
    name: str
    versions: Tuple[str, ...]

    def __str__(self) -> str:
        return (f"{self.name}={'|'.join(self.versions)}" if len(self.versions) > 0 else self.name)

    def __eq__(self, other) -> bool:
        return isinstance(other,
                          QiitaTag) and self.name.lower() == other.name.lower() and self.versions == other.versions

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def toApi(self) -> Dict[str, Any]:
        return {"name": self.name, "versions": self.versions}

    @classmethod
    def fromString(cls, text: str) -> QiitaTag:
        tpl = text.split("=", 1)
        return cls(tpl[0], tuple(sorted(tpl[1].split("|")))) if len(tpl) == 2 else cls(tpl[0], tuple())


class QiitaTags(Tuple[QiitaTag, ...]):

    def __str__(self) -> str:
        return ",".join(map(str, self))

    def toApi(self) -> List[Dict[str, Any]]:
        return [tag.toApi() for tag in self]

    @classmethod
    def fromString(cls, text: str) -> QiitaTags:
        return cls(tuple(sorted(map(lambda s: QiitaTag.fromString(s), text.split(",")))))

    @classmethod
    def fromApi(cls, value) -> QiitaTags:
        return cls(tuple(sorted(map(lambda data: QiitaTag(data["name"], tuple(sorted(data["versions"]))), value))))


class QiitaData(NamedTuple):
    title: str
    tags: QiitaTags
    id: Optional[str]
    private: bool = False

    def __str__(self) -> str:
        return os.linesep.join(
            filter(
                None,
                [
                    f"title:   {self.title}", f"tags:    {str(self.tags)}",
                    f"id:      {self.id}" if self.id is not None else None,
                    f"private: {'true' if self.private else 'false'}"
                ],
            ))

    def __eq__(self, other) -> bool:
        return isinstance(other, QiitaData) and self.title == other.title and self.tags == other.tags

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    @classmethod
    def fromString(cls, text: str, default_title=DEFAULT_TITLE, default_tags=DEFAULT_TAGS) -> QiitaData:
        data = dict({
            "title": default_title,
            "tags": default_tags
        },
                    **dict(
                        map(
                            lambda tpl: (tpl[0].strip(), tpl[1].strip()),
                            map(lambda line: line.split(":", 1),
                                filter(lambda line: re.match(r"^\s*\w+\s*:.*\S", line) is not None,
                                       text.splitlines())))))
        return cls(data["title"], QiitaTags.fromString(data["tags"]), data.get("id"),
                   Maybe(data.get("private")).map(str2bool).getOrElse(False))

    @classmethod
    def fromApi(cls, item) -> QiitaData:
        return cls(title=item["title"], tags=QiitaTags.fromApi(item["tags"]), id=item["id"], private=item["private"])


HEADER_REGEX = re.compile(r"^\s*\<\!\-\-\s(.*?)\s\-\-\>(.*)$", re.MULTILINE | re.DOTALL)


class QiitaArticle(NamedTuple):
    data: QiitaData
    body: str
    timestamp: datetime
    filepath: Optional[Path]

    def __eq__(self, other) -> bool:
        return isinstance(other, QiitaArticle) and self.data == other.data and self.body.strip() == other.body.strip()

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def toText(self) -> str:
        return (f"{os.linesep.join(['<!--', str(self.data), '-->'])}{os.linesep}{self.body}")

    def toApi(self) -> Dict[str, Any]:
        return {
            "body": self.body,
            "tags": self.data.tags.toApi(),
            "title": self.data.title,
            "private": self.data.private
        }

    @classmethod
    def fromFile(cls, filepath: Path) -> QiitaArticle:
        text = filepath.read_text()
        timestamp = qsync_get_timestamp(filepath)
        m = HEADER_REGEX.match(text)
        logger.debug(f'{filepath} :: {m.group(1) if m is not None else "None"}')
        body = Maybe(m).map(lambda m: m.group(2)).getOrElse(text)
        data = QiitaData.fromString(
            Maybe(m).map(lambda m: m.group(1)).getOrElse(""), qiita_get_temporary_title(body),
            qiita_get_temporary_tags(body))

        return cls(data=data, body=body, timestamp=timestamp, filepath=filepath)

    @classmethod
    def fromApi(cls, item) -> QiitaArticle:
        return cls(
            data=QiitaData.fromApi(item), body=item["body"], timestamp=get_utc(item["updated_at"]), filepath=None)


#######################################################################
# Markdown
#######################################################################

CODE_BLOCK_REGEX = re.compile(r"([\r\n]+\s*[\r\n]+(?P<CB>````*).*?[\r\n](?P=CB)\s*[\r\n]+)", re.MULTILINE | re.DOTALL)
CODE_INLINE_REGEX = re.compile(r"((?P<BT>``*)[^\r\n]*?(?P=BT))", re.MULTILINE | re.DOTALL)
MARKDOWN_LINK_REGEX = re.compile(r"(?<!\!)(\[[^\]]*\]\()([^\ \)]+)(.*?\))", re.MULTILINE | re.DOTALL)
MARKDOWN_IMAGE_REGEX = re.compile(r"(\!\[[^\]]*\]\()([^\ \)]+)(.*?\))", re.MULTILINE | re.DOTALL)


def markdown_code_block_split(text: str) -> List[str]:
    return list(
        filter(lambda elm: elm is not None and re.match(r"^````*$", elm) is None, re.split(CODE_BLOCK_REGEX, text)))


def markdown_code_inline_split(text: str) -> List[str]:
    return list(
        filter(
            None,
            filter(lambda elm: elm is not None and re.match(r"^``*$", elm) is None, re.split(CODE_INLINE_REGEX,
                                                                                             text))))


def markdown_replace_block_text(func: Callable[[str], str], text: str):
    return "".join(
        [func(block) if CODE_BLOCK_REGEX.match(block) is None else block for block in markdown_code_block_split(text)])


def markdown_replace_text(func: Callable[[str], str], text: str):
    return markdown_replace_block_text(
        lambda block: "".join(
            [func(x) if CODE_INLINE_REGEX.match(x) is None else x for x in markdown_code_inline_split(block)]), text)


def markdown_replace_link(conv: Callable[[str], str], text: str):
    return re.sub(MARKDOWN_LINK_REGEX, lambda m: "".join([m.group(1), conv(m.group(2)), m.group(3)]), text)


def markdown_replace_image(conv: Callable[[str], str], text: str):
    return re.sub(MARKDOWN_IMAGE_REGEX, lambda m: "".join([m.group(1), conv(m.group(2)), m.group(3)]), text)


#######################################################################
# GitHub
#######################################################################

GITHUB_SSH_URL_REGEX = re.compile(r"^git@github.com:(.*)/(.*)\.git")
GITHUB_HTTPS_URL_REGEX = re.compile(r"^https://github.com/(.*)/(.*)(?:\.git)?")
GITHUB_CONTENT_URL = "https://raw.githubusercontent.com/"


def match_github_ssh_url(text: str) -> Optional[Tuple[str, str]]:
    return Maybe(re.match(GITHUB_SSH_URL_REGEX, text)).map(lambda m: (m.group(1), m.group(2))).get()


def match_github_https_url(text: str) -> Optional[Tuple[str, str]]:
    return Maybe(re.match(GITHUB_HTTPS_URL_REGEX, text)).map(lambda m: (m.group(1), m.group(2))).get()


########################################################################
# Qiita Sync
########################################################################

QIITA_URL_PREFIX = 'https://qiita.com/'


@functools.lru_cache(maxsize=1)
def qsync_on_github_actions() -> bool:
    return os.environ.get(GITHUB_REF) is not None


def qsync_get_timestamp(filepath: Path) -> datetime:
    return git_get_committer_datetime(str(filepath)) if qsync_on_github_actions() \
        else datetime.fromtimestamp(filepath.stat().st_mtime, timezone.utc)


def qsync_get_access_token(token_file: str) -> str:
    filepath = Path(git_get_topdir()).joinpath(token_file)
    if filepath.exists() and filepath.is_file():
        with filepath.open("r") as fp:
            return fp.read().strip()
    else:
        token = os.getenv(ACCESS_TOKEN_ENV)
        if token is not None:
            return token
    # Read from stdin
    # return sys.stdin.readline().rstrip()
    raise ApplicationError("No Qiita Access Token")


def qsync_chdir_git(target: Path):
    if not target.exists():
        raise ApplicationError(f"{target} not exists")
    os.chdir(str(target if target.is_dir() else target.parent))


def qsync_get_local_article(include_patterns: List[str], exclude_patterns: List[str]) -> List[Path]:
    topdir = Path(git_get_topdir())
    return [
        Path(fp).resolve()
        for fp in (functools.reduce(lambda a, b: a | b, [set(topdir.glob(pattern)) for pattern in include_patterns]) -
                   functools.reduce(lambda a, b: a | b, [set(topdir.glob(pattern)) for pattern in exclude_patterns]))
    ]


class QiitaSync(NamedTuple):
    caller: RESTAPI_CALLER_TYPE
    git_user: str
    git_repository: str
    git_branch: str
    git_dir: str
    qiita_id: str
    atcl_path_map: Dict[Path, QiitaArticle]
    atcl_id_map: Dict[str, QiitaArticle]

    @classmethod
    def getInstance(cls, qiita_token: str, file_list: List[Path]) -> QiitaSync:
        url = git_get_remote_url()
        user_repo = match_github_https_url(url) or match_github_ssh_url(url) if url is not None else None
        if user_repo is None:
            raise ApplicationError(f"{url} is not GitHub")
        atcl_list = [QiitaArticle.fromFile(fp) for fp in file_list if fp.is_file()]
        caller = qiita_create_caller(qiita_token)

        return cls(caller, user_repo[0], user_repo[1], git_get_default_branch(), git_get_topdir(),
                   qiita_get_authenticated_user_id(caller),
                   dict([(atcl.filepath, atcl) for atcl in atcl_list if atcl.filepath is not None]),
                   dict([(atcl.data.id, atcl) for atcl in atcl_list if atcl.data.id is not None]))

    @property
    def github_url(self):
        return f"{GITHUB_CONTENT_URL}{self.git_user}/{self.git_repository}/{self.git_branch}/"

    def getGitHubUrl(self, pathname: Path) -> Optional[str]:
        try:
            _relative_path = pathname.resolve().relative_to(self.git_dir).as_posix()
            relative_path = _relative_path if _relative_path != "." else ""
            return f"{self.github_url}{relative_path}"
        except Exception:
            return None

    def getQiitaUrl(self, id: str) -> str:
        return f"{QIITA_URL_PREFIX}{self.qiita_id}/items/{id}"

    def getArticleDir(self, article: QiitaArticle) -> Path:
        return article.filepath.parent if article.filepath is not None else Path(self.git_dir)

    def getArticleById(self, id: str) -> Optional[QiitaArticle]:
        return self.atcl_id_map[id] if id in self.atcl_id_map else None

    def getFilePathById(self, id: str) -> Optional[Path]:
        return self.atcl_id_map[id].filepath if id in self.atcl_id_map else None

    def getArticleByPath(self, target: Path) -> Dict[Path, QiitaArticle]:
        if Path(self.git_dir) == target:
            return self.atcl_path_map
        else:
            return dict([(path, article)
                         for path, article in self.atcl_path_map.items()
                         if str(path).startswith(str(target.resolve()))])

    def toLocalImageLink(self, link: str, article: QiitaArticle) -> str:
        return Maybe(article.filepath).map(lambda fp: fp.resolve()).flatMap(
            lambda filepath: Maybe(diff_url(link, self.github_url)).filter(lambda x: x != link).map(lambda diff: str(
                rel_path(Path(self.git_dir).joinpath(diff), filepath.parent)))).getOrElse(link)

    def toLocaMarkdownlLink(self, link: str, article: QiitaArticle) -> str:
        return Maybe(article.filepath).map(lambda fp: fp.resolve()).flatMap(
            lambda filepath: Maybe(diff_url(link, f"{QIITA_URL_PREFIX}{self.qiita_id}/items/")).filter(
                lambda x: x != link).map(lambda id: Maybe(self.getFilePathById(id)).map(lambda fp: str(
                    rel_path(fp, filepath.parent))).getOrElse(f"{id}.md"))).getOrElse(link)

    def toLocalFormat(self, article: QiitaArticle) -> QiitaArticle:

        def convert_image_link(text: str, article: QiitaArticle) -> str:
            return markdown_replace_image(lambda link: self.toLocalImageLink(link, article), text)

        def convert_link(text: str) -> str:
            return markdown_replace_link(lambda link: self.toLocaMarkdownlLink(link, article), text)

        return article._replace(
            body=to_normalize_body(
                markdown_replace_text(lambda text: convert_image_link(convert_link(text), article), article.body)))

    def toGlobalImageLink(self, link: str, article: QiitaArticle) -> str:
        return Maybe(link).filterNot(
            os.path.isabs).filterNot(is_url).map(lambda x: add_path(self.getArticleDir(article), Path(x))).optionalMap(
                lambda p: self.getGitHubUrl(p)).getOrElse(link)

    def toGlobalMarkdownLink(self, link: str, article: QiitaArticle):
        return Maybe(link).filterNot(os.path.isabs).filterNot(is_url).map(
            lambda x: add_path(self.getArticleDir(article), Path(x))).filter(lambda p: p.is_file()).map(
                QiitaArticle.fromFile).optionalMap(lambda article: article.data.id).map(
                    self.getQiitaUrl).getOrElse(link)

    def toGlobalFormat(self, article: QiitaArticle) -> QiitaArticle:

        def convert_image_link(text: str) -> str:
            return markdown_replace_image(lambda link: self.toGlobalImageLink(link, article), text)

        def convert_link(text: str) -> str:
            return markdown_replace_link(lambda link: self.toGlobalMarkdownLink(link, article), text)

        return article._replace(
            body=to_normalize_body(
                markdown_replace_text(lambda text: convert_image_link(convert_link(text)), article.body), '\n'))

    def download(self, article: QiitaArticle):
        if article.data.id is not None:
            Maybe(qiita_get_item(self.caller, article.data.id)).map(
                QiitaArticle.fromApi).map(lambda x: x._replace(filepath=article.filepath)).map(self.save)
        else:
            pass

    def upload(self, article: QiitaArticle):
        if article.data.id is not None:
            qiita_patch_item(self.caller, article.data.id, self.toGlobalFormat(article).toApi())
        else:
            Maybe(qiita_post_item(
                self.caller,
                self.toGlobalFormat(article).toApi())).map(QiitaArticle.fromApi).map(
                    lambda x: article._replace(data=x.data, timestamp=x.timestamp)).map(lambda x: self.save(x))

    def save(self, article: QiitaArticle):
        filepath = article.filepath or Path(self.git_dir).joinpath(f"{article.data.id or 'unknown'}.md")

        with filepath.open("w") as fp:
            fp.write(self.toLocalFormat(article._replace(filepath=filepath)).toText())

    def delete(self, article: QiitaArticle):
        if article.data.id is not None:
            qiita_delete_item(self.caller, article.data.id)
        else:
            raise ApplicationFileError(f"{article.filepath} has no id")


########################################################################
# Qiita Sync CLI
########################################################################


class SyncStatus(Enum):
    LOCAL_ONLY = 1
    GLOBAL_ONLY = 2
    LOCAL_NEW = 3
    GLOBAL_NEW = 4
    GLOBAL_DELETED = 5
    SYNC = 6
    CONFLICT = 7


def qsync_check_status_local_article(
        qsync: QiitaSync, local_article: QiitaArticle,
        get_global_article: Callable[[str], Optional[QiitaArticle]]) -> Tuple[SyncStatus, Optional[QiitaArticle]]:
    if local_article.data.id is None:
        return (SyncStatus.LOCAL_ONLY, None)
    else:
        global_article = get_global_article(local_article.data.id)
        if global_article is None:
            return (SyncStatus.GLOBAL_DELETED, None)
        elif qsync.toLocalFormat(local_article) == qsync.toLocalFormat(global_article):
            return (SyncStatus.SYNC, global_article)
        elif local_article.timestamp > global_article.timestamp:
            return (SyncStatus.LOCAL_NEW, global_article)
        elif local_article.timestamp < global_article.timestamp:
            return (SyncStatus.GLOBAL_NEW, global_article)
        else:
            return (SyncStatus.CONFLICT, global_article)


def qsync_subcommand_download(qsync: QiitaSync, target: Path):
    logger.debug(f"{target} download")
    for global_article in qsync.getArticleByPath(target).values():
        qsync.download(global_article)


def qsync_subcommand_upload(qsync: QiitaSync, target: Path):
    logger.debug(f"{target} upload")
    for article in qsync.getArticleByPath(target).values():
        try:
            qsync.upload(article)
        except ApplicationError as err:
            print(err)


def qsync_subcommand_delete(qsync: QiitaSync, target: Path):
    logger.debug(f"{target} delete")
    for article in qsync.getArticleByPath(target).values():
        try:
            qsync.delete(article)
        except ApplicationError as err:
            print(err)


def qsync_str_diff(qsync: QiitaSync, local_article: QiitaArticle, global_article: QiitaArticle) -> List[str]:
    return list(
        difflib.unified_diff(
            qsync.toLocalFormat(local_article).body.splitlines(),
            qsync.toLocalFormat(global_article).body.splitlines()))


def qsync_str_timestamp(article: QiitaArticle) -> str:
    return article.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f%z")


def qsync_str_local_only(article: QiitaArticle) -> str:
    return f'{article.data.title}({article.filepath.name}) :: Local Only'


def qsync_str_global_only(article: QiitaArticle) -> str:
    return f'{article.data.title}({article.data.id}) :: Qiita Only'


def qsync_str_local_new(article: QiitaArticle) -> str:
    return f'{article.data.title} => Local is new ({qsync_str_timestamp(article)})'


def qsync_str_global_new(article: QiitaArticle) -> str:
    return f'{article.data.title} => Qiita is new ({qsync_str_timestamp(article)})'


def qsync_str_global_deleted(article: QiitaArticle) -> str:
    return f'{article.data.title}({article.data.id}) => Not found in Qiita'


def qsync_str_conflict(article: QiitaArticle) -> str:
    return f'{article.data.title} => Conflict'


def qsync_do_check(qsync: QiitaSync, status: SyncStatus, local_article: QiitaArticle,
                   global_article: Optional[QiitaArticle]):
    if status == SyncStatus.LOCAL_ONLY:
        print(qsync_str_local_only(local_article))
    elif status == SyncStatus.GLOBAL_ONLY and global_article is not None:
        print(qsync_str_global_only(global_article))
    elif status == SyncStatus.LOCAL_NEW and global_article is not None:
        print(qsync_str_local_new(local_article))
        print(os.linesep.join(qsync_str_diff(qsync, local_article, global_article)))
    elif status == SyncStatus.GLOBAL_NEW and global_article is not None:
        print(qsync_str_global_new(global_article))
        print(os.linesep.join(qsync_str_diff(qsync, local_article, global_article)))
    elif status == SyncStatus.GLOBAL_DELETED:
        print(qsync_str_global_deleted(local_article))
    elif status == SyncStatus.SYNC:
        pass
    elif status == SyncStatus.CONFLICT:
        print(qsync_str_conflict(local_article))
    else:
        raise ApplicationError(f"{local_article.filepath}: Unknown status")


def qsync_do_sync(qsync: QiitaSync, status: SyncStatus, local_article: QiitaArticle,
                  global_article: Optional[QiitaArticle]):
    if status == SyncStatus.LOCAL_ONLY:
        qsync.upload(local_article)
    elif status == SyncStatus.GLOBAL_ONLY and global_article is not None:
        qsync.save(global_article)
    elif status == SyncStatus.LOCAL_NEW:
        qsync.upload(local_article)
    elif status == SyncStatus.GLOBAL_NEW and global_article is not None:
        qsync.save(global_article._replace(filepath=local_article.filepath))
    elif status == SyncStatus.GLOBAL_DELETED:
        print(qsync_str_global_deleted(local_article))
    elif status == SyncStatus.SYNC:
        pass
    elif status == SyncStatus.CONFLICT:
        print(qsync_str_conflict(local_article))
    else:
        raise ApplicationError(f"{local_article.filepath}: Unknown status")


def qsync_do_purge(qsync: QiitaSync, status: SyncStatus, local_article: QiitaArticle,
                  global_article: Optional[QiitaArticle]):
    if local_article.data.private:
        qsync.delete(local_article)
        if local_article.filepath is not None:
            os.remove(local_article.filepath)
    elif status == SyncStatus.LOCAL_ONLY and local_article.filepath is not None:
        os.remove(local_article.filepath)
    elif status == SyncStatus.GLOBAL_ONLY and global_article is not None and global_article.data.id is not None:
        qiita_delete_item(qsync.caller, global_article.data.id)
    elif status == SyncStatus.LOCAL_NEW:
        qsync.upload(local_article)
    elif status == SyncStatus.GLOBAL_NEW and global_article is not None:
        qsync.save(global_article._replace(filepath=local_article.filepath))
    elif status == SyncStatus.GLOBAL_DELETED and local_article.filepath is not None:
        os.remove(local_article.filepath)
    elif status == SyncStatus.SYNC:
        pass
    elif status == SyncStatus.CONFLICT:
        qsync.upload(local_article)
    else:
        raise ApplicationError(f"{local_article.filepath}: Unknown status")


def qsync_foreach(qsync: QiitaSync, target: Path,
                  handler: Callable[[QiitaSync, SyncStatus, QiitaArticle, Optional[QiitaArticle]], Any]):
    if target == Path(qsync.git_dir):
        global_article_dict = dict([
            (article.data.id, article)
            for article in [QiitaArticle.fromApi(elem) for elem in (qiita_get_item_list(qsync.caller) or [])]
            if article.data.id is not None
        ])

        for local_article in qsync.atcl_path_map.values():
            resp = qsync_check_status_local_article(qsync, local_article, lambda id: global_article_dict.get(id))
            handler(qsync, resp[0], local_article, resp[1])
        for id, global_article in global_article_dict.items():
            if qsync.getArticleById(id) is None:
                handler(qsync, SyncStatus.GLOBAL_ONLY, global_article, global_article)
    else:
        for local_article in [
                article for article in qsync.atcl_path_map.values()
                if article.filepath is not None and article.filepath.is_relative_to(target)
        ]:
            try:
                resp = qsync_check_status_local_article(
                    qsync, local_article,
                    lambda id: Maybe(qiita_get_item(qsync.caller, id)).map(QiitaArticle.fromApi).get())
                handler(qsync, resp[0], local_article, resp[1])
            except ApplicationFileError:
                handler(qsync, SyncStatus.GLOBAL_DELETED, local_article, None)


def qsync_subcommand_check(qsync: QiitaSync, target: Path):
    qsync_foreach(qsync, target, qsync_do_check)


def qsync_subcommand_sync(qsync: QiitaSync, target: Path):
    qsync_foreach(qsync, target, qsync_do_sync)


def qsync_subcommand_purge(qsync: QiitaSync, target: Path):
    qsync_foreach(qsync, target, qsync_do_purge)


def qsync_argparse() -> ArgumentParser:

    def common_arg(parser: ArgumentParser) -> ArgumentParser:
        parser.add_argument("-t", "--token", default=DEFAULT_ACCESS_TOKEN_FILE, help="authentication token")
        parser.add_argument("-i", "--include", nargs='*', default=DEFAULT_INCLUDE_GLOB, help="include glob")
        parser.add_argument("-e", "--exclude", nargs='*', default=DEFAULT_EXCLUDE_GLOB, help="exclude glob")
        parser.add_argument("-v", "--verbose", action='store_true', help="debug logging")
        parser.add_argument("target", default='.', help="target Qiita article (file or directory)")

        return parser

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(help="sub-command help")

    common_arg(subparsers.add_parser("download", help="download help")).set_defaults(func=qsync_subcommand_download)
    common_arg(subparsers.add_parser("upload", help="upload help")).set_defaults(func=qsync_subcommand_upload)
    common_arg(subparsers.add_parser("check", help="check help")).set_defaults(func=qsync_subcommand_check)
    common_arg(subparsers.add_parser("delete", help="delete help")).set_defaults(func=qsync_subcommand_delete)    
    common_arg(subparsers.add_parser("sync", help="sync help")).set_defaults(func=qsync_subcommand_sync)
    common_arg(subparsers.add_parser("purge", help="purge help")).set_defaults(func=qsync_subcommand_purge)

    return parser


def qsync_init(args) -> QiitaSync:
    access_token = qsync_get_access_token(args.token)
    local_article = qsync_get_local_article(args.include, args.exclude)

    return QiitaSync.getInstance(access_token, local_article)


def qsync_main():
    cwd = os.getcwd()
    try:
        args = qsync_argparse().parse_args()
        logger.setLevel(logging.DEBUG if args.verbose else logging.ERROR)
        target = Path(args.target).resolve()
        qsync_chdir_git(target if target.is_dir() else target.parent)
        args.func(qsync_init(args), target)
    except CommandError as err:
        print(err)
    except ApplicationError as err:
        print(err)
    except ApplicationFileError as err:
        print(err)
    except HTTPError as http_error:
        print(http_error)
    finally:
        os.chdir(cwd)


if __name__ == "__main__":
    qsync_main()

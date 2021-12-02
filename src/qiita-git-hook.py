#!/usr/bin/env python3
#

import json
import os

from urllib import request
from urllib.error import HTTPError
from http.client import HTTPResponse
from urllib.request import OpenerDirector
from http import cookiejar

from typing import Union, Callable, Optional, TypeVar, NamedTuple, Dict, Any, List


T = TypeVar('T')

########################################################################
# Util
########################################################################


def convert_json_to_bytes(x):
    return bytes(json.dumps(x), 'utf-8')

########################################################################
# Rest API
########################################################################


class RestApiResponse(NamedTuple):
    header: HTTPResponse
    data: bytes


RESTAPI_CALLER_TYPE = Callable[[str, str, Optional[T]], RestApiResponse]


def reastapi_add_content_type(_headers: Optional[Dict[str, str]], content_type: Optional[str], content: Optional[bytes]) -> Dict[str, str]:
    '''Add 'Content-Type' header if exists'''
    headers = _headers.copy() if _headers is not None else {}
    if content_type is not None and content is not None and len(content) != 0:
        headers['Content-Type'] = content_type
    return headers


def restapi_create_request(url: str, method: str, headers: Optional[Dict[str, str]], content_type: Optional[str], content: Optional[bytes]) -> request.Request:
    '''Create Request instance including content if exists'''
    return request.Request(url, data=content if content is not None and len(content) > 0 else None, method=method, headers=reastapi_add_content_type(headers, content_type, content))


def restapi_call(opener: OpenerDirector, url: str, method: str, headers: Optional[Dict[str, str]], content_type: Optional[str] = None, content: Optional[bytes] = None) -> RestApiResponse:
    '''Execute HTTP Request with OpenerDirector'''
    with opener.open(restapi_create_request(url, method, headers, content_type, content)) as response:
        return RestApiResponse(response, response.read())


def restapi_build_opener() -> OpenerDirector:
    '''Create OpenerDirector instance with cookie processor'''
    return request.build_opener(request.BaseHandler(), request.HTTPCookieProcessor(cookiejar.CookieJar()))


########################################################################
# Qiita API
########################################################################


QIITA_API_ENDPOINT = "https://qiita.com/api/v2"


def qiita_build_caller(opener: OpenerDirector, content_type: str, headers: Optional[Dict[str, str]] = None, content_decoder=lambda x: x) -> RESTAPI_CALLER_TYPE:
    def _(url: str, method: str, content: Optional[T] = None) -> RestApiResponse:
        try:
            return restapi_call(opener, url, method, headers, content_type, content_decoder(content) if content is not None else None)
        except HTTPError as http_error:
            if http_error.code == 429:  # Too much Request                
                return _(url, method, content)
            else:
                raise http_error
    return _


def qiita_create_caller(auth_token: str):
    return qiita_build_caller(restapi_build_opener(), "application/json", {
        "Cache-Control": "no-cache, no-store",
        "Authorization": f"Bearer {auth_token}"
    }, convert_json_to_bytes)


def qiita_get_domain_list(caller: RESTAPI_CALLER_TYPE):
    resp: RestApiResponse = caller(f'{QIITA_API_ENDPOINT}/authenticated_user/itemss', "GET", None)
    return resp    


if __name__ == '__main__':
    print(os.getcwd())

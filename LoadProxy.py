#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代理模块 - 根据环境变量 proxy_server 自动为常用 HTTP 请求配置代理
创建日期：2026-04-24
模块作者：3iXi
作者主页：https://github.com/3ixi
使用方法：搭建好 SS 或 Clash 服务后，在环境变量 proxy_server 中填入 http:// 或 https:// 开头的代理地址（比如http://127.0.0.1:7890），脚本导入本模块后会自动应用代理。
"""

import inspect
import os
from functools import wraps
from typing import Any, Optional
from urllib.parse import urlparse

# ==================== 代理配置 ====================
PROXY_ENV_NAME = "proxy_server"
PROXY_ENV_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")


# ==================== 代理加载类 ====================
class ProxyLoader:

    def __init__(self):
        self.proxy_url = os.getenv(PROXY_ENV_NAME, "").strip()
        self.enabled = False
        self.applied = False
        self.requests_patched = False
        self.httpx_patched = False
        self.aiohttp_patched = False

    def is_valid_proxy_url(self, value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def set_proxy_env(self) -> None:
        for name in PROXY_ENV_KEYS:
            os.environ[name] = self.proxy_url

    def get_proxy(self) -> Optional[str]:
        return self.proxy_url if self.enabled else None

    def get_requests_proxies(self) -> Optional[dict[str, str]]:
        if not self.enabled:
            return None

        return {"http": self.proxy_url, "https": self.proxy_url}

    def patch_requests(self) -> None:
        if self.requests_patched:
            return

        try:
            import requests
        except Exception:
            return

        original_request = requests.Session.request
        if getattr(original_request, "_load_proxy_patched", False):
            self.requests_patched = True
            return

        @wraps(original_request)
        def request_with_proxy(session: Any, method: str, url: str, **kwargs: Any) -> Any:
            if "proxies" not in kwargs and not getattr(session, "proxies", None):
                kwargs["proxies"] = self.get_requests_proxies()

            return original_request(session, method, url, **kwargs)

        request_with_proxy._load_proxy_patched = True
        requests.Session.request = request_with_proxy
        self.requests_patched = True

    def httpx_proxy_kw(self, callable_obj: Any) -> Optional[str]:
        try:
            params = inspect.signature(callable_obj).parameters
        except (TypeError, ValueError):
            return None

        if "proxies" in params:
            return "proxies"
        if "proxy" in params:
            return "proxy"

        return None

    def inject_httpx_proxy(self, kwargs: dict[str, Any], proxy_kw: Optional[str]) -> None:
        if proxy_kw is None:
            return

        other_kw = "proxy" if proxy_kw == "proxies" else "proxies"
        if proxy_kw in kwargs or other_kw in kwargs:
            return

        if kwargs.get("transport") is not None or kwargs.get("mounts") is not None:
            return

        kwargs[proxy_kw] = self.proxy_url

    def patch_httpx_request(self, httpx: Any) -> None:
        original_request = httpx.request
        if getattr(original_request, "_load_proxy_patched", False):
            return

        request_proxy_kw = self.httpx_proxy_kw(original_request)

        @wraps(original_request)
        def request_with_proxy(method: str, url: Any, **kwargs: Any) -> Any:
            self.inject_httpx_proxy(kwargs, request_proxy_kw)
            return original_request(method, url, **kwargs)

        request_with_proxy._load_proxy_patched = True
        httpx.request = request_with_proxy

    def patch_httpx_client(self, client_cls: Any) -> None:
        original_init = client_cls.__init__
        if getattr(original_init, "_load_proxy_patched", False):
            return

        proxy_kw = self.httpx_proxy_kw(original_init)

        @wraps(original_init)
        def init_with_proxy(instance: Any, *args: Any, **kwargs: Any) -> None:
            self.inject_httpx_proxy(kwargs, proxy_kw)
            original_init(instance, *args, **kwargs)

        init_with_proxy._load_proxy_patched = True
        client_cls.__init__ = init_with_proxy

    def patch_httpx(self) -> None:
        if self.httpx_patched:
            return

        try:
            import httpx
        except Exception:
            return

        self.patch_httpx_request(httpx)
        for client_name in ("Client", "AsyncClient"):
            client_cls = getattr(httpx, client_name, None)
            if client_cls is not None:
                self.patch_httpx_client(client_cls)

        self.httpx_patched = True

    def patch_aiohttp(self) -> None:
        if self.aiohttp_patched:
            return

        try:
            import aiohttp
        except Exception:
            return

        original_init = aiohttp.ClientSession.__init__
        if getattr(original_init, "_load_proxy_patched", False):
            self.aiohttp_patched = True
            return

        try:
            params = inspect.signature(original_init).parameters
        except (TypeError, ValueError):
            params = {}

        supports_proxy = "proxy" in params
        supports_trust_env = "trust_env" in params

        @wraps(original_init)
        def init_with_proxy(session: Any, *args: Any, **kwargs: Any) -> None:
            if supports_proxy and "proxy" not in kwargs and not kwargs.get("trust_env", False):
                kwargs["proxy"] = self.proxy_url
            elif not supports_proxy and supports_trust_env and "trust_env" not in kwargs:
                kwargs["trust_env"] = True

            original_init(session, *args, **kwargs)

        init_with_proxy._load_proxy_patched = True
        aiohttp.ClientSession.__init__ = init_with_proxy
        self.aiohttp_patched = True

    def apply(self) -> bool:
        if self.applied:
            return self.enabled

        self.applied = True
        if not self.proxy_url:
            return False

        if not self.is_valid_proxy_url(self.proxy_url):
            print(f"[代理] 已忽略无效的 {PROXY_ENV_NAME}，请填写 http:// 或 https:// 开头的代理地址")
            return False

        self.enabled = True
        print(f"[代理] 已启用代理服务器：{self.proxy_url}")
        self.set_proxy_env()
        self.patch_requests()
        self.patch_httpx()
        self.patch_aiohttp()
        return True


_proxy_loader = ProxyLoader()


def is_enabled() -> bool:
    return _proxy_loader.enabled


def get_proxy() -> Optional[str]:
    return _proxy_loader.get_proxy()


def get_requests_proxies() -> Optional[dict[str, str]]:
    return _proxy_loader.get_requests_proxies()


def apply() -> bool:
    return _proxy_loader.apply()


apply()


# ==================== 功能测试 ====================
if __name__ == "__main__":
    print("[测试] LoadProxy代理模块测试")
    print("=" * 30)

    if is_enabled():
        print(f"[成功] 代理已启用: {get_proxy()}")
    else:
        print(f"[提示] 代理未启用，请检查环境变量 {PROXY_ENV_NAME}")

#!/usr/bin/env python3
# -*- coding：utf-8 -*-
"""
@脚本名称：ikuuu爱坤机场签到脚本（自动过验证版）
@创建时间：2025-03-12
@脚本作者：3iXi（https://github.com/3ixi）
@脚本功能：自动登录+自动签到+获取流量信息
@脚本版本：1.3.2
@更新时间：2026-05-09
@需要依赖：requests PyYAML pycryptodome beautifulsoup4
@脚本描述：
     1.访问https://ikuuu.org 注册账号
	 2.创建环境变量ikuuu，变量值是邮箱&密码，密码中不能包含&，否则会报错，示例：tony@qq.com&aaa112233..
	 3.如果请求接口失败，国内主机可配合LoadProxy.py模块来通过Clash等服务代理请求
"""

import importlib.util
import json
import os
import sys
import io
import yaml
import base64
import shutil
import subprocess
import random
import time
import hashlib
import binascii
import urllib.parse
import re
from uuid import uuid4
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from Crypto.PublicKey.RSA import construct
from Crypto.Cipher import PKCS1_v1_5
from bs4 import BeautifulSoup

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
except Exception:
    pass

try:
    from SendNotify import capture_output
except Exception as exc:
    print(f"[警告] 通知模块 SendNotify.py 导入失败：{exc}，将跳过通知推送。")

    def capture_output(title: str = "脚本运行结果"):
        def decorator(func):
            return func

        return decorator


def _load_optional_proxy_module() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    proxy_path = os.path.join(script_dir, "LoadProxy.py")
    if not os.path.exists(proxy_path):
        return

    try:
        spec = importlib.util.spec_from_file_location("LoadProxy", proxy_path)
        if spec is None or spec.loader is None:
            print("[警告] 代理模块加载失败：无法创建模块规格，将通过直连发起请求。")
            return
        module = importlib.util.module_from_spec(spec)
        sys.modules["LoadProxy"] = module
        spec.loader.exec_module(module)
    except Exception as exc:
        print(f"[警告] 代理模块导入失败：{exc}，将通过直连发起请求。")


_load_optional_proxy_module()

import requests

def get_accounts_from_env():
    accounts_str = os.getenv('ikuuu', '')
    if not accounts_str.strip():
        raise ValueError("未找到环境变量 'ikuuu'")
    
    accounts = []
    for line_no, original_line in enumerate(accounts_str.splitlines(), start=1):
        line = original_line.strip()
        if not line:
            continue
        if line.count('&') != 1:
            print(f"[警告] 第 {line_no} 行账号已忽略：格式应为 邮箱&密码")
            continue
        email, passwd = line.split('&', 1)
        email = email.strip()
        passwd = passwd.strip()
        if not email or not passwd:
            print(f"[警告] 第 {line_no} 行账号已忽略：邮箱或密码为空")
            continue
        accounts.append({'email': email, 'passwd': passwd})
    
    print(f"本轮获取到 {len(accounts)} 个账号")
    return accounts

DOMAINS = ['ikuuu.org', 'ikuuu.pw', 'ikuuu.de', 'ikuuu.one']
DOMAIN_DISCOVERY_URL = 'https://ikuuu.ch/'
DOMAIN_DISCOVERY_HOST = 'ikuuu.ch'
_AVAILABLE_DOMAIN_CACHE = None

header = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'x-requested-with': 'XMLHttpRequest',
    'connection': 'keep-alive'
}

class LotParser:
    def __init__(self):
        self.mapping = {"n[3:5]+n[9:11]": "n[7:12]"}
        self.lot = []
        self.lot_res = []
        for k, v in self.mapping.items():
            self.lot = self._parse(k)
            self.lot_res = self._parse(v)

    @staticmethod
    def _parse_slice(s):
        return [int(x) for x in s.split(':')]

    @staticmethod
    def _extract(part):
        res = re.search(r'\[(.*?)\]', part)
        return res.group(1) if res else ""

    def _parse(self, s):
        parts = s.split('+.+')
        parsed = []
        for part in parts:
            if '+' in part:
                subs = part.split('+')
                parsed_subs = [self._parse_slice(self._extract(sub)) for sub in subs]
                parsed.append(parsed_subs)
            else:
                extracted = self._extract(part)
                if extracted:
                    parsed.append([self._parse_slice(extracted)])
        return parsed

    @staticmethod
    def _build_str(parsed, num):
        result = []
        for p in parsed:
            current = []
            for s in p:
                start = s[0]
                end = s[1] + 1 if len(s) > 1 else start + 1
                current.append(num[start:end])
            result.append(''.join(current))
        return '.'.join(result)

    def get_dict(self, lot_number):
        i = self._build_str(self.lot, lot_number)
        r = self._build_str(self.lot_res, lot_number)
        parts = i.split('.')
        a = {}
        current = a
        for idx, part in enumerate(parts):
            if idx == len(parts) - 1:
                current[part] = r
            else:
                current[part] = current.get(part, {})
                current = current[part]
        return a

class Signer:
    encryptor_pubkey = construct((
        int("00C1E3934D1614465B33053E7F48EE4EC87B14B95EF88947713D25EECBFF7E74C7977D02DC1D9451F79DD5D1C10C29ACB6A9B4D6FB7D0A0279B6719E1772565F09AF627715919221AEF91899CAE08C0D686D748B20A3603BE2318CA6BC2B59706592A9219D0BF05C9F65023A21D2330807252AE0066D59CEEFA5F2748EA80BAB81".lower(),
            16),
        int("10001", 16))
    )
    lotParser = LotParser()

    @staticmethod
    def rand_uid():
        result = ''
        for _ in range(4):
            result += hex(int(65536 * (1 + random.random())))[2:].zfill(4)[-4:]
        return result

    @staticmethod
    def encrypt_symmetrical_1(o_text, random_str):
        key = random_str.encode('utf-8')
        iv = b'0000000000000000'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted_bytes = cipher.encrypt(pad(o_text.encode('utf-8'), AES.block_size))
        return encrypted_bytes

    @staticmethod
    def encrypt_asymmetric_1(message: str) -> str:
        message_bytes = message.encode('utf-8')
        cipher = PKCS1_v1_5.new(Signer.encryptor_pubkey)
        encrypted_bytes = cipher.encrypt(message_bytes)
        encrypted_hex = binascii.hexlify(encrypted_bytes).decode('utf-8')
        return encrypted_hex

    @staticmethod
    def encrypt_w(raw_input, pt) -> str:
        if not pt or '0' == pt:
            return urllib.parse.quote_plus(raw_input)
        random_uid = Signer.rand_uid()
        if pt == "1":
            enc_key = Signer.encrypt_asymmetric_1(random_uid)
            enc_input = Signer.encrypt_symmetrical_1(raw_input, random_uid)
            return binascii.hexlify(enc_input).decode() + enc_key
        raise NotImplementedError("Encryption pt != 1 not implemented")

    @staticmethod
    def generate_pow(lot_number_pow, captcha_id_pow, hash_func, hash_version, bits, date, empty) -> dict:
        bit_remainder = bits % 4
        bit_division = bits // 4
        prefix = '0' * bit_division
        pow_string = f"{hash_version}|{bits}|{hash_func}|{date}|{captcha_id_pow}|{lot_number_pow}|{empty}|"
        while True:
            h = Signer.rand_uid()
            combined = pow_string + h
            hashed_value = ""
            if hash_func == 'md5':
                hashed_value = hashlib.md5(combined.encode('utf-8')).hexdigest()
            elif hash_func == 'sha1':
                hashed_value = hashlib.sha1(combined.encode('utf-8')).hexdigest()
            elif hash_func == 'sha256':
                hashed_value = hashlib.sha256(combined.encode('utf-8')).hexdigest()
            
            if hashed_value.startswith(prefix):
                if bit_remainder == 0:
                    return {'pow_msg': pow_string + h, 'pow_sign': hashed_value}
                else:
                    length = len(prefix)
                    threshold = None
                    if bit_remainder == 1:
                        threshold = 7
                    elif bit_remainder == 2:
                        threshold = 3
                    elif bit_remainder == 3:
                        threshold = 1
                    if length <= threshold:
                        return {'pow_msg': pow_string + h, 'pow_sign': hashed_value}

    @staticmethod
    def build_lot_parser(mapping: dict):
        parser = LotParser()
        parser.mapping = mapping
        parser.lot = []
        parser.lot_res = []
        for k, v in mapping.items():
            parser.lot = parser._parse(k)
            parser.lot_res = parser._parse(v)
        return parser

    @staticmethod
    def generate_w(data: dict, captcha_id: str, risk_type: str, constants: dict = None):
        constants = constants or {
            "abo": {"1a8R": "daC2"},
            "mapping": {"n[3:5]+n[9:11]": "n[7:12]"},
        }
        lot_number = data['lot_number']
        pow_detail = data['pow_detail']
        parser = Signer.build_lot_parser(constants["mapping"])
        base = {
            **constants["abo"],
            **Signer.generate_pow(lot_number, captcha_id, pow_detail['hashfunc'], pow_detail['version'],
                                   pow_detail['bits'], pow_detail['datetime'], ""),
            **parser.get_dict(lot_number),
            "biht": "1426265548",
            "device_id": "",
            "em": {"cp": 0, "ek": "11", "nt": 0, "ph": 0, "sc": 0, "si": 0, "wd": 1},
            "gee_guard": {"roe": {"auh": "3", "aup": "3", "cdc": "3", "egp": "3", "res": "3", "rew": "3", "sep": "3", "snh": "3"}},
            "ep": "123",
            "geetest": "captcha",
            "lang": "zh",
            "lot_number": lot_number,
        }
        return Signer.encrypt_w(json.dumps(base), data["pt"])


class GeetestSolver:
    BUILTIN_CONSTANTS = [
        {
            "label": "legacy",
            "abo": {"1a8R": "daC2"},
            "mapping": {"n[3:5]+n[9:11]": "n[7:12]"},
        },
        {
            "label": "alt",
            "abo": {"4MTT": "0Qh0"},
            "mapping": {"(n[19:24])+.+(n[23:30])+.+(n[5:12])": "n[14:19]"},
        }
    ]
    RUNTIME_CONSTANTS = None

    def __init__(self, captcha_id: str, proxies=None):
        self.captcha_id = captcha_id
        self.session = requests.Session()
        self.session.trust_env = True
        self.session.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        if proxies:
            self.session.proxies.update(proxies)

    @staticmethod
    def _geetest_callback():
        return f"geetest_{int(random.random() * 10000) + int(time.time() * 1000)}"

    @staticmethod
    def _parse_jsonp(raw: str, callback: str):
        prefix = f"{callback}("
        text = raw.strip()
        if not text.startswith(prefix):
            raise ValueError(f"Unexpected JSONP response: {text[:120]}")
        if text.endswith(");"):
            payload = text[len(prefix):-2]
        elif text.endswith(")"):
            payload = text[len(prefix):-1]
        else:
            payload = text[len(prefix):]
        return json.loads(payload)

    @staticmethod
    def _is_rate_limited(status_code: int, body_text: str):
        text = (body_text or "").lower()
        return (
            status_code == 429
            or "error code: 1015" in text
            or "you are being rate limited" in text
            or ("cloudflare" in text and "access denied" in text)
        )

    @staticmethod
    def _backoff_with_jitter(attempt: int, base_ms: int, max_ms: int, jitter_ms: int):
        core = min(max_ms, base_ms * (2 ** max(0, attempt - 1)))
        return core + random.randint(0, max(1, jitter_ms))

    @staticmethod
    def _parse_geetest_response(resp, callback: str):
        text = (resp.text or "").strip()
        if GeetestSolver._is_rate_limited(resp.status_code, text):
            return {"kind": "rate_limited", "status": resp.status_code, "reason": text[:180]}
        try:
            parsed = GeetestSolver._parse_jsonp(text, callback)
            if isinstance(parsed, dict) and str(parsed.get("status", "")).lower() == "error":
                return {"kind": "upstream_error", "status": resp.status_code, "reason": text[:180], "data": parsed}
            return {"kind": "ok", "data": parsed}
        except Exception:
            pass
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and str(parsed.get("status", "")).lower() == "error":
                return {"kind": "upstream_error", "status": resp.status_code, "reason": text[:180], "data": parsed}
            return {"kind": "ok", "data": parsed}
        except Exception:
            pass
        if resp.status_code >= 400:
            return {"kind": "upstream_error", "status": resp.status_code, "reason": text[:180]}
        return {"kind": "invalid", "status": resp.status_code, "reason": text[:180]}

    @staticmethod
    def _extract_seccode(verify_data: dict):
        seccode = verify_data.get("seccode")
        if isinstance(seccode, dict):
            return seccode
        if all(k in verify_data for k in ("lot_number", "captcha_output", "pass_token", "gen_time")):
            return {
                "lot_number": str(verify_data["lot_number"]),
                "captcha_output": str(verify_data["captcha_output"]),
                "pass_token": str(verify_data["pass_token"]),
                "gen_time": str(verify_data["gen_time"]),
            }
        return None

    @staticmethod
    def _sanitize_string_map(value):
        if not isinstance(value, dict):
            return None
        out = {}
        for k, v in value.items():
            if isinstance(k, str) and isinstance(v, str):
                out[k] = v
        return out if out else None

    @staticmethod
    def _normalize_constants(value, source: str):
        if not isinstance(value, dict):
            return None
        abo = GeetestSolver._sanitize_string_map(value.get("abo"))
        mapping = GeetestSolver._sanitize_string_map(value.get("mapping"))
        if not abo or not mapping:
            return None
        return {
            "abo": abo,
            "mapping": mapping,
            "static_path": str(value.get("static_path") or value.get("staticPath") or ""),
            "fetched_at": str(value.get("fetched_at") or value.get("fetchedAt") or ""),
            "source": source,
        }

    @classmethod
    def _build_constants_candidates(cls, primary=None):
        candidates = []
        seen = set()

        def push(item):
            normalized = cls._normalize_constants(item, item.get("source", "remote") if isinstance(item, dict) else "remote")
            if not normalized:
                return
            key = json.dumps({"abo": normalized["abo"], "mapping": normalized["mapping"]}, sort_keys=True)
            if key in seen:
                return
            seen.add(key)
            candidates.append(normalized)

        push(primary)
        for item in cls.BUILTIN_CONSTANTS:
            push({
                "abo": item["abo"],
                "mapping": item["mapping"],
                "static_path": item["label"],
                "fetched_at": "",
                "source": "builtin",
            })
        return candidates

    @staticmethod
    def _normalize_static_path(path: str):
        if not path:
            return ""
        fixed = str(path).strip()
        if not fixed.startswith("/"):
            fixed = "/" + fixed
        if fixed.endswith("/"):
            fixed = fixed[:-1]
        return fixed

    @staticmethod
    def _decode_lookup_table(script: str):
        table_match = re.search(r'decodeURI\("([^"]+)"\)', script)
        key_match = re.search(r'\}\}\}\("(.+?)"\)\}', script)
        if not table_match or not key_match:
            return None
        try:
            table_enc = urllib.parse.unquote(table_match.group(1))
            key = key_match.group(1)
            if not key:
                return None
            out = []
            for idx, ch in enumerate(table_enc):
                out.append(chr(ord(ch) ^ ord(key[idx % len(key)])))
            return "".join(out).split("^")
        except Exception:
            return None

    @staticmethod
    def _parse_abo_block(raw: str):
        out = {}
        for m in re.finditer(r"""["']?([A-Za-z0-9_]+)["']?\s*:\s*["']([^"']+)["']""", raw):
            out[m.group(1)] = m.group(2)
        return out if out else None

    @staticmethod
    def _parse_mapping_block(raw: str):
        for m in re.finditer(r"""["']([^"']+)["']\s*:\s*["']([^"']+)["']""", raw):
            left = m.group(1)
            right = m.group(2)
            if "n[" in left and "n[" in right:
                return {left: right}
        return None

    @classmethod
    def _extract_constants_from_script(cls, script: str, static_path: str):
        lookup = cls._decode_lookup_table(script)
        if not lookup:
            return None

        def replace_lookup(match):
            idx = int(match.group(2))
            if idx < 0 or idx >= len(lookup):
                return match.group(0)
            return json.dumps(lookup[idx])

        deobfuscated = re.sub(r"(_.{4})\((\d+?)\)", replace_lookup, script)
        abo_match = re.search(r"""\[(?:'|")_lib(?:'|")\]\s*=\s*(\{[\s\S]*?\})\s*,""", deobfuscated)
        mapping_match = re.search(r"""\[(?:'|")_abo(?:'|")\]\s*=\s*([\s\S]*?)\}\(\)""", deobfuscated)
        if not abo_match or not mapping_match:
            return None

        abo = cls._parse_abo_block(abo_match.group(1))
        mapping = cls._parse_mapping_block(mapping_match.group(1)) or cls._parse_mapping_block(deobfuscated)
        if not abo or not mapping:
            return None
        return cls._normalize_constants({
            "abo": abo,
            "mapping": mapping,
            "static_path": static_path,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }, "remote")

    def _refresh_constants_from_static_path(self, static_path_raw: str):
        static_path = self._normalize_static_path(static_path_raw)
        if not static_path:
            return None
        script_url = f"https://static.geevisit.com{static_path}/js/gcaptcha4.js"
        try:
            res = self._get(script_url, headers={
                "user-agent": self.session.headers.get("user-agent", header["user-agent"]),
                "accept": "text/javascript,*/*;q=0.1",
            }, timeout=15)
            if res.status_code < 200 or res.status_code >= 300:
                print(f"Geetest 常量刷新失败: 拉取脚本状态 {res.status_code}")
                return None
            constants = self._extract_constants_from_script(res.text or "", static_path)
            if not constants:
                print("Geetest 常量刷新失败: 官方脚本解析不到可用常量")
                return None
            return constants
        except Exception as e:
            print(f"Geetest 常量刷新失败: {e}")
            return None

    def _get(self, url, **kwargs):
        return self.session.get(url, **kwargs)

    def solve(self, max_attempts: int = 30, max_duration_seconds: int = 180):
        last_verify_data = None
        continue_count = 0
        rate_limited_count = 0
        continuation_reset_count = 0
        continuation_continue_streak = 0
        continuation_error_streak = 0
        last_failure_message = ""
        continuation_context = None
        current_challenge = str(uuid4())
        started_at = time.time()
        runtime_constants = self.RUNTIME_CONSTANTS
        constants_candidates = self._build_constants_candidates(runtime_constants)

        for round_idx in range(max_attempts):
            if time.time() - started_at >= max_duration_seconds:
                break

            in_continuation = continuation_context is not None and continuation_context.get("continuation_mode") is True
            if not in_continuation:
                current_challenge = str(uuid4())

            callback = self._geetest_callback()
            params = {
                "captcha_id": self.captcha_id,
                "challenge": continuation_context["challenge"] if in_continuation else current_challenge,
                "client_type": "web",
                "risk_type": "ai",
                "lang": "zh",
                "callback": callback,
            }
            if in_continuation:
                params["lot_number"] = continuation_context["lot_number"]
                params["payload"] = continuation_context["payload"]
                params["process_token"] = continuation_context["process_token"]
                params["payload_protocol"] = continuation_context.get("payload_protocol", "1")
                params["pt"] = continuation_context.get("pt", "1")

            res = self._get("https://gcaptcha4.geevisit.com/load", params=params, timeout=15)
            load_parsed = self._parse_geetest_response(res, callback)
            if load_parsed["kind"] == "rate_limited":
                rate_limited_count += 1
                last_failure_message = f"{'[续链]' if in_continuation else '[普通]'} load 被限流({load_parsed.get('status')}): {load_parsed.get('reason')}"
                if in_continuation:
                    continuation_error_streak += 1
                    if continuation_error_streak >= 2:
                        continuation_reset_count += 1
                        continuation_context = None
                        continuation_continue_streak = 0
                        continuation_error_streak = 0
                time.sleep(self._backoff_with_jitter(rate_limited_count, 1.5, 15, 0.7))
                continue
            if load_parsed["kind"] != "ok":
                last_failure_message = f"{'[续链]' if in_continuation else '[普通]'} load 异常({load_parsed.get('status')}): {load_parsed.get('reason')}"
                if in_continuation:
                    continuation_error_streak += 1
                    if continuation_error_streak >= 2:
                        continuation_reset_count += 1
                        continuation_context = None
                        continuation_continue_streak = 0
                        continuation_error_streak = 0
                time.sleep(0.5 + random.random() * 0.25)
                continue
            if in_continuation:
                continuation_error_streak = 0
            data = (load_parsed.get("data") or {}).get("data") or {}
            if not data.get("lot_number") or not data.get("pow_detail") or not data.get("payload") or not data.get("process_token"):
                last_failure_message = f"{'[续链]' if in_continuation else '[普通]'} 验证码加载字段缺失"
                time.sleep(0.5 + random.random() * 0.25)
                continue

            lot_number = data["lot_number"]
            static_path = self._normalize_static_path(data.get("static_path"))
            cached_static_path = self._normalize_static_path((runtime_constants or {}).get("static_path", ""))
            should_refresh_constants = (
                static_path
                and (
                    not runtime_constants
                    or runtime_constants.get("source") == "builtin"
                    or cached_static_path != static_path
                )
            )
            if should_refresh_constants:
                refreshed = self._refresh_constants_from_static_path(static_path)
                if refreshed:
                    runtime_constants = refreshed
                    GeetestSolver.RUNTIME_CONSTANTS = refreshed
                    constants_candidates = self._build_constants_candidates(runtime_constants)
                    print(f"验证码算法已自动刷新: {refreshed.get('static_path')}")

            constants = constants_candidates[round_idx % len(constants_candidates)]
            try:
                w = Signer.generate_w(data, self.captcha_id, "ai", constants=constants)
            except Exception as e:
                last_failure_message = f"{'[续链]' if in_continuation else '[普通]'} 生成签名失败: {e}"
                if in_continuation:
                    continuation_error_streak += 1
                    if continuation_error_streak >= 2:
                        continuation_reset_count += 1
                        continuation_context = None
                        continuation_continue_streak = 0
                        continuation_error_streak = 0
                time.sleep(0.5 + random.random() * 0.25)
                continue

            callback = self._geetest_callback()
            verify_params = {
                "callback": callback,
                "captcha_id": self.captcha_id,
                "client_type": "web",
                "lot_number": lot_number,
                "risk_type": "ai",
                "payload": data["payload"],
                "process_token": data["process_token"],
                "payload_protocol": "1",
                "pt": data.get("pt", "1"),
                "w": w,
            }
            res = self._get("https://gcaptcha4.geevisit.com/verify", params=verify_params, timeout=15)
            verify_parsed = self._parse_geetest_response(res, callback)
            if verify_parsed["kind"] == "rate_limited":
                rate_limited_count += 1
                last_failure_message = f"{'[续链]' if in_continuation else '[普通]'} verify 被限流({verify_parsed.get('status')}): {verify_parsed.get('reason')}"
                if in_continuation:
                    continuation_error_streak += 1
                    if continuation_error_streak >= 2:
                        continuation_reset_count += 1
                        continuation_context = None
                        continuation_continue_streak = 0
                        continuation_error_streak = 0
                time.sleep(self._backoff_with_jitter(rate_limited_count, 1.5, 15, 0.7))
                continue
            if verify_parsed["kind"] != "ok":
                last_failure_message = f"{'[续链]' if in_continuation else '[普通]'} verify 异常({verify_parsed.get('status')}): {verify_parsed.get('reason')}"
                if in_continuation:
                    continuation_error_streak += 1
                    if continuation_error_streak >= 2:
                        continuation_reset_count += 1
                        continuation_context = None
                        continuation_continue_streak = 0
                        continuation_error_streak = 0
                time.sleep(0.5 + random.random() * 0.25)
                continue
            if in_continuation:
                continuation_error_streak = 0
            verify_data = (verify_parsed.get("data") or {}).get("data") or {}
            last_verify_data = verify_data

            if verify_data.get("result") == "success":
                seccode = self._extract_seccode(verify_data)
                if seccode:
                    return seccode
                raise Exception(f"Geetest success without seccode: {verify_data}")
            result = str(verify_data.get("result", "")).lower()
            if result in ("continue", "continued"):
                continue_count += 1
                continuation_continue_streak += 1
                continuation_context = {
                    "challenge": continuation_context["challenge"] if in_continuation else current_challenge,
                    "lot_number": str(verify_data.get("lot_number") or data.get("lot_number") or ""),
                    "payload": str(verify_data.get("payload") or data.get("payload") or ""),
                    "process_token": str(verify_data.get("process_token") or data.get("process_token") or ""),
                    "payload_protocol": str(verify_data.get("payload_protocol") or data.get("payload_protocol") or "1"),
                    "pt": str(verify_data.get("pt") or data.get("pt") or "1"),
                    "continuation_mode": True,
                }
                last_failure_message = f"验证码继续挑战({result})，续链次数={continuation_continue_streak}"
                if continuation_continue_streak >= 6:
                    continuation_reset_count += 1
                    continuation_context = None
                    continuation_continue_streak = 0
                    continuation_error_streak = 0
                    current_challenge = str(uuid4())
                    last_failure_message = "续链连续 continue 达到阈值(6)，已自动重开 challenge"
                time.sleep(self._backoff_with_jitter(max(1, continuation_continue_streak), 0.8, 6, 0.3))
                continue

            last_failure_message = f"验证码校验失败: {str(verify_data)[:280]}"
            continuation_context = None
            continuation_continue_streak = 0
            continuation_error_streak = 0
            current_challenge = str(uuid4())
            time.sleep(0.5 + random.random() * 0.25)

        raise Exception(
            f"验证码多次校验失败: {last_failure_message}; "
            f"统计: continue={continue_count}, 续链重开={continuation_reset_count}, 限流={rate_limited_count}, 最后响应={str(last_verify_data)[:260]}"
        )


def normalize_ikuuu_domain(value: str):
    if not value:
        return None
    raw = str(value).strip().strip('\'"<>[](){}，,。.;；')
    if not raw:
        return None
    if raw.startswith('//'):
        raw = 'https:' + raw
    if not raw.startswith(('http://', 'https://')):
        raw = 'https://' + raw
    parsed = urllib.parse.urlparse(raw)
    domain = (parsed.netloc or parsed.path.split('/')[0]).lower().strip()
    if ':' in domain:
        domain = domain.split(':', 1)[0]
    if not re.fullmatch(r'ikuuu\.[a-z0-9.-]+', domain):
        return None
    if domain == DOMAIN_DISCOVERY_HOST:
        return None
    return domain


def unique_domains(domains):
    result = []
    seen = set()
    for item in domains:
        domain = normalize_ikuuu_domain(item)
        if not domain or domain in seen:
            continue
        seen.add(domain)
        result.append(domain)
    return result


def extract_domains_with_node_vm(html: str):
    node_path = shutil.which('node')
    if not node_path:
        return []

    script_match = re.search(r'<script>([\s\S]*?_0x23763f[\s\S]*?)</script>', html or '', re.I)
    if not script_match:
        return []

    runner = r"""
const fs = require('fs');
const vm = require('vm');
const jsInput = fs.readFileSync(0, 'utf8');
const marker = 'const _0x23763f=[_0x1c49a4,_0x41e280];';
if (!jsInput.includes(marker)) {
  process.stdout.write('[]');
  process.exit(0);
}
const js = jsInput.replace(marker, marker + 'globalThis.__domains=_0x23763f;throw new Error("STOP_AFTER_DOMAINS");');
const sandbox = {
  window: { location: { href: 'https://ikuuu.ch/' }, setInterval() {} },
  document: { getElementById() { return null; }, querySelectorAll() { return []; } },
  fetch() { return Promise.resolve({}); },
  AbortController: class { constructor(){ this.signal = {}; } abort(){} },
  setTimeout() { return 1; },
  clearTimeout() {},
};
sandbox.globalThis = sandbox;
try {
  vm.runInNewContext(js, sandbox, { timeout: 5000 });
} catch (e) {
  if (e.message !== 'STOP_AFTER_DOMAINS') {
    process.stdout.write('[]');
    process.exit(0);
  }
}
process.stdout.write(JSON.stringify(sandbox.__domains || []));
"""
    try:
        result = subprocess.run(
            [node_path, '-e', runner],
            input=script_match.group(1),
            text=True,
            capture_output=True,
            timeout=8,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        decoded = json.loads(result.stdout)
    except Exception:
        return []

    candidates = []
    if isinstance(decoded, list):
        for item in decoded:
            if isinstance(item, dict):
                candidates.append(item.get('url', ''))
                candidates.append(item.get('name', ''))
            else:
                candidates.append(str(item))
    return unique_domains(candidates)


def extract_latest_domains(html: str):
    candidates = []
    soup = BeautifulSoup(html or '', 'html.parser')

    domain_list = soup.find(id='domain-list')
    search_scope = domain_list if domain_list else soup
    for tag in search_scope.find_all(['a', 'h3']):
        if tag.name == 'a':
            candidates.append(tag.get('href', ''))
        candidates.append(tag.get_text(' ', strip=True))

    candidates.extend(re.findall(r'https?://(?:www\.)?ikuuu\.[a-z0-9.-]+(?:/[^\s"\'<>]*)?', html or '', flags=re.I))
    candidates.extend(re.findall(r'\bikuuu\.[a-z0-9.-]+\b', html or '', flags=re.I))
    domains = unique_domains(candidates)
    if domains:
        return domains
    return extract_domains_with_node_vm(html)


def get_response_text(response):
    if not response.encoding or response.encoding.lower() == 'iso-8859-1':
        response.encoding = 'utf-8'
    return response.text


def fetch_latest_domains(timeout=10):
    response = requests.get(
        DOMAIN_DISCOVERY_URL,
        headers={
            'User-Agent': header['user-agent'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        },
        timeout=timeout,
        allow_redirects=True,
    )
    response.raise_for_status()
    domains = extract_latest_domains(get_response_text(response))
    if domains:
        print(f'从 {DOMAIN_DISCOVERY_URL} 获取到最新域名: {", ".join(domains)}')
    else:
        print(f'已访问 {DOMAIN_DISCOVERY_URL}，但页面中未解析到可用候选域名')
    return domains


def is_domain_available(domain: str, timeout=6):
    urls = (f'https://{domain}/auth/login', f'https://{domain}/')
    last_error = None
    for url in urls:
        try:
            response = requests.get(
                url,
                headers={'User-Agent': header['user-agent']},
                timeout=timeout,
                allow_redirects=True,
            )
            if 200 <= response.status_code < 400:
                print(f'检测到域名 {domain} 可用')
                return True
            last_error = f'状态码 {response.status_code}'
        except Exception as exc:
            last_error = str(exc)
    print(f'域名 {domain} 不可用: {last_error}')
    return False


def get_available_domain():
    global _AVAILABLE_DOMAIN_CACHE
    if _AVAILABLE_DOMAIN_CACHE and is_domain_available(_AVAILABLE_DOMAIN_CACHE):
        return _AVAILABLE_DOMAIN_CACHE

    fallback_to_static = False
    try:
        domains = fetch_latest_domains()
    except Exception as exc:
        print(f'访问 {DOMAIN_DISCOVERY_URL} 失败，降级使用内置 DOMAINS: {exc}')
        domains = []
        fallback_to_static = True

    for domain in domains:
        if is_domain_available(domain):
            _AVAILABLE_DOMAIN_CACHE = domain
            return domain

    if domains:
        print('最新域名均不可用，继续尝试内置 DOMAINS')
    elif not fallback_to_static:
        print('未获取到最新域名，继续尝试内置 DOMAINS')

    for domain in DOMAINS:
        if is_domain_available(domain):
            _AVAILABLE_DOMAIN_CACHE = domain
            return domain
    raise Exception('所有域名都不可用，请检查网络连接')

def check_in(email, passwd):
    try:
        domain = get_available_domain()
        login_url = f'https://{domain}/auth/login'
        check_url = f'https://{domain}/user/checkin'
        user_url = f'https://{domain}/user'
        
        session = requests.session()
        session.get(f'https://{domain}/auth/login', headers=header, timeout=10)

        print(f'[{email}] 开始破解验证码...')
        solver = GeetestSolver("cc96d05ba8b60f9112f76e18526fcb73")
        captcha_result = solver.solve()
        print(f'[{email}] 验证码破解成功')

        data = {
            'email': email,
            'passwd': passwd,
            'host': domain,
            'remember_me': 'on',
            'pageLoadedAt': int(time.time() * 1000),
            'captcha_result[lot_number]': captcha_result['lot_number'],
            'captcha_result[captcha_output]': captcha_result['captcha_output'],
            'captcha_result[pass_token]': captcha_result['pass_token'],
            'captcha_result[gen_time]': captcha_result['gen_time']
        }

        current_header = header.copy()
        current_header['content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        current_header['origin'] = f'https://{domain}'
        current_header['referer'] = f'https://{domain}/auth/login'
        
        print(f'[{email}] 请求 URL: {login_url}')
        
        response = session.post(
            url=login_url, 
            headers=current_header, 
            data=data,
            timeout=15
        )
        
        if response.status_code not in [200, 302]:
            raise Exception(f'登录失败，状态码: {response.status_code}, 响应: {response.text[:200]}')
            
        try:
            response_data = response.json()
            print(f"登录响应: {response_data.get('msg', '无消息')}")
            if response_data.get('ret') != 1:
                return f"登录失败: {response_data.get('msg')}", None, None
        except:
            if response.status_code == 302:
                print("登录看起来成功了（重定向）")
            else:
                print(f"无法解析JSON响应: {response.text[:100]}")
        
        # Following steps...
        result = session.post(
            url=check_url, 
            headers=current_header,
            timeout=15
        )
        
        if result.status_code != 200:
            raise Exception(f'签到失败，状态码: {result.status_code}')
            
        result_data = result.json()
        content = result_data['msg']
        
        user_page = session.get(
            url=user_url,
            headers=current_header,
            timeout=15
        )

        html_content = user_page.text
        try:
            import base64
            import re
            m = re.search(r'originBody\s*=\s*["\']([A-Za-z0-9+/=\n\r]+)["\']', html_content, re.S)
            if m:
                b64 = m.group(1).replace('\n', '').replace('\r', '')
                decoded = base64.b64decode(b64)
                html_content = decoded.decode('utf-8', errors='ignore')
        except:
            pass

        soup = BeautifulSoup(html_content, 'html.parser')
        flow = None
        flow_unit = None

        cards = soup.find_all('div', class_='card card-statistic-2')
        for card in cards:
            h4 = card.find('h4')
            if h4 and '剩余流量' in h4.text:
                counter_span = card.find('span', class_='counter')
                if counter_span:
                    flow = counter_span.text.strip()
                    unit_text = ''
                    if counter_span.next_sibling and isinstance(counter_span.next_sibling, str):
                        unit_text = counter_span.next_sibling.strip()
                    if not unit_text:
                        small = card.find('small')
                        if small:
                            unit_text = small.text.strip()
                    flow_unit = unit_text
                    break
        return content, flow, flow_unit
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'发生错误: {e}')
        return '签到失败', None, None

@capture_output("ikuuu运行结果")
def main():
    try:
        accounts = get_accounts_from_env()
        for account in accounts:
            email = account['email']
            passwd = account['passwd']
            print(f"\n开始处理账号: {email}")
            content, flow, flow_unit = check_in(email, passwd)
            print(f'签到结果: {content}')
            if flow:
                print(f'账号剩余流量: {flow}{flow_unit if flow_unit else ""}')
            else:
                print('未能获取账号流量信息')
    except Exception as e:
        print(f'程序出错: {e}')

if __name__ == '__main__':
    main()

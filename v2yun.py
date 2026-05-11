#!/usr/bin/env python3
# -*- coding：utf-8 -*-
"""
@脚本名称：V2云机场签到脚本
@创建时间：2026-04-24
@脚本作者：3iXi（https://github.com/3ixi）
@脚本功能：自动登录+自动签到+自动维护cookie有效期
@脚本版本：1.0.1
@需要依赖：requests pycryptodome numpy Pillow opencv-python-headless（镜像系统使用Alpine等musl libc的青龙面板无法通过网页安装opencv依赖，请自行问AI通过终端安装）
@脚本描述：
     1.访问https://v2cloud.club 注册账号
	 2.创建环境变量v2yun，变量值是邮箱&密码，密码中不能包含&，否则会报错，示例：tony@qq.com&aaa112233..
	 3.国内主机请配合LoadProxy.py模块来通过Clash等服务代理请求，也可通过创建环境变量v2yun_url来指定V2云服务器，比如https://v2cloud.club ，如果未指定则默认使用脚本中自带的https://v2yun.uk 进行请求
"""

import argparse
import importlib.util
import json
import os
import re
import sys
import time
import types
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

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

DEFAULT_BASE_URL = "https://v2yun.uk"
BASE_URL = os.getenv("v2yun_url", DEFAULT_BASE_URL)
DEFAULT_ACCOUNT_ENV = "v2yun"
DEFAULT_ACCOUNT_RETRY = 3
DEFAULT_CAPTCHA_RETRY = 5
DEFAULT_TIMEOUT = 20
COOKIE_FILE_NAME = "v2yun_cookie.json"
REQUIRED_COOKIE_KEYS = ("uid", "email", "key", "expire_in")

GEETEST_EMBEDDED_SOURCES = {
    "crypto": 'from __future__ import annotations\n\nimport hashlib\nimport random\nfrom functools import lru_cache\nfrom typing import Any\n\nfrom Crypto.Cipher import AES, PKCS1_v1_5\nfrom Crypto.PublicKey import RSA\n\nRSA_MODULUS_DATA = {\n    0: 134982529,\n    1: 254232810,\n    2: 164556709,\n    3: 234907349,\n    4: 134685994,\n    5: 35463984,\n    6: 258277946,\n    7: 12518857,\n    8: 44638621,\n    9: 93783641,\n    10: 212253739,\n    11: 62792472,\n    12: 186688352,\n    13: 109500232,\n    14: 182488077,\n    15: 261196188,\n    16: 26354094,\n    17: 103248217,\n    18: 106891695,\n    19: 165771045,\n    20: 41530993,\n    21: 263704736,\n    22: 111785174,\n    23: 12753611,\n    24: 232116673,\n    25: 155524985,\n    26: 218291229,\n    27: 122452343,\n    28: 248250238,\n    29: 118739550,\n    30: 251169095,\n    31: 129059733,\n    32: 149835464,\n    33: 5498868,\n    34: 71719731,\n    35: 154456417,\n    36: 49635,\n    "t": 37,\n    "s": 0,\n}\nGEETEST_BASE64_CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789()"\nGEETEST_BASE64_PAD = "."\nGEETEST_BASE64_MASKS = (7274496, 9483264, 19220, 235)\nAES_IV = b"0" * 16\n\n\ndef four_random_chart() -> str:\n    """生成 4 位十六进制随机片段。"""\n\n    return f"{random.randint(0, 0xFFFF):04x}"\n\n\ndef parse_jsbn_bigint(n_obj: dict[Any, int]) -> int:\n    """将 JSBN 结构的模数数据还原为整数。"""\n\n    db = 28\n    dv = 1 << db\n    return sum(n_obj[index] * (dv**index) for index in range(n_obj["t"]))\n\n\n@lru_cache(maxsize=1)\ndef _get_public_key() -> RSA.RsaKey:\n    """构造并缓存极验公钥。"""\n\n    exponent = 65537\n    modulus = parse_jsbn_bigint(RSA_MODULUS_DATA)\n    return RSA.construct((modulus, exponent))\n\n\ndef encrypt_data(plaintext: str) -> str:\n    """使用 PKCS#1 v1.5 对字符串做 RSA 加密。"""\n\n    cipher = PKCS1_v1_5.new(_get_public_key())\n    return cipher.encrypt(plaintext.encode("utf-8")).hex()\n\n\ndef RSA_jiami_r(str_16: str) -> str:\n    """使用极验公钥加密 16 位随机种子。"""\n\n    return encrypt_data(str_16)\n\n\ndef parse_string_to_wordarray(text: str) -> list[int]:\n    """按 CryptoJS 的方式将字符串拆成 32 位整数数组。"""\n\n    words: list[int] = []\n    for index, char in enumerate(text):\n        word_index = index >> 2\n        while len(words) <= word_index:\n            words.append(0)\n        shift = 24 - (index % 4) * 8\n        words[word_index] |= (ord(char) & 0xFF) << shift\n    return words\n\n\ndef AES_O(plaintext: str, str_16: str) -> list[int]:\n    """使用 AES-CBC 加密字符串并返回字节列表。"""\n\n    key = str_16.encode("utf-8")\n    if len(key) != 16:\n        raise ValueError("AES 密钥长度必须为 16 字节")\n\n    data = plaintext.encode("utf-8")\n    pad_len = 16 - len(data) % 16\n    padded = data + bytes([pad_len] * pad_len)\n\n    cipher = AES.new(key, AES.MODE_CBC, AES_IV)\n    return list(cipher.encrypt(padded))\n\n\ndef geetest_base64_encode(data: list[int]) -> dict[str, str]:\n    """使用极验自定义字符表对字节数组做 Base64 编码。"""\n\n    def extract_bits(value: int, mask: int) -> int:\n        result = 0\n        for bit_index in range(23, -1, -1):\n            if (mask >> bit_index) & 1:\n                result = (result << 1) | ((value >> bit_index) & 1)\n        return result\n\n    encoded = []\n    padding = ""\n    index = 0\n\n    while index < len(data):\n        remain = len(data) - index\n        if remain >= 3:\n            block = (data[index] << 16) | (data[index + 1] << 8) | data[index + 2]\n            encoded.extend(\n                GEETEST_BASE64_CHARSET[extract_bits(block, mask)]\n                for mask in GEETEST_BASE64_MASKS\n            )\n            index += 3\n            continue\n\n        if remain == 2:\n            block = (data[index] << 16) | (data[index + 1] << 8)\n            encoded.extend(\n                GEETEST_BASE64_CHARSET[extract_bits(block, mask)]\n                for mask in GEETEST_BASE64_MASKS[:3]\n            )\n            padding = GEETEST_BASE64_PAD\n        else:\n            block = data[index] << 16\n            encoded.extend(\n                GEETEST_BASE64_CHARSET[extract_bits(block, mask)]\n                for mask in GEETEST_BASE64_MASKS[:2]\n            )\n            padding = GEETEST_BASE64_PAD * 2\n        break\n\n    return {"res": "".join(encoded), "end": padding}\n\n\ndef encrypt_string(text: str, mapping: list[int], salt: str) -> str:\n    """按极验规则把十六进制盐值插入原字符串。"""\n\n    if not mapping or not salt:\n        return text\n\n    result = text\n    factor_a = mapping[0]\n    factor_b = mapping[2]\n    factor_c = mapping[4]\n    offset = 0\n\n    while offset < len(salt):\n        pair = salt[offset : offset + 2]\n        if len(pair) < 2:\n            break\n\n        offset += 2\n        value = int(pair, 16)\n        insert_at = (factor_a * value * value + factor_b * value + factor_c) % len(text)\n        result = result[:insert_at] + chr(value) + result[insert_at:]\n\n    return result\n\n\ndef simple_md5(message: str) -> str:\n    """返回字符串的 MD5 十六进制结果。"""\n\n    return hashlib.md5(message.encode("utf-8")).hexdigest()\n\n\n__all__ = [\n    "AES_O",\n    "RSA_jiami_r",\n    "encrypt_data",\n    "encrypt_string",\n    "four_random_chart",\n    "geetest_base64_encode",\n    "parse_jsbn_bigint",\n    "parse_string_to_wordarray",\n    "simple_md5",\n]\n',
    "trajectory": 'from __future__ import annotations\n\nimport math\nimport random\nfrom typing import Any, Optional\n\nfrom .crypto import encrypt_string as insert_chars_with_salt\n\nMOVE_EVENTS = {"move", "mousemove", "touchmove", "pointermove"}\nCLICK_EVENTS = {\n    "down",\n    "up",\n    "click",\n    "mousedown",\n    "mouseup",\n    "touchstart",\n    "touchend",\n    "pointerdown",\n    "pointerup",\n}\nTIME_ONLY_EVENTS = {"focus", "blur", "keydown", "keyup"}\n\n\ndef generate_realistic_trajectory(\n    start_x: int,\n    start_y: int,\n    end_x: int,\n    end_y: int,\n    start_time: int,\n) -> list[Any]:\n    """生成一组更接近真实用户行为的鼠标轨迹。"""\n\n    trajectory: list[Any] = []\n    distance = ((end_x - start_x) ** 2 + (end_y - start_y) ** 2) ** 0.5\n    steps = int(distance / 2) + random.randint(5, 15)\n    current_time = start_time\n\n    for index in range(steps):\n        progress = index / steps\n\n        if progress < 0.3:\n            eased = progress / 0.3 * 0.2\n        elif progress < 0.7:\n            eased = 0.2 + (progress - 0.3) / 0.4 * 0.5\n        else:\n            eased = 0.7 + (progress - 0.7) / 0.3 * 0.3\n\n        target_x = start_x + (end_x - start_x) * eased\n        target_y = start_y + (end_y - start_y) * eased\n        current_x = int(target_x + random.uniform(-0.5, 0.5))\n        current_y = int(target_y + random.uniform(-0.5, 0.5))\n\n        current_time += random.choices(\n            [3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 24],\n            weights=[5, 8, 10, 12, 10, 8, 5, 3, 2, 1, 1],\n        )[0]\n\n        trajectory.append(["move", current_x, current_y, current_time, "pointermove"])\n\n        if random.random() < 0.15:\n            stay_duration = random.randint(5, 15)\n            trajectory.append(\n                ["move", current_x, current_y, current_time + stay_duration, "pointermove"]\n            )\n            current_time += stay_duration\n\n    for _ in range(random.randint(2, 5)):\n        current_time += random.randint(8, 25)\n        trajectory.append(\n            [\n                "move",\n                end_x + random.randint(-1, 1),\n                end_y + random.randint(-1, 1),\n                current_time,\n                "pointermove",\n            ]\n        )\n\n    current_time += random.randint(50, 150)\n    trajectory.append(["down", end_x, end_y, current_time, "pointerdown"])\n    trajectory.append(["focus", current_time + 1])\n\n    click_duration = random.randint(80, 130)\n    trajectory.append(["up", end_x, end_y, current_time + click_duration, "pointerup"])\n    return trajectory\n\n\ndef process_mouse_trajectory(\n    events: list[Any],\n    max_records: Optional[int] = None,\n) -> dict[str, Any]:\n    """将绝对坐标轨迹压缩为相对位移和时间差。"""\n\n    if not events:\n        return {\n            "data": [],\n            "first_event": None,\n            "last_event": None,\n            "total_events": 0,\n        }\n\n    start_index = 0\n    if max_records and len(events) > max_records:\n        start_index = len(events) - max_records\n\n    result: list[Any] = []\n    first_event = None\n    last_event = None\n    prev_x = 0\n    prev_y = 0\n    prev_time = 0\n\n    for event in events[start_index:]:\n        event_type = event[0]\n\n        if event_type in MOVE_EVENTS:\n            x = event[1]\n            y = event[2]\n            timestamp = event[3]\n\n            if first_event is None:\n                first_event = event\n            last_event = event\n\n            delta_x = x - prev_x\n            delta_y = y - prev_y\n            time_diff = 0 if prev_time == 0 else timestamp - prev_time\n\n            result.append([event_type, [delta_x, delta_y], time_diff])\n            prev_x = x\n            prev_y = y\n            prev_time = timestamp\n            continue\n\n        if event_type in CLICK_EVENTS:\n            timestamp = event[3] if len(event) > 3 else event[1]\n            time_diff = 0 if prev_time == 0 else timestamp - prev_time\n            result.append([event_type, [0, 0], time_diff])\n            prev_time = timestamp\n            continue\n\n        if event_type in TIME_ONLY_EVENTS:\n            timestamp = event[1]\n            time_diff = 0 if prev_time == 0 else timestamp - prev_time\n            result.append([event_type, time_diff])\n            prev_time = timestamp\n\n    return {\n        "data": result,\n        "first_event": first_event,\n        "last_event": last_event,\n        "total_events": len(result),\n    }\n\n\ndef compress_trajectory(events: list[Any]) -> str:\n    """按极验的位级压缩规则编码轨迹数据。"""\n\n    event_type_map = {\n        "move": 0,\n        "down": 1,\n        "up": 2,\n        "scroll": 3,\n        "focus": 4,\n        "blur": 5,\n        "unload": 6,\n        "unknown": 7,\n    }\n\n    def to_bits(value: int, width: int) -> str:\n        binary = bin(value)[2:]\n        return binary.rjust(width, "0")\n\n    def transform(values: list[int], func) -> list[int]:\n        return [func(value) for value in values]\n\n    def encode_event_types(types: list[str]) -> str:\n        encoded: list[int] = []\n        index = 0\n        total = len(types)\n\n        while index < total:\n            current = types[index]\n            repeat = 0\n            while True:\n                if repeat >= 16:\n                    break\n                next_index = index + repeat + 1\n                if next_index >= total or types[next_index] != current:\n                    break\n                repeat += 1\n\n            index += repeat + 1\n            code = event_type_map[current]\n            if repeat:\n                encoded.append(8 | code)\n                encoded.append(repeat - 1)\n            else:\n                encoded.append(code)\n\n        payload = "".join(to_bits(item, 4) for item in encoded)\n        return to_bits(32768 | total, 16) + payload\n\n    def encode_numbers(values: list[int], is_coordinate: bool) -> str:\n        def limit_value(value: int) -> int:\n            limit = 32767\n            return max(-limit, min(limit, value))\n\n        limited = transform(values, limit_value)\n        run_length_encoded: list[int] = []\n        index = 0\n\n        while index < len(limited):\n            repeat = 1\n            current = limited[index]\n            absolute = abs(current)\n\n            while (\n                index + repeat < len(limited)\n                and limited[index + repeat] == current\n                and absolute < 127\n                and repeat < 127\n            ):\n                repeat += 1\n\n            if repeat > 1:\n                run_length_encoded.append(\n                    (49152 if current < 0 else 32768) | (repeat << 7) | absolute\n                )\n            else:\n                run_length_encoded.append(current)\n\n            index += repeat\n\n        meta_parts: list[str] = []\n        data_parts: list[str] = []\n        for value in run_length_encoded:\n            if value == 0:\n                hex_digits = 1\n            else:\n                hex_digits = max(1, math.ceil(math.log(abs(value) + 1) / math.log(16)))\n            meta_parts.append(to_bits(hex_digits - 1, 2))\n            data_parts.append(to_bits(abs(value), 4 * hex_digits))\n\n        if is_coordinate:\n            sign_payload = "".join(\n                "1"\n                if value < 0\n                else "0"\n                for value in run_length_encoded\n                if value != 0 and (value >> 15) != 1\n            )\n        else:\n            sign_payload = ""\n\n        return (\n            to_bits(32768 | len(run_length_encoded), 16)\n            + "".join(meta_parts)\n            + "".join(data_parts)\n            + sign_payload\n        )\n\n    event_types: list[str] = []\n    time_diffs: list[int] = []\n    x_deltas: list[int] = []\n    y_deltas: list[int] = []\n\n    for event in events:\n        event_types.append(event[0])\n        time_diffs.append(event[1] if len(event) == 2 else event[2])\n        if len(event) == 3:\n            x_deltas.append(event[1][0])\n            y_deltas.append(event[1][1])\n\n    binary = (\n        encode_event_types(event_types)\n        + encode_numbers(time_diffs, False)\n        + encode_numbers(x_deltas, True)\n        + encode_numbers(y_deltas, True)\n    )\n    if len(binary) % 6:\n        binary += to_bits(0, 6 - len(binary) % 6)\n\n    charset = "()*,-./0123456789:?@ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz~"\n    return "".join(charset[int(binary[index : index + 6], 2)] for index in range(0, len(binary), 6))\n\n\nclass TrajectoryEncoder:\n    """按滑块验证阶段的规则编码轨迹。"""\n\n    CHARSET = "()*,-./0123456789:?@ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqr"\n    BASE = len(CHARSET)\n    DIRECTION_CHARS = "stuvwxyz~"\n    DIRECTION_PATTERNS = (\n        (1, 0),\n        (2, 0),\n        (1, -1),\n        (1, 1),\n        (0, 1),\n        (0, -1),\n        (3, 0),\n        (2, -1),\n        (2, 1),\n    )\n\n    def encode_number(self, num: int) -> str:\n        """将单个数字编码为自定义 64 进制字符串。"""\n\n        absolute = abs(num)\n        high = absolute // self.BASE\n        low = absolute % self.BASE\n\n        encoded = []\n        if num < 0:\n            encoded.append("!")\n        if 0 < high < self.BASE:\n            encoded.extend(("$", self.CHARSET[high]))\n        encoded.append(self.CHARSET[low])\n        return "".join(encoded)\n\n    def compress_trajectory(self, points: list[list[int]]) -> list[list[int]]:\n        """把连续点位转换成相邻差值。"""\n\n        compressed: list[list[int]] = []\n        accumulated_time = 0\n\n        for index in range(len(points) - 1):\n            dx = points[index + 1][0] - points[index][0]\n            dy = points[index + 1][1] - points[index][1]\n            dt = abs(points[index + 1][2] - points[index][2])\n\n            if dx == 0 and dy == 0 and dt == 0:\n                continue\n\n            if dx == 0 and dy == 0:\n                accumulated_time += dt\n                continue\n\n            compressed.append([dx, dy, dt + accumulated_time])\n            accumulated_time = 0\n\n        if accumulated_time:\n            compressed.append([0, 0, accumulated_time])\n\n        return compressed\n\n    def get_direction_code(self, dx: int, dy: int) -> str | None:\n        """判断差值是否可用方向码表示。"""\n\n        for index, pattern in enumerate(self.DIRECTION_PATTERNS):\n            if (dx, dy) == pattern:\n                return self.DIRECTION_CHARS[index]\n        return None\n\n    def encode(self, trajectory: list[list[int]]) -> str:\n        """编码轨迹为极验所需的 aa 字符串。"""\n\n        compressed = self.compress_trajectory(trajectory)\n        x_encoded: list[str] = []\n        y_encoded: list[str] = []\n        t_encoded: list[str] = []\n\n        for dx, dy, dt in compressed:\n            direction_code = self.get_direction_code(dx, dy)\n            if direction_code is not None:\n                y_encoded.append(direction_code)\n            else:\n                x_encoded.append(self.encode_number(dx))\n                y_encoded.append(self.encode_number(dy))\n            t_encoded.append(self.encode_number(dt))\n\n        return "".join(x_encoded) + "!!" + "".join(y_encoded) + "!!" + "".join(t_encoded)\n\n    def encrypt_string(self, text: str, mapping: list[int], salt: str) -> str:\n        """复用通用加密插入逻辑，避免重复实现。"""\n\n        return insert_chars_with_salt(text, mapping, salt)\n\n\ndef H(distance: int, challenge: str) -> str:\n    """根据 challenge 计算 userresponse。"""\n\n    suffix = challenge[-2:]\n    digits = []\n    for char in suffix:\n        code = ord(char)\n        digits.append(code - 87 if code > 57 else code - 48)\n\n    target = round(distance) + 36 * digits[0] + digits[1]\n\n    buckets = [[], [], [], [], []]\n    seen: dict[str, int] = {}\n    bucket_index = 0\n    for char in challenge[:-2]:\n        if char in seen:\n            continue\n        seen[char] = 1\n        buckets[bucket_index].append(char)\n        bucket_index = (bucket_index + 1) % 5\n\n    result = ""\n    weights = [1, 2, 5, 10, 50]\n    weight_index = 4\n\n    while target > 0 and weight_index >= 0:\n        if target >= weights[weight_index] and buckets[weight_index]:\n            char_index = int(random.random() * len(buckets[weight_index]))\n            result += buckets[weight_index][char_index]\n            target -= weights[weight_index]\n            continue\n        buckets.pop(weight_index)\n        weights.pop(weight_index)\n        weight_index -= 1\n\n    return result\n\n\n__all__ = [\n    "H",\n    "TrajectoryEncoder",\n    "compress_trajectory",\n    "generate_realistic_trajectory",\n    "process_mouse_trajectory",\n]\n',
    "performance": 'from __future__ import annotations\n\nimport random\nimport time\nfrom typing import Optional\n\n\ndef generate_fake_performance_timing(base_time: Optional[int] = None) -> dict[str, int]:\n    """生成一组看起来合理的 performance.timing 数据。"""\n\n    if base_time is None:\n        base_time = int(time.time() * 1000)\n\n    intervals = {\n        "fetch": random.randint(1, 2),\n        "domain_lookup_start": random.randint(3, 5),\n        "domain_lookup": random.randint(5, 15),\n        "connect": random.randint(50, 150),\n        "ssl_offset": random.randint(30, 50),\n        "request": random.randint(1, 5),\n        "response": random.randint(20, 100),\n        "response_end": random.randint(1, 3),\n        "unload_start": random.randint(1, 3),\n        "unload": random.randint(1, 5),\n        "dom_loading": random.randint(1, 3),\n        "dom_interactive": random.randint(50, 200),\n        "dom_content_loaded": random.randint(1, 3),\n        "load_event": random.randint(0, 5),\n    }\n\n    timing = {\n        "navigationStart": base_time,\n    }\n    timing["fetchStart"] = timing["navigationStart"] + intervals["fetch"]\n    timing["domainLookupStart"] = timing["fetchStart"] + intervals["domain_lookup_start"]\n    timing["domainLookupEnd"] = timing["domainLookupStart"] + intervals["domain_lookup"]\n    timing["connectStart"] = timing["domainLookupEnd"]\n    timing["secureConnectionStart"] = timing["connectStart"] + intervals["ssl_offset"]\n    timing["connectEnd"] = timing["connectStart"] + intervals["connect"]\n    timing["requestStart"] = timing["connectEnd"] + intervals["request"]\n    timing["responseStart"] = timing["requestStart"] + intervals["response"]\n    timing["responseEnd"] = timing["responseStart"] + intervals["response_end"]\n    timing["unloadEventStart"] = timing["responseEnd"] + intervals["unload_start"]\n    timing["unloadEventEnd"] = timing["unloadEventStart"] + intervals["unload"]\n    timing["domLoading"] = timing["unloadEventEnd"] + intervals["dom_loading"]\n    timing["domInteractive"] = timing["domLoading"] + intervals["dom_interactive"]\n    timing["domContentLoadedEventStart"] = timing["domInteractive"]\n    timing["domContentLoadedEventEnd"] = timing["domInteractive"] + intervals["dom_content_loaded"]\n    timing["domComplete"] = timing["domContentLoadedEventEnd"]\n    timing["loadEventStart"] = timing["domComplete"]\n    timing["loadEventEnd"] = timing["loadEventStart"] + intervals["load_event"]\n    timing["redirectStart"] = 0\n    timing["redirectEnd"] = 0\n    return timing\n\n\ndef _ease_out_expo(progress: float) -> float:\n    """指数缓动函数，用于生成更自然的滑动轨迹。"""\n\n    if progress == 1:\n        return 1\n    return 1 - pow(2, -10 * progress)\n\n\ndef get_slide_track(distance: int) -> tuple[list[list[int]], int]:\n    """根据滑动距离生成滑块轨迹。"""\n\n    if not isinstance(distance, int) or distance < 0:\n        raise ValueError(f"distance 必须是大于等于 0 的整数，当前值为 {distance!r}")\n\n    track = [\n        [random.randint(-50, -10), random.randint(-50, -10), 0],\n        [0, 0, 0],\n    ]\n    point_count = 10 + distance // 2\n    elapsed = random.randint(50, 100)\n    last_x = 0\n\n    for index in range(point_count):\n        current_x = round(_ease_out_expo(index / point_count) * distance)\n        elapsed += random.randint(10, 50)\n        if current_x == last_x:\n            continue\n        track.append([current_x, 0, elapsed])\n        last_x = current_x\n\n    track.append(track[-1][:])\n    return track, track[-1][2]\n\n\n__all__ = ["generate_fake_performance_timing", "get_slide_track"]\n',
    "imaging": 'from __future__ import annotations\n\nfrom pathlib import Path\nfrom tempfile import TemporaryDirectory\n\nimport cv2\nimport numpy as np\nimport requests\nfrom PIL import Image\n\nSTATIC_HOST = "https://static.geetest.com/"\nREQUEST_TIMEOUT = 15\nHTTP_DEBUG = True\nRESTORE_ORDER = (\n    39,\n    38,\n    48,\n    49,\n    41,\n    40,\n    46,\n    47,\n    35,\n    34,\n    50,\n    51,\n    33,\n    32,\n    28,\n    29,\n    27,\n    26,\n    36,\n    37,\n    31,\n    30,\n    44,\n    45,\n    43,\n    42,\n    12,\n    13,\n    23,\n    22,\n    14,\n    15,\n    21,\n    20,\n    8,\n    9,\n    25,\n    24,\n    6,\n    7,\n    3,\n    2,\n    0,\n    1,\n    11,\n    10,\n    4,\n    5,\n    19,\n    18,\n    16,\n    17,\n)\n\n\ndef pil_to_cv2(image: Image.Image, flag: int = cv2.COLOR_RGB2BGR) -> np.ndarray:\n    """把 Pillow 图像转换为 OpenCV 图像。"""\n\n    return cv2.cvtColor(np.asarray(image), flag)\n\n\ndef set_image_debug(enabled: bool) -> None:\n    global HTTP_DEBUG\n    HTTP_DEBUG = enabled\n\n\ndef detect_gap_distance(background: Image.Image, slider: Image.Image) -> int:\n    """识别缺口位置并返回滑块移动距离。"""\n\n    gray_background = pil_to_cv2(background, cv2.COLOR_BGR2GRAY)\n    gray_slider = pil_to_cv2(slider, cv2.COLOR_BGR2GRAY)\n\n    edge_background = cv2.Canny(gray_background, 255, 255)\n    edge_slider = cv2.Canny(gray_slider, 255, 255)\n\n    result = cv2.matchTemplate(edge_background, edge_slider, cv2.TM_CCOEFF_NORMED)\n    max_location = cv2.minMaxLoc(result)[3]\n    return int(max_location[0])\n\n\ndef restore_geetest_image(input_path: str | Path, output_path: str | Path) -> None:\n    """按照极验切片顺序还原背景图。"""\n\n    with Image.open(input_path) as source:\n        restored = Image.new("RGB", (260, 160))\n        for index, block_index in enumerate(RESTORE_ORDER):\n            source_x = block_index % 26 * 12 + 1\n            source_y = 80 if block_index > 25 else 0\n            tile = source.crop((source_x, source_y, source_x + 10, source_y + 80))\n            target_x = index % 26 * 10\n            target_y = 80 if index > 25 else 0\n            restored.paste(tile, (target_x, target_y))\n        restored.save(output_path)\n\n\ndef _download_file(relative_path: str, target: Path) -> None:\n    url = f"{STATIC_HOST}{relative_path}"\n    response = requests.get(url, timeout=REQUEST_TIMEOUT)\n    response.raise_for_status()\n    if HTTP_DEBUG:\n        print(f"[图片下载] 状态码={response.status_code} 文件={relative_path}")\n    target.write_bytes(response.content)\n\n\ndef download_picture(bg: str, fullbg: str, slice_image: str) -> int:\n    """下载并还原验证码图片，返回识别出的缺口距离。"""\n\n    with TemporaryDirectory(prefix="geetest_") as temp_dir:\n        temp_path = Path(temp_dir)\n        bg_path = temp_path / "bg.jpg"\n        fullbg_path = temp_path / "fullbg.jpg"\n        slice_path = temp_path / "slice.png"\n\n        _download_file(bg, bg_path)\n        restore_geetest_image(bg_path, bg_path)\n\n        _download_file(fullbg, fullbg_path)\n        restore_geetest_image(fullbg_path, fullbg_path)\n\n        _download_file(slice_image, slice_path)\n\n        with Image.open(fullbg_path) as background, Image.open(slice_path) as slider:\n            return detect_gap_distance(background, slider)\n\n\npilImgToCv2 = pil_to_cv2\nshibie = detect_gap_distance\n\n__all__ = [\n    "detect_gap_distance",\n    "download_picture",\n    "pilImgToCv2",\n    "pil_to_cv2",\n    "restore_geetest_image",\n    "set_image_debug",\n    "shibie",\n]\n',
    "network": 'from __future__ import annotations\n\nimport json\nimport re\nimport time\nfrom typing import Any\n\nimport requests\n\nREQUEST_TIMEOUT = 15\nHTTP_DEBUG = True\nSESSION = requests.Session()\nBASE_HEADERS = {\n    "accept-language": "zh-CN,zh;q=0.9",\n    "sec-ch-ua": \'"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"\',\n    "sec-ch-ua-mobile": "?0",\n    "sec-ch-ua-platform": \'"Windows"\',\n    "user-agent": (\n        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "\n        "AppleWebKit/537.36 (KHTML, like Gecko) "\n        "Chrome/140.0.0.0 Safari/537.36"\n    ),\n}\nJSONP_PATTERN = re.compile(r"\\((.*)\\)$")\n\n\ndef set_http_debug(enabled: bool) -> None:\n    global HTTP_DEBUG\n    HTTP_DEBUG = enabled\n\n\ndef _timestamp_ms() -> str:\n    return str(int(round(time.time() * 1000)))\n\n\ndef _jsonp_callback() -> str:\n    return f"geetest_{_timestamp_ms()}"\n\n\ndef _build_headers(**extra: str) -> dict[str, str]:\n    headers = BASE_HEADERS.copy()\n    headers.update(extra)\n    return headers\n\n\ndef _summarize_value(value: Any) -> Any:\n    if isinstance(value, str):\n        if len(value) <= 48:\n            return value\n        return f"{value[:16]}...{value[-8:]}"\n    if isinstance(value, list):\n        if len(value) <= 10:\n            return value\n        return f"<list len={len(value)}>"\n    if isinstance(value, dict):\n        return {key: _summarize_value(item) for key, item in value.items()}\n    return value\n\n\ndef _log_result(label: str, **fields: Any) -> None:\n    if not HTTP_DEBUG:\n        return\n    payload = json.dumps(\n        {key: _summarize_value(value) for key, value in fields.items()},\n        ensure_ascii=False,\n        separators=(",", ":"),\n    )\n    print(f"[接口][{label}] {payload}")\n\n\ndef _parse_jsonp(text: str) -> dict[str, Any]:\n    match = JSONP_PATTERN.search(text)\n    if not match:\n        raise ValueError("Unable to parse JSONP response")\n    return json.loads(match.group(1))\n\n\ndef _get(\n    label: str,\n    url: str,\n    *,\n    params: dict[str, Any] | None = None,\n    headers: dict[str, str] | None = None,\n) -> requests.Response:\n    response = SESSION.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)\n    response.raise_for_status()\n    return response\n\n\ndef get_challenge_gt() -> tuple[str, str]:\n    response = _get(\n        "register-slide",\n        "https://demos.geetest.com/gt/register-slide",\n        params={"t": _timestamp_ms()},\n        headers=_build_headers(\n            **{\n                "accept": "application/json, text/javascript, */*; q=0.01",\n                "priority": "u=1, i",\n                "referer": "https://demos.geetest.com/slide-float.html",\n                "sec-fetch-dest": "empty",\n                "sec-fetch-mode": "cors",\n                "sec-fetch-site": "same-origin",\n                "x-requested-with": "XMLHttpRequest",\n            }\n        ),\n    )\n    data = response.json()\n    _log_result("注册", 状态码=response.status_code, gt=data["gt"], challenge=data["challenge"])\n    return data["gt"], data["challenge"]\n\n\ndef get_js_address(gt: str) -> dict[str, Any]:\n    response = _get(\n        "gettype",\n        "https://apiv6.geetest.com/gettype.php",\n        params={"gt": gt, "callback": _jsonp_callback()},\n        headers=_build_headers(\n            **{\n                "accept": "*/*",\n                "referer": "https://demos.geetest.com/",\n                "sec-fetch-dest": "script",\n                "sec-fetch-mode": "no-cors",\n                "sec-fetch-site": "same-site",\n            }\n        ),\n    )\n    data = _parse_jsonp(response.text)\n    _log_result(\n        "类型",\n        状态码=response.status_code,\n        status=data.get("status"),\n        type=data.get("data", {}).get("type"),\n        api_server=data.get("data", {}).get("api_server"),\n    )\n    return data\n\n\ndef get_c_s(gt: str, challenge: str, w: str) -> tuple[list[int], str]:\n    response = _get(\n        "get-c-s",\n        "https://apiv6.geetest.com/get.php",\n        params={\n            "gt": gt,\n            "challenge": challenge,\n            "lang": "zh-cn",\n            "pt": 0,\n            "client_type": "web",\n            "w": w,\n            "callback": _jsonp_callback(),\n        },\n        headers=_build_headers(\n            **{\n                "accept": "*/*",\n                "referer": "https://demos.geetest.com/",\n                "sec-fetch-dest": "script",\n                "sec-fetch-mode": "no-cors",\n                "sec-fetch-site": "same-site",\n            }\n        ),\n    )\n    data = _parse_jsonp(response.text)["data"]\n    _log_result("参数", 状态码=response.status_code, c=data["c"], s=data["s"])\n    return data["c"], data["s"]\n\n\ndef req_slide(gt: str, challenge: str, w2: str) -> None:\n    response = _get(\n        "slide-entry",\n        "https://api.geevisit.com/ajax.php",\n        params={\n            "gt": gt,\n            "challenge": challenge,\n            "lang": "zh-cn",\n            "pt": 0,\n            "client_type": "web",\n            "w": w2,\n            "callback": _jsonp_callback(),\n        },\n        headers=_build_headers(\n            **{\n                "Accept": "*/*",\n                "Connection": "keep-alive",\n                "Referer": "https://demos.geetest.com/",\n                "Sec-Fetch-Dest": "script",\n                "Sec-Fetch-Mode": "no-cors",\n                "Sec-Fetch-Site": "cross-site",\n                "Sec-Fetch-Storage-Access": "active",\n            }\n        ),\n    )\n    data = _parse_jsonp(response.text)\n    _log_result("进入滑块", 状态码=response.status_code, result=data.get("data", {}).get("result"))\n\n\ndef get_picture(gt: str, challenge: str) -> tuple[str, str, list[int], str, str, str]:\n    response = _get(\n        "get-picture",\n        "https://api.geevisit.com/get.php",\n        params={\n            "is_next": "true",\n            "type": "slide3",\n            "gt": gt,\n            "challenge": challenge,\n            "lang": "zh-cn",\n            "https": "true",\n            "protocol": "https://",\n            "offline": "false",\n            "product": "embed",\n            "api_server": "api.geevisit.com",\n            "isPC": "true",\n            "autoReset": "true",\n            "width": "100%",\n            "callback": _jsonp_callback(),\n        },\n        headers=_build_headers(\n            **{\n                "Accept": "*/*",\n                "Connection": "keep-alive",\n                "Referer": "https://demos.geetest.com/",\n                "Sec-Fetch-Dest": "script",\n                "Sec-Fetch-Mode": "no-cors",\n                "Sec-Fetch-Site": "cross-site",\n                "Sec-Fetch-Storage-Access": "active",\n            }\n        ),\n    )\n    data = _parse_jsonp(response.text)\n    _log_result(\n        "图片",\n        状态码=response.status_code,\n        bg=data["bg"],\n        fullbg=data["fullbg"],\n        slice=data["slice"],\n        challenge=data["challenge"],\n    )\n    return data["bg"], data["fullbg"], data["c"], data["s"], data["slice"], data["challenge"]\n\n\ndef req_end(gt: str, challenge: str, w: str) -> str:\n    response = _get(\n        "final-check",\n        "https://api.geevisit.com/ajax.php",\n        params={\n            "gt": gt,\n            "challenge": challenge,\n            "lang": "zh-cn",\n            "$_BCm": 0,\n            "client_type": "web",\n            "w": w,\n            "callback": _jsonp_callback(),\n        },\n        headers=_build_headers(\n            **{\n                "Accept": "*/*",\n                "Connection": "keep-alive",\n                "Referer": "https://demos.geetest.com/",\n                "Sec-Fetch-Dest": "script",\n                "Sec-Fetch-Mode": "no-cors",\n                "Sec-Fetch-Site": "cross-site",\n                "Sec-Fetch-Storage-Access": "active",\n            }\n        ),\n    )\n    data = _parse_jsonp(response.text)\n    _log_result(\n        "终验",\n        状态码=response.status_code,\n        success=data.get("success"),\n        message=data.get("message"),\n        validate=data.get("validate"),\n        score=data.get("score"),\n    )\n    return data["message"]\n\n\n__all__ = [\n    "get_c_s",\n    "get_challenge_gt",\n    "get_js_address",\n    "get_picture",\n    "req_end",\n    "req_slide",\n    "set_http_debug",\n]\n',
    "solver": 'from __future__ import annotations\n\nimport json\nimport random\nimport time\n\nfrom .crypto import AES_O, RSA_jiami_r, encrypt_string, four_random_chart, geetest_base64_encode, simple_md5\nfrom .imaging import download_picture, set_image_debug\nfrom .network import get_c_s, get_challenge_gt, get_js_address, get_picture, req_end, req_slide, set_http_debug\nfrom .performance import generate_fake_performance_timing, get_slide_track\nfrom .trajectory import H, TrajectoryEncoder, compress_trajectory, generate_realistic_trajectory, process_mouse_trajectory\n\nINITIAL_INTERACTION_TRACE = "!!".join(["-1"] * 74)\nW1_PAYLOAD = {\n    "offline": False,\n    "new_captcha": True,\n    "product": "float",\n    "width": "300px",\n    "https": True,\n    "api_server": "apiv6.geetest.com",\n    "protocol": "https://",\n    "type": "fullpage",\n    "static_servers": ["static.geetest.com/", "static.geevisit.com/"],\n    "voice": "/static/js/voice.1.2.6.js",\n    "click": "/static/js/click.3.1.2.js",\n    "beeline": "/static/js/beeline.1.0.1.js",\n    "fullpage": "/static/js/fullpage.9.2.0-guwyxh.js",\n    "slide": "/static/js/slide.7.9.3.js",\n    "geetest": "/static/js/geetest.6.0.9.js",\n    "aspect_radio": {"slide": 103, "click": 128, "voice": 128, "beeline": 50},\n    "cc": 16,\n    "ww": True,\n    "i": INITIAL_INTERACTION_TRACE,\n}\nW2_EP = {\n    "v": "9.2.0-guwyxh",\n    "te": False,\n    "$_BBn": True,\n    "ven": "Google Inc. (AMD)",\n    "ren": "ANGLE (AMD, AMD Radeon RX 6750 GRE 12GB (0x000073DF) Direct3D11 vs_5_0 ps_5_0, D3D11)",\n    "em": {"ph": 0, "cp": 0, "ek": "11", "wd": 1, "nt": 0, "si": 0, "sc": 0},\n    "dnf": "dnf",\n    "by": 0,\n}\n\n\ndef _json_dumps(payload: dict) -> str:\n    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))\n\n\ndef _log(message: str, *, enabled: bool) -> None:\n    if enabled:\n        print(message)\n\n\ndef _mask_text(value: str, *, head: int = 8, tail: int = 8) -> str:\n    if len(value) <= head + tail:\n        return value\n    return f"{value[:head]}...{value[-tail:]} ({len(value)} chars)"\n\n\ndef _generate_seed() -> str:\n    return "".join(four_random_chart() for _ in range(4))\n\n\ndef _build_timing_payload() -> dict[str, int]:\n    timing = generate_fake_performance_timing()\n    return {\n        "a": timing["navigationStart"],\n        "b": timing["unloadEventStart"],\n        "c": timing["unloadEventEnd"],\n        "d": timing["redirectStart"],\n        "e": timing["redirectEnd"],\n        "f": timing["fetchStart"],\n        "g": timing["domainLookupStart"],\n        "h": timing["domainLookupEnd"],\n        "i": timing["connectStart"],\n        "j": timing["connectEnd"],\n        "k": timing["secureConnectionStart"],\n        "l": timing["requestStart"],\n        "m": timing["responseStart"],\n        "n": timing["responseEnd"],\n        "o": timing["domLoading"],\n        "p": timing["domInteractive"],\n        "q": timing["domContentLoadedEventStart"],\n        "r": timing["domContentLoadedEventEnd"],\n        "s": timing["domComplete"],\n        "t": timing["loadEventStart"],\n        "u": timing["loadEventEnd"],\n    }\n\n\ndef _encrypt_payload(payload: dict, seed: str) -> dict[str, str]:\n    plaintext = _json_dumps(payload)\n    return geetest_base64_encode(AES_O(plaintext, seed))\n\n\ndef get_w1(gt: str, challenge: str, str_16: str) -> str:\n    payload = W1_PAYLOAD.copy()\n    payload["gt"] = gt\n    payload["challenge"] = challenge\n    encrypted = _encrypt_payload(payload, str_16)\n    return encrypted["res"] + encrypted["end"] + RSA_jiami_r(str_16)\n\n\ndef get_w2(gt: str, challenge: str, c: list[int], s: str, str_16: str) -> str:\n    first_time = int(round(time.time() * 1000))\n    raw_trajectory = generate_realistic_trajectory(\n        start_x=random.randint(400, 600),\n        start_y=random.randint(400, 500),\n        end_x=853,\n        end_y=288,\n        start_time=first_time,\n    )\n    processed_trajectory = process_mouse_trajectory(raw_trajectory)["data"]\n    compressed_trajectory = compress_trajectory(processed_trajectory)\n    tt = encrypt_string(compressed_trajectory, c, s)\n    passtime = str(int(round(time.time() * 1000)) - first_time)\n    rp = simple_md5(gt + challenge + passtime)\n\n    payload = {\n        "lang": "zh-cn",\n        "type": "fullpage",\n        "tt": tt,\n        "light": "DIV_0",\n        "s": "c7c3e21112fe4f741921cb3e4ff9f7cb",\n        "h": "321f9af1e098233dbd03f250fd2b5e21",\n        "hh": "39bd9cad9e425c3a8f51610fd506e3b3",\n        "hi": "09eb21b3ae9542a9bc1e8b63b3d9a467",\n        "vip_order": -1,\n        "ct": -1,\n        "ep": {\n            **W2_EP,\n            "fp": raw_trajectory[0],\n            "lp": raw_trajectory[-1],\n            "tm": _build_timing_payload(),\n        },\n        "passtime": int(passtime),\n        "rp": rp,\n        "captcha_token": "112439067",\n        "tsfq": "xovrayel",\n    }\n    encrypted = _encrypt_payload(payload, str_16)\n    return encrypted["res"] + encrypted["end"] + encrypted["end"]\n\n\ndef get_w3(str_16: str, challenge: str, hkjl: int, c: list[int], s: str, gt: str) -> str:\n    encoder = TrajectoryEncoder()\n    trajectory, passtime = get_slide_track(hkjl)\n    userresponse = H(trajectory[-1][0], challenge)\n    aa = encoder.encrypt_string(encoder.encode(trajectory), c, s)\n    rp = simple_md5(gt + challenge[:32] + str(passtime))\n\n    payload = {\n        "lang": "zh-cn",\n        "userresponse": userresponse,\n        "passtime": passtime,\n        "imgload": 50,\n        "aa": aa,\n        "ep": {\n            "v": "7.9.3",\n            "$_BIT": False,\n            "me": True,\n            "tm": _build_timing_payload(),\n            "td": -1,\n        },\n        "h9s9": "1816378497",\n        "rp": rp,\n    }\n    encrypted = _encrypt_payload(payload, str_16)\n    return encrypted["res"] + RSA_jiami_r(str_16)\n\n\ndef run_solver(verbose: bool = True, http_debug: bool = True) -> str:\n    set_http_debug(http_debug)\n    set_image_debug(http_debug)\n\n    _log("[1/7] 生成种子", enabled=verbose)\n    str_16 = _generate_seed()\n    _log(f"  种子: {_mask_text(str_16)}", enabled=verbose)\n\n    _log("[2/7] 注册验证码", enabled=verbose)\n    gt, challenge = get_challenge_gt()\n    _log(f"  gt: {gt}", enabled=verbose)\n    _log(f"  challenge: {challenge}", enabled=verbose)\n\n    gettype_data = get_js_address(gt)\n    _log(\n        f"  类型字段: {\',\'.join(sorted(gettype_data.keys()))}",\n        enabled=verbose,\n    )\n\n    _log("[3/7] 获取加密参数", enabled=verbose)\n    w1 = get_w1(gt, challenge, str_16)\n    _log(f"  w1摘要: {_mask_text(w1, head=16, tail=12)}", enabled=verbose)\n    c, s = get_c_s(gt, challenge, w1)\n    _log(f"  c: {c}", enabled=verbose)\n    _log(f"  s: {s}", enabled=verbose)\n\n    _log("[4/7] 进入滑块", enabled=verbose)\n    w2 = get_w2(gt, challenge, c, s, str_16)\n    _log(f"  w2摘要: {_mask_text(w2, head=16, tail=12)}", enabled=verbose)\n    req_slide(gt, challenge, w2)\n\n    _log("[5/7] 获取图片", enabled=verbose)\n    bg, fullbg, c, s, slice_image, challenge = get_picture(gt, challenge)\n    _log(f"  背景图: {bg}", enabled=verbose)\n    _log(f"  完整图: {fullbg}", enabled=verbose)\n    _log(f"  滑块图: {slice_image}", enabled=verbose)\n    _log(f"  新challenge: {challenge}", enabled=verbose)\n\n    _log("[6/7] 识别缺口并生成终验参数", enabled=verbose)\n    hkjl = download_picture(bg, fullbg, slice_image)\n    _log(f"  缺口距离: {hkjl}", enabled=verbose)\n    w3 = get_w3(str_16, challenge, hkjl, c, s, gt)\n    _log(f"  w3摘要: {_mask_text(w3, head=16, tail=12)}", enabled=verbose)\n\n    _log("[7/7] 提交终验", enabled=verbose)\n    message = req_end(gt, challenge, w3)\n    print(f"[结果] {message}")\n    return message\n\n\n__all__ = ["get_w1", "get_w2", "get_w3", "run_solver"]\n',
}


def _ensure_embedded_geetest_modules() -> None:
    if "geetest.solver" in sys.modules:
        return

    geetest_pkg = sys.modules.get("geetest")
    if geetest_pkg is None:
        geetest_pkg = types.ModuleType("geetest")
        geetest_pkg.__path__ = []
        geetest_pkg.__package__ = "geetest"
        sys.modules["geetest"] = geetest_pkg

    for module_name in ("crypto", "trajectory", "performance", "imaging", "network", "solver"):
        full_name = f"geetest.{module_name}"
        if full_name in sys.modules:
            setattr(geetest_pkg, module_name, sys.modules[full_name])
            continue

        module = types.ModuleType(full_name)
        module.__file__ = f"<embedded geetest/{module_name}.py>"
        module.__package__ = "geetest"
        sys.modules[full_name] = module
        setattr(geetest_pkg, module_name, module)

        source = GEETEST_EMBEDDED_SOURCES[module_name]
        code = compile(source, module.__file__, "exec")
        exec(code, module.__dict__)


class GeetestProtocolSolver:
    def __init__(self, timeout: int, verbose: bool):
        self.timeout = timeout
        self.verbose = verbose

        self._generate_seed = None
        self._get_w1 = None
        self._get_w2 = None
        self._get_w3 = None
        self._get_c_s = None
        self._req_slide = None
        self._get_picture = None
        self._download_picture = None

        self._load_modules()

    def _load_modules(self) -> None:
        _ensure_embedded_geetest_modules()

        try:
            from geetest import imaging as imaging_module  # type: ignore
            from geetest import network as network_module  # type: ignore
            from geetest.imaging import download_picture, set_image_debug  # type: ignore
            from geetest.network import (  # type: ignore
                get_c_s,
                get_picture,
                req_slide,
                set_http_debug,
            )
            from geetest.solver import (  # type: ignore
                _generate_seed,
                get_w1,
                get_w2,
                get_w3,
            )
        except Exception as exc:
            raise RuntimeError(
                "导入内置 geetest 模块失败，请检查依赖是否安装："
                "requests opencv-python pillow numpy pycryptodome。"
            ) from exc

        network_module.REQUEST_TIMEOUT = self.timeout
        imaging_module.REQUEST_TIMEOUT = self.timeout
        set_http_debug(self.verbose)
        set_image_debug(self.verbose)

        self._generate_seed = _generate_seed
        self._get_w1 = get_w1
        self._get_w2 = get_w2
        self._get_w3 = get_w3
        self._get_c_s = get_c_s
        self._req_slide = req_slide
        self._get_picture = get_picture
        self._download_picture = download_picture

    @staticmethod
    def _parse_json_or_jsonp(text: str) -> Optional[Dict[str, Any]]:
        content = text.strip()
        if not content:
            return None
        try:
            data = json.loads(content)
            return data if isinstance(data, dict) else None
        except Exception:
            pass

        m = re.search(r"\((\{.*\})\)\s*$", content, flags=re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                return data if isinstance(data, dict) else None
            except Exception:
                return None

        m = re.search(r"(\{.*\})", content, flags=re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(1))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def solve(self, gt: str, challenge: str) -> Tuple[Optional[Dict[str, str]], str]:
        try:
            seed = self._generate_seed()
            w1 = self._get_w1(gt, challenge, seed)
            c, s = self._get_c_s(gt, challenge, w1)
            w2 = self._get_w2(gt, challenge, c, s, seed)
            self._req_slide(gt, challenge, w2)
            bg, fullbg, c2, s2, slice_image, new_challenge = self._get_picture(
                gt, challenge
            )
            distance = self._download_picture(bg, fullbg, slice_image)
            w3 = self._get_w3(seed, new_challenge, distance, c2, s2, gt)

            callback = f"geetest_{int(time.time() * 1000)}"
            params = {
                "gt": gt,
                "challenge": new_challenge,
                "lang": "zh-cn",
                "$_BCm": 0,
                "client_type": "web",
                "w": w3,
                "callback": callback,
            }
            resp = requests.get(
                "https://api.geevisit.com/ajax.php",
                params=params,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            parsed = self._parse_json_or_jsonp(resp.text)
            if parsed is None:
                return None, f"终验响应解析失败: HTTP {resp.status_code}"

            if parsed.get("success") == 1 and parsed.get("validate"):
                validate = str(parsed["validate"]).strip()
                if not validate:
                    return None, "终验成功但 validate 为空"
                return (
                    {
                        "geetest_challenge": str(new_challenge),
                        "geetest_validate": validate,
                        "geetest_seccode": f"{validate}|jordan",
                    },
                    "success",
                )

            message = str(parsed.get("message", "")).strip() or str(
                parsed.get("error", "")
            ).strip()
            if not message:
                message = "终验失败"
            return None, message
        except requests.RequestException as exc:
            return None, f"网络错误: {exc}"
        except Exception as exc:
            return None, f"协议求解异常: {exc}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="v2yun 自动登录"
    )
    parser.add_argument("--base-url", "--login-url", dest="base_url", default=BASE_URL)
    parser.add_argument("--account-env", default=DEFAULT_ACCOUNT_ENV)
    parser.add_argument("--account-retry", type=int, default=DEFAULT_ACCOUNT_RETRY)
    parser.add_argument("--captcha-retry", type=int, default=DEFAULT_CAPTCHA_RETRY)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.account_retry < 1:
        parser.error("--account-retry 必须 >= 1")
    if args.captcha_retry < 1:
        parser.error("--captcha-retry 必须 >= 1")
    if args.timeout < 1:
        parser.error("--timeout 必须 >= 1")
    return args


def get_login_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/auth/login"


def build_session(base_url: str) -> requests.Session:
    login_url = get_login_url(base_url)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Referer": login_url,
        }
    )
    return session


def get_script_cookie_file_path() -> str:
    script_abs_path = os.path.abspath(__file__)
    script_dir = os.path.dirname(script_abs_path)
    return os.path.join(script_dir, COOKIE_FILE_NAME)


def load_cookie_store(cookie_file_path: str) -> Dict[str, Dict[str, str]]:
    if not os.path.exists(cookie_file_path):
        return {}

    try:
        with open(cookie_file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as exc:
        print(f"[警告] 读取 cookie 文件失败：{exc}")
        return {}

    if not isinstance(raw, dict):
        return {}

    accounts = raw.get("accounts")
    source = accounts if isinstance(accounts, dict) else raw
    store: Dict[str, Dict[str, str]] = {}
    for email, info in source.items():
        if isinstance(email, str) and isinstance(info, dict):
            store[email] = {str(k): str(v) for k, v in info.items()}
    return store


def save_cookie_store(cookie_file_path: str, store: Dict[str, Dict[str, str]]) -> None:
    payload = {"accounts": store}
    with open(cookie_file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def format_expire_time_utc8(expire_in: str) -> str:
    try:
        ts = int(expire_in)
        utc8 = timezone(timedelta(hours=8))
        return datetime.fromtimestamp(ts, tz=utc8).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return expire_in


def is_cookie_expired(expire_in: str) -> bool:
    try:
        return int(expire_in) <= int(time.time())
    except Exception:
        return True


def extract_set_cookie_map(resp: requests.Response) -> Dict[str, str]:
    set_cookie_headers: List[str] = []
    raw_headers = getattr(resp.raw, "headers", None)
    if raw_headers is not None:
        if hasattr(raw_headers, "getlist"):
            set_cookie_headers = list(raw_headers.getlist("Set-Cookie"))
        elif hasattr(raw_headers, "get_all"):
            values = raw_headers.get_all("Set-Cookie")
            if values:
                set_cookie_headers = list(values)

    if not set_cookie_headers:
        fallback = resp.headers.get("Set-Cookie")
        if fallback:
            set_cookie_headers = [fallback]

    cookie_map: Dict[str, str] = {}
    for item in set_cookie_headers:
        token = item.split(";", 1)[0].strip()
        if not token or "=" not in token:
            continue
        key, value = token.split("=", 1)
        cookie_map[key.strip()] = value.strip()
    return cookie_map


def pick_required_cookies(cookie_map: Dict[str, str]) -> Tuple[Optional[Dict[str, str]], str]:
    result: Dict[str, str] = {}
    for key in REQUIRED_COOKIE_KEYS:
        value = str(cookie_map.get(key, "")).strip()
        if not value:
            return None, f"缺少必须 cookie: {key}"
        result[key] = value
    return result, "ok"


def build_cookie_header(cookies: Dict[str, str]) -> str:
    return "; ".join(f"{k}={cookies[k]}" for k in REQUIRED_COOKIE_KEYS if cookies.get(k))


def set_session_required_cookies(
    session: requests.Session, base_url: str, cookies: Dict[str, str]
) -> None:
    for key in REQUIRED_COOKIE_KEYS:
        value = cookies.get(key, "")
        if value:
            session.cookies.set(key, value)


def build_api_headers(base_url: str, cookies: Dict[str, str]) -> Dict[str, str]:
    base = base_url.rstrip("/")
    return {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": base,
        "Referer": f"{base}/user",
        "Cookie": build_cookie_header(cookies),
    }


def load_accounts_from_env(env_name: str) -> Tuple[List[Tuple[int, str, str]], int]:
    raw = os.getenv(env_name)
    if raw is None or not raw.strip():
        print(f"[错误] 环境变量 '{env_name}' 为空或缺失。")
        return [], 0

    accounts: List[Tuple[int, str, str]] = []
    invalid_lines = 0
    for line_no, original_line in enumerate(raw.splitlines(), start=1):
        line = original_line.strip()
        if not line:
            continue
        if line.count("&") != 1:
            invalid_lines += 1
            print(
                f"[警告] 第 {line_no} 行账号已忽略：只能包含一个 '&' -> {original_line!r}"
            )
            continue
        email, password = line.split("&", 1)
        email = email.strip()
        password = password.strip()
        if not email or not password:
            invalid_lines += 1
            print(f"[警告] 第 {line_no} 行账号已忽略：邮箱或密码为空。")
            continue
        accounts.append((line_no, email, password))
    return accounts, invalid_lines


def parse_gt_and_challenge(html: str) -> Tuple[Optional[str], Optional[str]]:
    gt_m = re.search(r'gt\s*:\s*"([0-9a-fA-F]+)"', html)
    ch_m = re.search(r'challenge\s*:\s*"([0-9a-fA-F]+)"', html)
    gt = gt_m.group(1) if gt_m else None
    challenge = ch_m.group(1) if ch_m else None
    return gt, challenge


def fetch_login_meta(
    session: requests.Session, base_url: str, timeout: int
) -> Tuple[Optional[str], Optional[str]]:
    login_url = get_login_url(base_url)
    resp = session.get(login_url, timeout=timeout)
    resp.raise_for_status()
    html = resp.text
    gt, challenge = parse_gt_and_challenge(html)
    return gt, challenge


def parse_json_or_jsonp(text: str) -> Optional[Dict[str, Any]]:
    content = text.strip()
    if not content:
        return None
    try:
        data = json.loads(content)
        return data if isinstance(data, dict) else None
    except Exception:
        pass

    m = re.search(r"\((\{.*\})\)\s*$", content, flags=re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    m = re.search(r"(\{.*\})", content, flags=re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def do_login(
    session: requests.Session,
    base_url: str,
    email: str,
    password: str,
    captcha_payload: Dict[str, str],
    timeout: int,
) -> Tuple[Optional[int], str, Dict[str, Any], requests.Response]:
    login_url = f"{base_url.rstrip('/')}/auth/login"
    payload = {
        "email": email,
        "passwd": password,
        "remember": "on",
        "code_2fa": "",
        "geetest_challenge": captcha_payload["geetest_challenge"],
        "geetest_validate": captcha_payload["geetest_validate"],
        "geetest_seccode": captcha_payload["geetest_seccode"],
    }
    resp = session.post(login_url, data=payload, timeout=timeout)
    parsed = parse_json_or_jsonp(resp.text)
    if parsed is None:
        return None, f"非 JSON 响应 (HTTP {resp.status_code})", {}, resp
    ret = parsed.get("ret")
    ret_int = ret if isinstance(ret, int) else None
    msg = str(parsed.get("msg", "")).strip()
    return ret_int, msg, parsed, resp


def post_authcode(
    session: requests.Session, base_url: str, cookies: Dict[str, str], timeout: int
) -> Tuple[Optional[int], str, Dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/user/authcode"
    headers = build_api_headers(base_url, cookies)
    resp = session.post(url, headers=headers, timeout=timeout)
    parsed = parse_json_or_jsonp(resp.text)
    if parsed is None:
        return None, f"非 JSON 响应 (HTTP {resp.status_code})", {}
    ret = parsed.get("ret")
    ret_int = ret if isinstance(ret, int) else None
    msg = str(parsed.get("msg", "")).strip()
    return ret_int, msg, parsed


def post_checkin(
    session: requests.Session, base_url: str, cookies: Dict[str, str], timeout: int
) -> Tuple[Optional[int], str, str]:
    url = f"{base_url.rstrip('/')}/user/checkin"
    headers = build_api_headers(base_url, cookies)
    resp = session.post(url, headers=headers, timeout=timeout)
    parsed = parse_json_or_jsonp(resp.text)
    if parsed is None:
        return None, f"非 JSON 响应 (HTTP {resp.status_code})", ""

    ret = parsed.get("ret")
    ret_int = ret if isinstance(ret, int) else None
    msg = str(parsed.get("msg", "")).strip()

    traffic_info = parsed.get("trafficInfo")
    un_used = ""
    if isinstance(traffic_info, dict):
        un_used = str(traffic_info.get("unUsedTraffic", "")).strip()
    return ret_int, msg, un_used


def is_twofa_message(msg: str) -> bool:
    lower = msg.lower()
    keywords = [
        "2fa",
        "otp",
        "two-factor",
        "二步",
        "两步",
        "动态码",
        "google authenticator",
    ]
    return any(k in lower for k in keywords)


def is_retryable_captcha_message(msg: str) -> bool:
    lower = msg.lower()
    keywords = [
        "captcha",
        "geetest",
        "verify",
        "点击按钮进行验证",
        "请点击",
        "验证",
        "网络不给力",
        "old challenge",
        "error_02",
        "error_03",
        "error_21",
        "error_23",
        "illegal challenge",
        "param decrypt error",
        "not proof",
        "forbidden",
        "fail",
    ]
    return any(k in lower for k in keywords)


@capture_output("v2yun运行结果")
def main() -> int:
    args = parse_args()
    accounts, invalid_lines = load_accounts_from_env(args.account_env)
    if not accounts:
        print("[错误] 未找到有效的账号。")
        return 1

    cookie_file_path = get_script_cookie_file_path()
    cookie_store = load_cookie_store(cookie_file_path)

    try:
        solver = GeetestProtocolSolver(
            timeout=args.timeout,
            verbose=args.verbose,
        )
    except Exception as exc:
        print(f"[错误] 初始化验证码求解器协议失败：{exc}")
        return 1

    print(
        f"[信息] 已加载 {len(accounts)} 个账号，无效行数：{invalid_lines}，"
        f"账号重试={args.account_retry}，验证码重试={args.captcha_retry}"
    )

    success_count = 0
    twofa_count = 0
    fail_count = 0

    for idx, (line_no, email, password) in enumerate(accounts, start=1):
        print(f"\n[账号 {idx}/{len(accounts)}] 行号={line_no}, 邮箱={email}")
        account_success = False
        account_twofa = False
        cached_cookie = cookie_store.get(email)
        base_url = args.base_url.rstrip("/")

        if cached_cookie:
            cookie_ok, cookie_msg = pick_required_cookies(cached_cookie)
            if not cookie_ok:
                print(f"  [Cookie] 本地 cookie 不完整：{cookie_msg}，即将重新登录。")
            elif is_cookie_expired(cookie_ok["expire_in"]):
                expire_show = format_expire_time_utc8(cookie_ok["expire_in"])
                print(f"  [Cookie] 本地 cookie 已过期（{expire_show}），即将重新登录。")
            else:
                session = build_session(base_url)
                set_session_required_cookies(session, base_url, cookie_ok)
                try:
                    ret, msg, _ = post_authcode(
                        session=session,
                        base_url=base_url,
                        cookies=cookie_ok,
                        timeout=args.timeout,
                    )
                    msg_show = msg if msg else "(空)"
                    print(f"  [Cookie校验] ret={ret}, msg={msg_show}")
                    if ret == 1:
                        ret_ci, msg_ci, un_used = post_checkin(
                            session=session,
                            base_url=base_url,
                            cookies=cookie_ok,
                            timeout=args.timeout,
                        )
                        if ret_ci == 1:
                            print(f"  [签到] 签到成功，{msg_ci}，当前剩余流量{un_used}")
                        elif ret_ci == 0:
                            print(f"  [签到] 签到失败，{msg_ci}")
                        else:
                            print(f"  [签到] 签到失败，{msg_ci if msg_ci else '未知响应'}")
                        account_success = True
                        success_count += 1
                        continue

                    print(f"  [Cookie] {msg_show}，触发重新登录。")
                except requests.RequestException as exc:
                    print(f"  [Cookie] 校验网络错误: {exc}，触发重新登录。")
                except Exception as exc:
                    print(f"  [Cookie] 校验异常: {exc}，触发重新登录。")

        for account_attempt in range(1, args.account_retry + 1):
            print(f"  [账号尝试 {account_attempt}] 开始")
            session = build_session(base_url)

            try:
                gt, challenge = fetch_login_meta(session, base_url, args.timeout)
                if not gt or not challenge:
                    print("  [账号尝试] 无法从登录页面解析 gt/challenge。")
                    if account_attempt < args.account_retry:
                        time.sleep(1.0)
                    continue

                for captcha_attempt in range(1, args.captcha_retry + 1):
                    if captcha_attempt > 1:
                        gt_new, challenge_new = fetch_login_meta(
                            session, base_url, args.timeout
                        )
                        if gt_new and challenge_new:
                            gt, challenge = gt_new, challenge_new

                    if args.verbose:
                        print(
                            f"    [验证码尝试 {captcha_attempt}] gt={gt}, challenge={challenge}"
                        )
                    else:
                        print(f"    [验证码尝试 {captcha_attempt}] 开始")

                    captcha_payload, solver_msg = solver.solve(gt, challenge)
                    if not captcha_payload:
                        print(f"    [验证码] 失败: {solver_msg}")
                        if captcha_attempt < args.captcha_retry:
                            time.sleep(0.8)
                            continue
                        break

                    ret, msg, _, login_resp = do_login(
                        session=session,
                        base_url=base_url,
                        email=email,
                        password=password,
                        captcha_payload=captcha_payload,
                        timeout=args.timeout,
                    )
                    msg_show = msg if msg else "(空)"
                    print(f"    [登录] 响应: ret={ret}, msg={msg_show}")

                    if ret == 1:
                        all_cookie_map = extract_set_cookie_map(login_resp)
                        required_cookies, cookie_msg = pick_required_cookies(all_cookie_map)
                        if not required_cookies:
                            print(f"    [登录] 登录成功但 cookie 校验失败：{cookie_msg}")
                            if captcha_attempt < args.captcha_retry:
                                time.sleep(0.8)
                                continue
                            break

                        cookie_store[email] = required_cookies
                        save_cookie_store(cookie_file_path, cookie_store)
                        expire_show = format_expire_time_utc8(required_cookies["expire_in"])
                        print(
                            f"    [登录] 账号{email}登录cookie已保存到配置文件中，过期时间:{expire_show}"
                        )

                        set_session_required_cookies(session, base_url, required_cookies)
                        ret_ci, msg_ci, un_used = post_checkin(
                            session=session,
                            base_url=base_url,
                            cookies=required_cookies,
                            timeout=args.timeout,
                        )
                        if ret_ci == 1:
                            print(f"    [签到] 签到成功，{msg_ci}，当前剩余流量{un_used}")
                        elif ret_ci == 0:
                            print(f"    [签到] 签到失败，{msg_ci}")
                        else:
                            print(f"    [签到] 签到失败，{msg_ci if msg_ci else '未知响应'}")

                        account_success = True
                        success_count += 1
                        print("    [登录] 登录成功")
                        break

                    if is_twofa_message(msg):
                        account_twofa = True
                        twofa_count += 1
                        print("    [跳过] 不支持开启了两步验证 (2FA) 的账号。")
                        break

                    if is_retryable_captcha_message(msg):
                        if captcha_attempt < args.captcha_retry:
                            time.sleep(0.8)
                            continue
                        break

                    break

                if account_success or account_twofa:
                    break

                if account_attempt < args.account_retry:
                    time.sleep(1.0)
                    continue
            except requests.RequestException as exc:
                print(f"  [账号尝试] 网络错误: {exc}")
                if account_attempt < args.account_retry:
                    time.sleep(1.0)
                    continue
            except Exception as exc:
                print(f"  [账号尝试] 未知错误: {exc}")
                if account_attempt < args.account_retry:
                    time.sleep(1.0)
                    continue

        if not account_success and not account_twofa:
            fail_count += 1
            print("  [失败] 账号在重试后仍然失败。")

    print("\n[统计摘要]")
    print(f"  成功: {success_count}")
    print(f"  失败: {fail_count}")
    print(f"  跳过 (2FA): {twofa_count}")
    print(f"  总计: {len(accounts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

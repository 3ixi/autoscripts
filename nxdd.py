#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本名称：奈雪点单签到
脚本作者：3iXi
创建时间：2026-01-23
抓包说明：打开小程序“奈雪点单”，登录后抓请求头 Authorization 中 Bearer 后面的 token 值。
环境变量：
        变量名：nxdd
        变量值：token（不含 Bearer 前缀），多账号换行分隔或用 # 分隔
奖励内容：奈雪币
"""

import base64
import hashlib
import hmac
import json
import os
import random
import time
from datetime import datetime, timezone, timedelta

try:
    from SendNotify import capture_output
except Exception as exc:
    print(f"[警告] 通知模块 SendNotify.py 导入失败：{exc}，将跳过通知推送。")

    def capture_output(title: str = "脚本运行结果"):
        def decorator(func):
            return func

        return decorator

import requests


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF XWEB/6945"
OPEN_ID = "QL6ZOftGzbziPlZwfiXM"
SIGN_SECRET = "sArMTldQ9tqU19XIRDMWz7BO5WaeBnrezA"


def split_accounts(value: str) -> list[str]:
    value = value.replace("#", "\n")
    tokens = []
    for line in value.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("Bearer "):
            line = line[len("Bearer ") :].strip()
        tokens.append(line)
    return tokens


def random_int_string(length: int) -> str:
    return "".join(random.choice("123456789") for _ in range(length))


def hmac_sha1_base64(secret: str, message: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def build_request_data(extra_params: dict) -> dict:
    nonce = random_int_string(6)
    timestamp = int(time.time())
    url_path = f"nonce={nonce}&openId={OPEN_ID}&timestamp={timestamp}"
    signature = hmac_sha1_base64(SIGN_SECRET, url_path)

    common = {
        "platform": "wxapp",
        "version": "5.1.8",
        "imei": "",
        "osn": "microsoft",
        "sv": "Windows 10 x64",
        "lang": "zh_CN",
        "currency": "CNY",
        "timeZone": "",
        "nonce": int(nonce),
        "openId": OPEN_ID,
        "timestamp": timestamp,
        "signature": signature,
    }
    params = {
        "businessType": 1,
        "brand": 26000252,
        "tenantId": 1,
        "channel": 2,
        "stallType": None,
        "storeId": None,
        **extra_params,
    }
    return {"common": common, "params": params}


def call_api(fn: str, url: str, token: str, body: dict | None = None, method: str = "POST") -> dict:
    headers = {
        "User-Agent": UA,
        "Authorization": f"Bearer {token}",
        "Referer": "https://tm-web.pin-dao.cn/",
        "Origin": "https://tm-web.pin-dao.cn",
    }
    payload = build_request_data(body or {}) if body is not None else None
    if method.upper() == "GET":
        response = requests.get(url, headers=headers, timeout=30)
    else:
        headers["Content-Type"] = "application/json"
        response = requests.post(url, headers=headers, data=json.dumps(payload, separators=(",", ":")), timeout=30)

    try:
        return response.json()
    except Exception:
        return {"code": -1, "message": f"非 JSON 返回: {response.text[:200]}"}


def china_date_parts() -> tuple[int, int, int]:
    now = datetime.now(timezone(timedelta(hours=8)))
    return now.year, now.month, now.day


def run_for_token(token: str) -> None:
    userinfo = call_api("baseUserinfo", "https://tm-web.pin-dao.cn/user/base-userinfo", token, {})
    if userinfo.get("code") != 0:
        raise RuntimeError(f"登录失败: {userinfo.get('message') or '未知错误'}")

    phone = str(userinfo.get("data", {}).get("phone") or "")
    masked_phone = f"{phone[:3]}****{phone[7:]}" if len(phone) >= 11 else (phone or "未知")
    print(f"登录成功: {masked_phone}")

    year, month, day = china_date_parts()
    sign_date = f"{year}-{month:02d}-01"
    today = f"{year}-{month:02d}-{day:02d}"

    sign_records = call_api(
        "signRecord",
        "https://tm-web.pin-dao.cn/user/sign/records",
        token,
        {"signDate": sign_date, "startDate": today},
    )
    if sign_records.get("code") != 0:
        print(f"查询签到失败: {sign_records.get('message') or '未知错误'}")
    else:
        status = bool(sign_records.get("data", {}).get("status"))
        count = sign_records.get("data", {}).get("signCount", "-")
        print(f"今天{'已' if status else '未'}签到，已签到{count}天")
        if not status:
            sign_save = call_api(
                "signSave",
                "https://tm-web.pin-dao.cn/user/sign/save",
                token,
                {"signDate": today},
            )
            if sign_save.get("code") == 0 and sign_save.get("data", {}).get("flag"):
                print("签到成功")
            else:
                print(f"签到失败: {sign_save.get('message') or '未知错误'}")

    account = call_api("userAccount", "https://tm-web.pin-dao.cn/user/account/user-account", token, {})
    if account.get("code") == 0:
        print(f"当前奈雪币: {account.get('data', {}).get('coin', '-')}")
    else:
        print(f"查询奈雪币失败: {account.get('message') or '未知错误'}")


@capture_output("奈雪点单签到运行结果")
def main() -> None:
    tokens = split_accounts(os.getenv("nxdd", ""))
    if not tokens:
        print("未找到环境变量 nxdd，请配置 token，多账号换行分隔或用 # 分隔")
        return

    print(f"共找到 {len(tokens)} 个账号")
    for index, token in enumerate(tokens, 1):
        print(f"\n--- 账号 {index} ---")
        try:
            run_for_token(token)
        except Exception as exc:
            print(f"失败: {exc}")
        if index < len(tokens):
            time.sleep(2)

    print("\n所有账号处理完成")


if __name__ == "__main__":
    main()

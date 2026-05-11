#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本名称：品赞签到
脚本作者：3iXi
创建时间：2026-02-24
使用说明：品赞代理每周领取 3 金币。
环境变量：
        变量名：ipzan
        变量值：账号&密码，多账号换行分隔或用 # 分隔。密码中不要包含 &
"""

import base64
import os
import random
import time

try:
    from SendNotify import capture_output
except Exception as exc:
    print(f"[警告] 通知模块 SendNotify.py 导入失败：{exc}，将跳过通知推送。")

    def capture_output(title: str = "脚本运行结果"):
        def decorator(func):
            return func

        return decorator

import requests


def split_accounts(value: str) -> list[str]:
    value = value.replace("#", "\n")
    return [line.strip() for line in value.splitlines() if line.strip()]


def parse_account(line: str) -> tuple[str, str] | None:
    parts = line.split("&")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        return None
    return parts[0].strip(), parts[1].strip()


def mask_phone(phone: str) -> str:
    if len(phone) <= 7:
        return phone
    return f"{phone[:3]}****{phone[-4:]}"


def random_hex(length: int) -> str:
    return "".join(random.choice("0123456789abcdef") for _ in range(length))


def encrypt_account(phone: str, password: str) -> str:
    salt = "QWERIPZAN1290QWER"
    payload = f"{phone}{salt}{password}".encode("utf-8")
    b64_payload = base64.b64encode(payload).decode("ascii")
    part1 = b64_payload[:8]
    part2 = b64_payload[8:20]
    part3 = b64_payload[20:]
    noise = random_hex(400)
    return noise[:100] + part1 + noise[100:200] + part2 + noise[200:300] + part3 + noise[300:400]


def login(phone: str, password: str) -> tuple[bool, str, str]:
    url = "https://service.ipzan.com/users-login"
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.ipzan.com",
        "Referer": "https://www.ipzan.com/login",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    }
    payload = {"account": encrypt_account(phone, password), "source": "ipzan-home-one"}
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if not response.ok:
        return False, "", f"HTTP {response.status_code}"
    data = response.json()
    if data.get("code") == 0:
        return True, data.get("data", {}).get("token", ""), ""
    return False, "", data.get("message") or "未知错误"


def precheck(url: str) -> None:
    headers = {
        "Accept": "*/*",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
        "Origin": "https://www.ipzan.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://www.ipzan.com/",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    try:
        requests.options(url, headers=headers, timeout=15)
    except Exception:
        pass


def auth_get(url: str, token: str) -> tuple[bool, dict | None, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Origin": "https://www.ipzan.com",
        "Referer": "https://www.ipzan.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    }
    response = requests.get(url, headers=headers, timeout=30)
    if not response.ok:
        return False, None, f"HTTP {response.status_code}"
    data = response.json()
    if data.get("code") == 0:
        return True, data.get("data"), ""
    return False, data.get("data"), data.get("message") or "未知错误"


def process_account(raw: str) -> None:
    parsed = parse_account(raw)
    if not parsed:
        print(f"账号格式错误，跳过：{raw}")
        return

    phone, password = parsed
    print(f"\n>>> 账号: {mask_phone(phone)}")

    ok, token, message = login(phone, password)
    if not ok:
        print(f"❌ 登录失败: {message}")
        return
    print("登录成功，准备开始签到...")

    receive_url = "https://service.ipzan.com/home/userWallet-receive"
    precheck(receive_url)
    ok, _, message = auth_get(receive_url, token)
    if ok:
        print("本周金币领取成功，到账会有一点延迟")
    elif "您已领取过了" in message:
        print(f"🔔 {message}")
    else:
        print(f"❌ 领取金币失败: {message}")

    wallet_url = "https://service.ipzan.com/home/userWallet-find"
    precheck(wallet_url)
    ok, data, message = auth_get(wallet_url, token)
    if ok and data:
        print(f"【{data.get('user_id')}】当前余额 {data.get('balance')}")
    else:
        print(f"❌ 查询余额失败: {message}")


@capture_output("品赞签到运行结果")
def main() -> None:
    accounts = split_accounts(os.getenv("ipzan", ""))
    if not accounts:
        print("未找到环境变量 ipzan，请配置 账号&密码，多账号换行分隔或用 # 分隔")
        return

    print(f"共找到 {len(accounts)} 个账号")
    for index, raw in enumerate(accounts, 1):
        print(f"\n========== 账号 {index} ==========")
        try:
            process_account(raw)
        except Exception as exc:
            print(f"❌ 执行异常: {exc}")
        if index < len(accounts):
            time.sleep(2)

    print("\n所有账号处理完成")


if __name__ == "__main__":
    main()

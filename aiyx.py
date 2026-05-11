#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本名称：爱隐形自动签到
脚本作者：3iXi
创建时间：2026-02-25
抓包说明：微信搜索小程序“爱隐形”，登录后抓包任意请求体中的 userid 值。
环境变量：
        变量名：aiyx
        变量值：userid，多账号换行分隔或用 # 分隔
奖励内容：金币，可兑换实物
"""

import hashlib
import os
import random
import string
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


BASE_URL = "https://japi.yinxingyanjing.com"
TOKEN = "4224D9FF108FE2BAB4B6F30964839B94"


def split_accounts(value: str) -> list[str]:
    value = value.replace("#", "\n")
    return [line.strip() for line in value.splitlines() if line.strip()]


def mask_user_id(user_id: str) -> str:
    return f"{user_id[:8]}***" if len(user_id) > 8 else user_id


def make_nonce(length: int = 16) -> str:
    chars = string.digits + string.ascii_letters
    return "".join(random.choice(chars) for _ in range(length))


def request_api(path: str, payload: dict) -> dict:
    timestamp = str(int(time.time()))
    noncestr = make_nonce()
    sign_raw = f"noncestr={noncestr}&timestamp={timestamp}&token={TOKEN}"
    signature = hashlib.md5(sign_raw.encode("utf-8")).hexdigest().upper()

    headers = {
        "timestamp": timestamp,
        "signature": signature,
        "sourcechannel": "Mina",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50(0x18003229) NetType/WIFI MiniProgramEnv/iPhone",
        "Content-Type": "application/json",
        "version": "2.0.1",
        "noncestr": noncestr,
        "Accept": "*/*",
        "Referer": "https://servicewechat.com/wx0a7972d739462c46/173/page-frame.html",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    response = requests.post(f"{BASE_URL}{path}", headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def process_account(user_id: str) -> None:
    print(f"\n[账号: {mask_user_id(user_id)}]")

    login_res = request_api(
        "/sso/login/baselogin",
        {"sourceChannel": "Mina", "UserId": user_id, "login_type": "MemberCenter"},
    )
    if login_res.get("error_code") != 10001:
        raise RuntimeError(f"登录失败: {login_res.get('error_msg') or '未知错误'}")
    print(f"账号 {login_res.get('data', {}).get('username', '未知')} 登录成功")

    sign_list_res = request_api(
        "/user/sigouser/getsignlist",
        {"sourcechannel": "Mina", "user_id": user_id},
    )
    if sign_list_res.get("error_code"):
        raise RuntimeError(f"获取签到列表失败: {sign_list_res.get('error_msg')}")

    today_info = sign_list_res.get("data", {}).get("todaySignInfo", {})
    is_sign = today_info.get("isSign")
    sign_msg = today_info.get("msg", "")
    print(f"今日{'已' if is_sign == 1 else '未'}签到，{sign_msg}")

    if is_sign == 0:
        sign_res = request_api(
            "/user/sigouser/sign-in",
            {"user_id": user_id, "source_channel": "Mina"},
        )
        if sign_res.get("error_code"):
            print(f"❌ 签到执行失败: {sign_res.get('error_msg')}")
        else:
            print("✅ 签到成功")

    asset_res = request_api("/user/user-info/getassetheaderinfo", {"user_id": user_id})
    if not asset_res.get("error_code"):
        print(f"当前总金币：{asset_res.get('data', {}).get('gold')}")
    else:
        print(f"⚠️ 获取金币信息失败: {asset_res.get('error_msg')}")


@capture_output("爱隐形自动签到运行结果")
def main() -> None:
    accounts = split_accounts(os.getenv("aiyx", ""))
    if not accounts:
        print("未找到环境变量 aiyx，请配置 userid，多账号换行分隔或用 # 分隔")
        return

    print(f"共找到 {len(accounts)} 个账号")
    for index, user_id in enumerate(accounts, 1):
        print(f"\n========== 账号 {index} ==========")
        try:
            process_account(user_id)
        except Exception as exc:
            print(f"❌ 执行出错: {exc}")
        if index < len(accounts):
            time.sleep(2)

    print("\n所有账号处理完成")


if __name__ == "__main__":
    main()

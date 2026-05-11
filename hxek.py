#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本名称：鸿星尔克签到
脚本作者：3iXi
创建时间：2026-01-23
抓包说明：打开小程序“鸿星尔克官方会员中心”，抓包请求体中的 memberId 字段值。
环境变量：
        变量名：hxek
        变量值：memberId，多账号换行分隔或用 # 分隔
奖励内容：积分，可兑换实物
"""

import hashlib
import os
import random
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

try:
    from SendNotify import capture_output
except Exception as exc:
    print(f"[警告] 通知模块 SendNotify.py 导入失败：{exc}，将跳过通知推送。")

    def capture_output(title: str = "脚本运行结果"):
        def decorator(func):
            return func

        return decorator

import requests


ENTERPRISE_ID = "ff8080817d9fbda8017dc20674f47fb6"
APP_ID = "wxa1f1fa3785a47c7d"
SECRET = "damogic8888"


def split_accounts(value: str) -> list[str]:
    value = value.replace("#", "\n")
    return [line.strip() for line in value.splitlines() if line.strip()]


def mask_member_id(member_id: str) -> str:
    if len(member_id) <= 6:
        return member_id
    return f"{member_id[:3]}****{member_id[-3:]}"


def china_timestamp() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def run_once(member_id: str) -> None:
    timestamp = china_timestamp()
    random_int = random.randint(1000000, 9999999)
    trans_id = f"{APP_ID}{timestamp}"
    sign_raw = (
        f"timestamp={timestamp}transId={APP_ID}{timestamp}"
        f"secret={SECRET}random={random_int}memberId={member_id}"
    )
    sign = hashlib.md5(sign_raw.encode("utf-8")).hexdigest()

    url = "https://hope.demogic.com/gic-wx-app/member_sign.json"
    headers = {
        "xweb_xhr": "1",
        "channelEntrance": "wx_app",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090551)XWEB/11177",
        "sign": ENTERPRISE_ID,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "*/*",
        "Referer": "https://servicewechat.com/wxa1f1fa3785a47c7d/60/page-frame.html",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    body = {
        "memberId": member_id,
        "cliqueId": "-1",
        "cliqueMemberId": "-1",
        "useClique": "0",
        "enterpriseId": ENTERPRISE_ID,
        "random": str(random_int),
        "sign": sign,
        "timestamp": timestamp,
        "transId": trans_id,
        "gicWxaVersion": "3.9.21.1",
        "launchOptions": '{"path":"pages/authorize/authorize","query":{},"scene":1256,"referrerInfo":{},"apiCategory":"default"}',
    }

    response = requests.post(url, headers=headers, data=urlencode(body), timeout=30)
    if not response.ok:
        print(f"❌ HTTP {response.status_code}: {response.text[:200]}")
        return

    data = response.json()
    errcode = data.get("errcode")
    if errcode == 0:
        result = data.get("response") or {}
        member_sign = result.get("memberSign") or {}
        print(
            f"✅ 签到成功，获得积分 {member_sign.get('integralCount', '未知')}，"
            f"连续签到 {member_sign.get('continuousCount', '未知')} 天，积分余额 {result.get('points', '未知')}"
        )
        return

    errmsg = (
        data.get("errmsg")
        or data.get("msg")
        or data.get("message")
        or (data.get("response") or {}).get("errmsg")
        or (data.get("response") or {}).get("msg")
        or ""
    )
    if errcode == 900001:
        print(f"❌ 签到失败(errcode=900001){'，errmsg=' + str(errmsg) if errmsg else ''}")
    else:
        print(f"❌ 签到结果未知, errcode={errcode}{'，errmsg=' + str(errmsg) if errmsg else ''}")
    print(f"调试: timestamp={timestamp}, random={random_int}, transIdTail={trans_id[-8:]}, signHead={sign[:8]}")


@capture_output("鸿星尔克签到运行结果")
def main() -> None:
    accounts = split_accounts(os.getenv("hxek", ""))
    if not accounts:
        print("未找到环境变量 hxek，多账号换行分隔或用 # 分隔")
        return

    print(f"共找到 {len(accounts)} 个账号")
    for index, member_id in enumerate(accounts, 1):
        print("\n" + "=" * 15)
        print(f"账号 {index}: {mask_member_id(member_id)}")
        print("=" * 15)
        try:
            run_once(member_id)
        except Exception as exc:
            print(f"❌ 处理过程中出现异常: {exc}")
        if index < len(accounts):
            time.sleep(2)

    print("\n所有账号处理完成")


if __name__ == "__main__":
    main()

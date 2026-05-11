#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本名称：铛铛一下签到抽奖答题
脚本作者：3iXi
创建时间：2026-03-06
抓包说明：打开小程序“旧衣服回收 铛铛一下”，登录后抓任意请求头中的 token 字段值。
环境变量：
        变量名：dd1x
        变量值：token 或 token#base_url=https://vues.dd1x.cn，每行一个账号
奖励内容：现金，满 0.3 可提现
"""

import base64
import json
import os
import time
import uuid
from dataclasses import dataclass
from urllib.parse import quote, urljoin, urlparse

try:
    from SendNotify import capture_output
except Exception as exc:
    print(f"[警告] 通知模块 SendNotify.py 导入失败：{exc}，将跳过通知推送。")

    def capture_output(title: str = "脚本运行结果"):
        def decorator(func):
            return func

        return decorator

import requests


DEFAULT_BASE_URL = "https://vues.dd1x.cn"
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541022) XWEB/16467",
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Referer": "https://servicewechat.com/wxe378d2d7636c180e/801/page-frame.html",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


@dataclass
class AccountConfig:
    token: str
    base_url: str
    raw: str


def split_accounts(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def parse_account_line(line: str) -> AccountConfig | None:
    parts = [part.strip() for part in line.split("#") if part.strip()]
    if not parts:
        return None

    token = parts[0]
    base_url = DEFAULT_BASE_URL
    for part in parts[1:]:
        if part.lower().startswith("base_url="):
            base_url = part.split("=", 1)[1].strip()

    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return AccountConfig(token=token, base_url=f"{parsed.scheme}://{parsed.netloc}", raw=line)


def decode_openid_from_jwt(token: str) -> str:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return ""
        payload = parts[1].replace("-", "+").replace("_", "/")
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.b64decode(payload).decode("utf-8"))
        return data.get("openid") or data.get("openId") or ""
    except Exception:
        return ""


def assert_ok(resp: dict) -> None:
    if resp.get("code") == 0:
        return
    raise RuntimeError(str(resp.get("msg") or resp.get("message") or "请求失败"))


def call_api(acc: AccountConfig, method: str, path: str, body: dict | list | None = None) -> dict:
    url = urljoin(acc.base_url, path)
    headers = {**COMMON_HEADERS, "token": acc.token}
    if method.upper() == "GET":
        response = requests.get(url, headers=headers, timeout=30)
    else:
        response = requests.post(url, headers=headers, json=body or {}, timeout=30)

    text = response.text
    try:
        return response.json()
    except Exception as exc:
        return {"code": -1, "msg": f"JSON解析失败: {exc}; body={text[:500]}{'...' if len(text) > 500 else ''}"}


def api_get(acc: AccountConfig, path: str) -> dict:
    return call_api(acc, "GET", path)


def api_post(acc: AccountConfig, path: str, body: dict | list | None = None) -> dict:
    return call_api(acc, "POST", path, body)


def send_tracking(open_id: str, path: str, action: str, page_query_obj: dict | None = None, random_args: dict | None = None) -> None:
    payload = {
        "type": "1",
        "platform": "weapp",
        "appLaunch": {
            "path": "pages/index/index",
            "query": {},
            "scene": 1256,
            "referrerInfo": {},
            "apiCategory": "default",
        },
        "pageQueryObj": page_query_obj or {},
        "appHeader": {
            "platformVersion": "4.1.0.34",
            "resolution": "978*519",
            "pixelRatio": 1.25,
            "os": "windows",
            "fontSizeSetting": 15,
            "deviceModel": "microsoft",
            "deviceBrand": "microsoft",
            "deviceManufacturer": "microsoft",
            "deviceManuid": "microsoft",
            "deviceName": "microsoft",
            "osVersion": "Windows 10 x64",
            "language": "zh_CN",
            "access": "wifi",
        },
        "path": path,
        "uuid": str(uuid.uuid4()),
        "randomArgs": random_args or {},
        "appid": "wxe378d2d7636c180e",
        "channelId": "154",
        "openId": open_id,
        "action": action,
    }
    try:
        requests.post("https://data.dd1x.cn/api/test_api", headers=COMMON_HEADERS, json=payload, timeout=15)
    except Exception:
        pass


def xcx_point(acc: AccountConfig, process_id: str, note: str, page_name: str) -> None:
    if not process_id:
        return
    try:
        api_get(acc, f"/front/xcxPoint?processId={process_id}&processNote={quote(note)}&channel=154&pageName={quote(page_name)}")
    except Exception:
        pass


def build_answer_payload(data) -> list[dict]:
    if not isinstance(data, list):
        return []
    payload = []
    for item in data:
        try:
            questions_id = int(item.get("id"))
            answer_id = int(item.get("correctAnswerId"))
        except Exception:
            continue
        payload.append({"answerId": answer_id, "questionsId": questions_id})
    return payload


def run_for_account(acc: AccountConfig) -> None:
    open_id = decode_openid_from_jwt(acc.token)

    print("正在初始化会话...")
    access_res = api_get(acc, "/front/accessXcx?channelId=154&processId=")
    process_id = str(access_res.get("data") or "")
    if process_id:
        print(f"会话初始化成功: {process_id}")
        api_get(acc, f"/front/accessXcx?channelId=154&processId={process_id}")
    else:
        print("警告: 未获取到 processId，部分任务可能失效")

    send_tracking(open_id, "pages/index/index", "page_show")
    send_tracking(open_id, "pages/index/index", "page_click", random_args={"event_name": "进入小程序"})
    xcx_point(acc, process_id, "进入小程序", "首页")

    user_info = api_get(acc, "/ali/getUserInfo")
    assert_ok(user_info)
    nick_name = str(user_info.get("data", {}).get("nickName") or "未知")
    print(f"账号【{nick_name}】Token有效")

    send_tracking(open_id, "pages/index/index", "page_show")
    member_info = api_get(acc, "/api/v2/get_member_info")
    assert_ok(member_info)
    print(f"当前余额{member_info.get('data', {}).get('money', '-')}元")

    sign = api_get(acc, "/api/v2/sign_join")
    if sign.get("code") == 0:
        print(f"签到成功，获得【{sign.get('data', {}).get('name', '未知奖励')}】")
        send_tracking(open_id, "pages/index/index", "page_click", random_args={"event_name": "首页-立即签到"})
        xcx_point(acc, process_id, "首页-立即签到", "首页")
    else:
        msg = str(sign.get("msg") or sign.get("message") or "签到失败")
        if "签" in msg and ("过" in msg or "已经" in msg):
            print("今天已经签到过，继续执行抽奖/答题任务")
        else:
            raise RuntimeError(msg)

    send_tracking(open_id, "pages/activity/turntable/turntable", "page_show")
    lottery_info = api_get(acc, "/front/activity/get_lottery_info?id=13&channelId=154")
    assert_ok(lottery_info)
    times = max(int(lottery_info.get("data", {}).get("member_count") or 0), 0)
    print(f"今日有{times}次抽奖机会")

    for _ in range(times):
        send_tracking(open_id, "pages/activity/turntable/turntable", "page_click", random_args={"event_name": "抽奖页-立即抽奖"})
        xcx_point(acc, process_id, "抽奖页-立即抽奖", "抽奖页")
        result = api_get(acc, "/front/activity/get_lottery_result?id=13")
        assert_ok(result)
        record_id = result.get("data", {}).get("record_id")
        print(f"获得奖励{result.get('data', {}).get('prizeName', '未知奖励')}")
        if record_id is not None:
            assert_ok(api_get(acc, f"/front/activity/update_lottery_result?id={quote(str(record_id))}"))

    print("开始获取今日题目...")
    send_tracking(open_id, "pages/find_page/index", "page_show")
    send_tracking(open_id, "pages/index/index", "page_click", random_args={"event_name": "底部导航-发现"})
    send_tracking(open_id, "pages/find_page/index", "page_click", random_args={"event_name": "回收问答-立即参与"})
    send_tracking(open_id, "pages/find_page/answerQues/index", "page_show")

    questions = api_get(acc, "/api/questions/get_questions")
    assert_ok(questions)
    answer_payload = build_answer_payload(questions.get("data"))
    if answer_payload:
        send_tracking(open_id, "pages/find_page/answerSelectQues/index", "page_show")
        judge = api_post(acc, "/api/questions/judge", answer_payload)
        assert_ok(judge)
        if judge.get("data") == 2:
            print("今日已经答过题了")
        else:
            print("答题提交完成")
            send_tracking(open_id, "pages/find_page/answerSelectQues/index", "page_click", random_args={"event_name": "提现说明-立即提现"})
            xcx_point(acc, process_id, "提现说明-立即提现", "回答问题页")

    send_tracking(open_id, "pages/mine/mine", "page_show")
    send_tracking(open_id, "pages/index/index", "page_click", random_args={"event_name": "底部导航-我的"})

    member_info = api_get(acc, "/api/v2/get_member_info")
    assert_ok(member_info)
    current_money = float(member_info.get("data", {}).get("money") or 0)
    print(f"任务完毕，当前余额{member_info.get('data', {}).get('money', '-')}元")

    if current_money < 0.3:
        return

    print("余额满足提现要求，准备提现...")
    send_tracking(open_id, "pages/mine/mine", "page_click", random_args={"event_name": "设置-我的钱包"})
    xcx_point(acc, process_id, "中心首页-我的钱包", "我的")
    send_tracking(open_id, "pages/mine/withdrawal/index", "page_show", page_query_obj={"channelId": "154"})
    xcx_point(acc, process_id, "进入钱包", "提现")
    send_tracking(open_id, "pages/mine/withdrawal/index", "page_click", random_args={"event_name": "钱包-提现"})
    xcx_point(acc, process_id, "钱包-提现", "提现")

    withdrawal_list = api_get(acc, "/api/h/get_withdrawal_trade_list")
    if isinstance(withdrawal_list, list):
        trade_list = withdrawal_list
    else:
        trade_list = withdrawal_list.get("data") if isinstance(withdrawal_list.get("data"), list) else []

    available = [item for item in trade_list if not item.get("disabled") and float(item.get("money") or 0) >= 0.3]
    if not available:
        print("没有满足提现金额(>=0.3元)的订单")
        return

    total_money = f"{sum(float(item.get('money') or 0) for item in available):.2f}"
    print(f"检测到可提现订单 {len(available)} 个，合计 {total_money} 元")
    withdraw_res = api_post(
        acc,
        "/api/h/withdrawal",
        {"totalMoney": total_money, "type": 1, "withdrawalDetailPojoList": available},
    )
    if withdraw_res.get("code") == 1:
        print(f"提现成功: {withdraw_res.get('msg') or '确定'}")
        send_tracking(open_id, "pages/mine/mine", "page_click", random_args={"event_name": "全选-提现成功"})
        xcx_point(acc, process_id, "全选-提现成功", "提现")
    else:
        print(f"提现失败: {withdraw_res.get('msg') or '未知错误'}")


@capture_output("铛铛一下签到抽奖答题运行结果")
def main() -> None:
    lines = split_accounts(os.getenv("dd1x", ""))
    if not lines:
        print("未找到环境变量 dd1x，请配置 token，每行一个账号")
        return

    accounts = []
    for line in lines:
        acc = parse_account_line(line)
        if acc:
            accounts.append(acc)
        else:
            print(f"账号配置格式错误，跳过：{line}")

    print("\n=== 任务开始 ===")
    print(f"配置账号总数: {len(accounts)}")
    for index, acc in enumerate(accounts, 1):
        print(f"\n--- 账号 {index} ---")
        try:
            run_for_account(acc)
        except Exception as exc:
            print(f"失败: {exc}")
        if index < len(accounts):
            time.sleep(2)

    print("\n=== 任务完成 ===")


if __name__ == "__main__":
    main()

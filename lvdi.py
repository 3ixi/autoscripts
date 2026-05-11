#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本名称：绿地酒店签到
脚本作者：3iXi
创建时间：2026-03-31
抓包说明：微信小程序“绿地尊享会”，登录时抓包
https://api.wx.gcihotel.net/guardian/api/member/memberLoginByMobileAndOpenId.json
网址参数中的 openid 值。
环境变量：
        变量名：lvdi
        变量值：openid，多账号换行分隔或用 # 分隔
奖励内容：积分
"""

import os
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


BASE_URL = "https://wx4a359c7b9ddf878b.wx.gcihotel.net"
COMMON_HEADERS = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541022) XWEB/16467",
    "Referer": "https://wx4a359c7b9ddf878b.wx.gcihotel.net/wechat/?/",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def split_accounts(value: str) -> list[str]:
    value = value.replace("#", "\n")
    return [line.strip() for line in value.splitlines() if line.strip()]


def mask_mobile(mobile: str) -> str:
    if len(mobile) <= 7:
        return mobile
    return f"{mobile[:3]}****{mobile[-4:]}"


def get_json(url: str) -> dict:
    response = requests.get(url, headers=COMMON_HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def post_json(url: str, payload: dict) -> dict:
    response = requests.post(url, headers=COMMON_HEADERS, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def get_sign_code() -> str:
    url = (
        f"{BASE_URL}/guardian/api/wechat/platform/sign/wechatSignConfig.json"
        "?appid=wx4a359c7b9ddf878b&componentAppid=wxe715bd146a4e468b"
    )
    data = get_json(url)
    if data.get("result") == 1 and data.get("retVal", {}).get("code"):
        sign_code = data["retVal"]["code"]
        print(f"签到活动ID：{sign_code}")
        return sign_code
    raise RuntimeError(f"获取签到活动配置失败: {data.get('msg') or '未知原因'}")


def claim_continuous_award(sign_code: str, openid: str, member_id: str, member_token: str) -> None:
    record_url = (
        f"{BASE_URL}/guardian/api/wechat/platform/sign/wechatSignRecord.json"
        f"?signCode={sign_code}&appid=wx4a359c7b9ddf878b&componentAppid=wxe715bd146a4e468b"
        f"&memberId={member_id}&openid={openid}&memberToken={member_token}"
    )
    record = get_json(record_url)
    if record.get("result") != 1:
        print(f"查询连续签到奖励失败: {record.get('msg') or '未知原因'}")
        return

    ret = record.get("retVal") or {}
    if ret.get("hasUnReceivedAward") != "F":
        return

    print("检测到可领取连续签到奖励，准备领取...")
    award_uuid = None
    sign_days_list = ret.get("signDaysList")
    if isinstance(sign_days_list, dict):
        for day_arr in sign_days_list.values():
            if not isinstance(day_arr, list):
                continue
            for item in day_arr:
                is_receive = item.get("isReceive")
                is_award = item.get("isAward")
                points = item.get("points")
                if (is_receive in ("F", False)) and (is_award == "T" or (isinstance(points, (int, float)) and points > 0)):
                    award_uuid = item.get("uuid") or item.get("signRecordUuid")
                    break
            if award_uuid:
                break

    if not award_uuid:
        award_uuid = (
            ret.get("awardRecordUuid")
            or (ret.get("awardRecord") or {}).get("uuid")
            or ((ret.get("awardRecordList") or [{}])[0]).get("awardRecordUuid")
            or ((ret.get("awardRecordList") or [{}])[0]).get("uuid")
            or ((ret.get("list") or [{}])[0]).get("awardRecordUuid")
            or ((ret.get("list") or [{}])[0]).get("uuid")
        )

    if not award_uuid:
        print("未找到可用的 awardRecordUuid，跳过领取")
        return

    claim_url = (
        f"{BASE_URL}/guardian/api/wechat/platform/sign/getWechatSignAward.json"
        f"?signCode={sign_code}&openid={openid}&awardRecordUuid={award_uuid}&memberId={member_id}"
        f"&appid=wx4a359c7b9ddf878b&componentAppid=wxe715bd146a4e468b&hotelGroupCode=GIHG&memberToken={member_token}"
    )
    claim = get_json(claim_url)
    if claim.get("result") == 1:
        print(f"领取成功，{claim.get('msg') or ''}")
    else:
        print(f"领取失败: {claim.get('msg') or '未知原因'}")


def process_account(openid: str, sign_code: str) -> None:
    login_url = (
        f"{BASE_URL}/guardian/api/member/memberLoginOpen.json"
        f"?hotelCode=0&hotelGroupCode=GIHG&hotelGroupId=1&openid={openid}"
        "&appid=wx17d27ce1cca04bd7&componentAppid=wxe715bd146a4e468b"
    )
    login = get_json(login_url)
    if login.get("result") != 1:
        print(f"❌ 登录失败: {login.get('msg') or '未知原因'}")
        return

    ret = login.get("retVal") or {}
    member_token = ret.get("memberToken")
    member_id = ret.get("memberId")
    mobile = ret.get("mobile", "")
    name = ret.get("name", "")
    print(f"登录成功，准备为 {name}({mask_mobile(mobile)}) 签到")

    sign_payload = {
        "signCode": sign_code,
        "openid": openid,
        "memberId": member_id,
        "memberName": name,
        "appid": "wx4a359c7b9ddf878b",
        "componentAppid": "wxe715bd146a4e468b",
        "hotelGroupCode": "GIHG",
        "memberToken": member_token,
    }
    sign = post_json(f"{BASE_URL}/guardian/api/wechat/platform/sign/wechatSign.json", sign_payload)
    if sign.get("result") == 1:
        print(f"✅ 签到成功，获得 {sign.get('retVal', {}).get('points') or 0} 积分")
    else:
        print(f"❌ 签到失败: {sign.get('msg') or '未知原因'}")

    try:
        claim_continuous_award(sign_code, openid, str(member_id), str(member_token))
    except Exception as exc:
        print(f"查询/领取连续签到奖励异常: {exc}")

    points_url = (
        f"{BASE_URL}/guardian/api/member/memberLoginOpen.json"
        f"?hotelCode=0&hotelGroupCode=GIHG&hotelGroupId=1&memberId={member_id}&openid={openid}"
        f"&appid=wx17d27ce1cca04bd7&componentAppid=wxe715bd146a4e468b&memberToken={member_token}"
    )
    points = get_json(points_url)
    if points.get("result") == 1:
        print(f"当前账号共有 {points.get('retVal', {}).get('pointBalance', 0)} 积分")
    else:
        print(f"获取积分信息失败: {points.get('msg') or '未知原因'}")


@capture_output("绿地酒店签到运行结果")
def main() -> None:
    openids = split_accounts(os.getenv("lvdi", ""))
    if not openids:
        print("未找到环境变量 lvdi，请配置 openid，多账号换行分隔或用 # 分隔")
        return

    try:
        sign_code = get_sign_code()
    except Exception as exc:
        print(f"获取签到配置请求异常: {exc}")
        return

    for index, openid in enumerate(openids, 1):
        print(f"\n[账号 {index}] openid: {openid[:4]}...{openid[-4:]}")
        try:
            process_account(openid, sign_code)
        except Exception as exc:
            print(f"❌ 运行异常: {exc}")
        if index < len(openids):
            time.sleep(2)

    print("\n所有账号处理完成")


if __name__ == "__main__":
    main()

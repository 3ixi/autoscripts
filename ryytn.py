#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本名称：认养一头牛签到
脚本作者：3iXi
创建时间：2026-03-27
抓包说明：打开小程序“认养一头牛官方商城”，抓请求头中的 X-Auth-Token 值。
环境变量：
        变量名：ryytn
        变量值：X-Auth-Token，多账号换行分隔或用 # 分隔
脚本功能：自动签到、自动尝试申请可申请的试用商品、查询中奖记录、社区答题、发帖后自动删帖
"""

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


BASE_URL = "https://www.milkcard.mall.ryytngroup.com"


def split_accounts(value: str) -> list[str]:
    value = value.replace("#", "\n")
    return [line.strip() for line in value.splitlines() if line.strip()]


def mask_token(token: str) -> str:
    if len(token) <= 12:
        return token
    return f"{token[:6]}****{token[-4:]}"


def mask_phone(phone: str) -> str:
    if len(phone) >= 11:
        return f"{phone[:3]}****{phone[-4:]}"
    return phone


def request_json(token: str, method: str, path: str, payload: dict | None = None) -> tuple[bool, str, dict | None]:
    url = f"{BASE_URL}{path}"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.61(0x18003d24) NetType/4G Language/zh_CN",
        "Referer": "https://servicewechat.com/wx0408f3f20d769a2f/305/page-frame.html",
        "X-Auth-Token": token,
        "Accept": "application/json",
    }

    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        else:
            response = requests.post(url, headers=headers, json=payload or {}, timeout=30)
    except Exception as exc:
        return False, f"请求异常: {exc}", None

    text = response.text
    if not response.ok:
        return False, f"HTTP {response.status_code}: {text[:200]}", None

    try:
        data = response.json()
    except Exception as exc:
        return False, f"JSON解析失败: {exc}; body={text[:500]}{'...' if len(text) > 500 else ''}", None

    if not isinstance(data, dict):
        return False, f"响应不是 JSON 对象: {text[:200]}", data
    if data.get("code") != 200:
        return False, f"请求失败: code={data.get('code')} msg={data.get('msg') or '未知错误'}", data
    return True, "ok", data


def check_checkin_status(token: str):
    return request_json(token, "POST", "/mall/xhr/task/checkin/save")


def get_checkin_rule(token: str):
    return request_json(token, "GET", "/mall/xhr/task/checkin/getRule")


def get_address_list(token: str):
    return request_json(token, "POST", "/mall/xhr/address/receive/list")


def get_trial_list(token: str):
    return request_json(token, "POST", "/mall/xhr/freeTrial/getList", {"pageNum": 1, "pageSize": 10, "statusList": [1, 2]})


def apply_trial(token: str, trial_id: int, address_id: int):
    return request_json(token, "POST", "/mall/xhr/freeTrial/apply", {"id": trial_id, "addressId": address_id})


def get_winning_records(token: str):
    return request_json(token, "POST", "/mall/xhr/freeTrialUser/getList", {"parentTabStatus": 1, "pageNum": 1, "pageSize": 10, "subTabStatus": 1})


def get_quiz_activities(token: str):
    return request_json(token, "GET", "/mall/xhr/quizActivity/activities")


def submit_quiz_answer(token: str, quiz_activity_id: int, user_answer: str):
    return request_json(token, "POST", "/mall/xhr/quizActivity/submit", {"quizActivityId": quiz_activity_id, "userAnswer": user_answer})


def get_recommend_items(token: str):
    return request_json(
        token,
        "POST",
        "/mall/xhr/community/home/recommend/item",
        {"recommendationId": 7, "sort": "personalized", "direction": "desc", "pageNum": 1, "pageSize": 3},
    )


def push_community_post(token: str, content: str, image_urls: list):
    return request_json(
        token,
        "POST",
        "/mall/xhr/community/posts/push",
        {
            "postId": None,
            "title": "",
            "content": content,
            "imageUrls": image_urls,
            "topicLabelNames": [],
            "communityTopicActivityId": None,
            "communitPostDraftId": None,
            "freeTrialCommentId": None,
            "productIds": [],
        },
    )


def delete_community_post(token: str, post_id: int):
    return request_json(token, "GET", f"/mall/xhr/community/posts/delete?postId={post_id}")


def beijing_today_0am() -> str:
    now = datetime.now(timezone(timedelta(hours=8)))
    return now.strftime("%Y-%m-%d 00:00:00")


def run_once(token: str) -> bool:
    success = True

    ok, message, checkin = check_checkin_status(token)
    if not ok:
        print(f"获取账号信息失败: {message}")
        return False

    checkin_data = checkin.get("data") or {}
    grade = checkin_data.get("grade")
    phone = str(checkin_data.get("phone") or "")
    point = checkin_data.get("point", 0)
    print(f"{mask_phone(phone)} 当前积分 {point}")

    ok, message, rule = get_checkin_rule(token)
    if ok:
        print("✅ 签到成功")
    else:
        print(f"❌ 签到失败: {message}")
        return False

    ok, message, addr = get_address_list(token)
    if not ok:
        print(f"获取收货地址失败: {message}")
        return False

    addresses = addr.get("data") if isinstance(addr.get("data"), list) else []
    if not addresses:
        print("需要先在小程序 我的-收货地址 中填写地址")
        return True

    address_id = int(addresses[0].get("id"))
    city_name = str(addresses[0].get("cityName") or "")

    ok, message, trial = get_trial_list(token)
    if not ok:
        print(f"获取试用商品列表失败: {message}")
        success = False
    else:
        trial_list = ((trial.get("data") or {}).get("list") or [])
        for item in trial_list:
            if item.get("freeTrialButton") != 3:
                continue
            grade_list = [str(x) for x in (item.get("gradeList") or [])]
            if grade is None or str(grade) not in grade_list:
                continue
            trial_id = int(item.get("id"))
            product_name = str(item.get("productName") or "")
            draw_time = str(item.get("drawTime") or "")
            print(f"【{product_name}】可申请试用，开奖时间 {draw_time}")
            ok, message, _ = apply_trial(token, trial_id, address_id)
            if ok:
                print(f"✅ 试用申请成功，收货地址 {city_name}")
            else:
                print(f"❌ 试用申请失败: {message}")

    ok, message, win = get_winning_records(token)
    if ok:
        records = ((win.get("data") or {}).get("list") or [])
        if not records:
            print("暂无中奖记录")
        else:
            for item in records:
                print(f"恭喜中奖【{item.get('productName') or ''}】，完成试用后需要提交试用报告，否则会取消下次中奖资格")
    else:
        print(f"查询中奖记录失败: {message}")

    try:
        run_quiz(token)
    except Exception as exc:
        print(f"❌ 社区答题异常: {exc}")
        success = False

    try:
        run_community_post(token)
    except Exception as exc:
        print(f"❌ 发帖种草异常: {exc}")
        success = False

    return success


def run_quiz(token: str) -> None:
    ok, message, quiz_res = get_quiz_activities(token)
    if not ok:
        print(f"获取社区答题题库失败: {message}")
        return

    activities = quiz_res.get("data") if isinstance(quiz_res.get("data"), list) else []
    today = beijing_today_0am()
    today_quiz = next((item for item in activities if item.get("relatedDate") == today), None)
    if not today_quiz:
        print("今日暂无社区答题题目")
        return

    print(f"获取到社区答题题目：{today_quiz.get('questionTitle')}")
    try:
        options = json.loads(today_quiz.get("options") or "[]")
    except Exception:
        print("❌ 解析答题选项失败")
        return
    if not options:
        print("未获取到题目选项，跳过答题")
        return

    selected = random.choice(options)
    selected_key = selected.get("key")
    print(f"准备随机提交答案{selected_key}：{selected.get('value')}")
    time.sleep(6 + random.random() * 2)

    ok, message, submit = submit_quiz_answer(token, int(today_quiz.get("id")), selected_key)
    if not ok:
        print(f"❌ 提交答题失败: {message}")
        return

    data = submit.get("data") or {}
    actual_correct_key = data.get("correctAnswer") or (selected_key if data.get("isCorrect") == 1 else "")
    if data.get("isCorrect") == 1:
        print(f"回答正确，获得{data.get('point', 0)}积分")
    else:
        print(f"答案错误{'，正确答案是' + str(actual_correct_key) if actual_correct_key else ''}，今日未获得积分")


def run_community_post(token: str) -> None:
    ok, message, recommend = get_recommend_items(token)
    if not ok:
        print(f"获取推荐内容失败: {message}")
        return

    items = ((recommend.get("data") or {}).get("list") or [])
    if not items:
        print("未获取到推荐帖子内容，跳过发帖")
        return

    item = random.choice(items)
    content = item.get("content") or ""
    image_urls = item.get("imageUrls") or []
    print(f"准备发帖，内容：{content[:10]}...")
    time.sleep(6 + random.random() * 2)

    ok, message, push_res = push_community_post(token, content, image_urls)
    if not ok:
        print(f"❌ 发帖失败: {message}")
        return

    post_id = (push_res.get("data") or None)
    print("发帖成功，准备删帖...")
    if not post_id:
        print("❌ 发帖响应中未获取到 postId，取消删帖")
        return

    ok, message, _ = delete_community_post(token, int(post_id))
    if ok:
        print("帖子删除成功")
        ok, _, final_check = check_checkin_status(token)
        if ok:
            print(f"操作完成，当前积分 {(final_check.get('data') or {}).get('point', 0)}")
    else:
        print(f"❌ 删帖失败: {message}")


@capture_output("认养一头牛签到运行结果")
def main() -> None:
    tokens = split_accounts(os.getenv("ryytn", ""))
    if not tokens:
        print("未找到环境变量 ryytn，请配置 X-Auth-Token，多账号换行分隔或用 # 分隔")
        return

    print(f"共找到 {len(tokens)} 个账号")
    has_failure = False
    for index, token in enumerate(tokens, 1):
        print("\n" + "=" * 15)
        print(f"账号 {index}: {mask_token(token)}")
        print("=" * 15)
        try:
            if not run_once(token):
                has_failure = True
        except Exception as exc:
            has_failure = True
            print(f"❌ 处理过程中出现异常: {exc}")
        if index < len(tokens):
            time.sleep(2 + random.random() * 2)

    print("\n所有账号处理完成")
    if has_failure:
        print("部分账号执行失败，请查看上方日志")


if __name__ == "__main__":
    main()

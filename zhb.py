#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中华保自动任务和任务提交脚本
脚本作者：3iXi
创建日期：2025-11-26
抓包描述: 开启抓包，打开小程序“中华保”，进去后抓包域名https://sfa.cic.cn ，复制请求头中的token字段值作为环境变量值
环境变量：
        变量名：zhb
        变量值：token
        多账号之间换行分隔
脚本奖励：积分，token有效期至少半年
"""

import os
import json
import hmac
import hashlib
import base64
import uuid
import time
import random
from datetime import datetime


try:
    from SendNotify import capture_output
except Exception as exc:
    print(f"[警告] 通知模块 SendNotify.py 导入失败：{exc}，将跳过通知推送。")

    def capture_output(title: str = "脚本运行结果"):
        def decorator(func):
            return func

        return decorator


import requests

BASE_URL = "https://sfa.cic.cn"
APP_ID = "4172b5dbae0c11ebb57c0242ac110003"
SECRET_KEY = "a0febe42a67811eba09f0242ac110003"
SIGN_KEY = "adf1d8eaa67811eba09f0242ac110003"
DEFAULT_PATH = "pages/home/home#pages/home/home#1256"

def generate_nonce():
    return str(uuid.uuid4())

def generate_timestamp():
    return str(int(time.time() * 1000))


def generate_signature(path, body, nonce, timestamp, token):
    sign_string = f"{path}{body}{nonce}{timestamp}{token}"
    
    hmac_obj = hmac.new(
        SIGN_KEY.encode('utf-8'),
        sign_string.encode('utf-8'),
        hashlib.sha256
    )
    
    signature = base64.b64encode(hmac_obj.digest()).decode('utf-8')
    return signature


def build_headers(path, token, body="", method="GET"):
    nonce = generate_nonce()
    timestamp = generate_timestamp()
    signature = generate_signature(path, body, nonce, timestamp, token)
    
    headers = {
        "Host": "sfa.cic.cn",
        "Connection": "keep-alive",
        "appId": APP_ID,
        "timestamp": timestamp,
        "signature": signature,
        "secretKey": SECRET_KEY,
        "nonce": nonce,
        "path": DEFAULT_PATH,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B)",
        "Content-Type": "application/json",
        "token": token
    }
    
    if method == "POST" and body:
        headers["Content-Length"] = str(len(body))
    
    return headers


def make_request(method, path, token, payload=None, custom_path=None):
    url = f"{BASE_URL}{path}"
    
    body = ""
    if method == "POST" and payload:
        body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
    
    headers = build_headers(path, token, body, method)
    
    if custom_path:
        headers["path"] = custom_path
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        else:
            response = requests.post(url, headers=headers, data=body.encode('utf-8'), timeout=30)
        
        result = response.json()
        
        if result.get("code") == "200":
            return True, result.get("data")
        else:
            error_msg = result.get("msg", "未知错误")
            # print(f"❌ 请求失败: {error_msg}")
            return False, None
            
    except Exception as e:
        print(f"❌ 请求异常: {str(e)}")
        return False, None


def mask_name(name):
    if not name or len(name) == 0:
        return "未实名用户"
    if len(name) == 1:
        return name
    return name[0] + "*" * (len(name) - 1)


class TokenExpiredException(Exception):
    pass


def get_user_name(token):
    url = f"{BASE_URL}/miniprogram/api/integral/v2/queryIntegralCardWindows?areaCode=510107"
    headers = build_headers("/miniprogram/api/integral/v2/queryIntegralCardWindows?areaCode=510107", token, "", "GET")
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        result = response.json()

        if result.get("code") != "200":
            error_msg = result.get("msg", "Token错误")
            print(f"❌ Token失效: {error_msg}")
            raise TokenExpiredException(error_msg)

        data = result.get("data")
        if data and isinstance(data, list) and len(data) > 0:
            return data[0].get("name", "未实名用户")
        return "未实名用户"
        
    except TokenExpiredException:
        raise
    except Exception as e:
        print(f"❌ 获取用户名失败: {str(e)}")
        raise TokenExpiredException(f"请求异常: {str(e)}")


def check_sign_status(token):
    success, data = make_request("GET", "/miniprogram/api/integral/v2/getSignInfo", token)
    if success and data:
        today_sign = data.get("todaySign", 0)
        initial_integral = data.get("totalIntegral", 0)
        return today_sign == 1, initial_integral
    return False, 0


def do_sign(token):
    today = datetime.now().strftime("%Y-%m-%d")
    payload = {
        "description": "签到",
        "integralDate": today,
        "type": 0
    }
    
    custom_path = "pages/home/home#pages/shoppingMall/huaBaoPark/huaBaoHome/index#1256"
    success, _ = make_request("POST", "/miniprogram/api/integral/v2/sign", token, payload, custom_path)
    
    if success:
        print(f"✅ {today}签到成功")
        return True
    return False


def get_task_list(token):
    custom_path = "pages/home/home#pages/shoppingMall/huaBaoPark/huaBaoHome/index#1256"
    success, data = make_request("GET", "/miniprogram/api/huabaopark/v6/getHomePage", token, custom_path=custom_path)
    
    if success and data:
        return data
    return None


def submit_task(token, task_type, point_strategy_id, task_name):
    payload = {
        "integralTaskTypeCd": task_type,
        "pointStrategyId": point_strategy_id
    }
    
    if task_type == 11:
        payload["answerPassed"] = True
    
    custom_path = "pages/home/home#pages/shoppingMall/huaBaoPark/dailyQuiz/index#1256"
    success, _ = make_request("POST", "/miniprogram/api/huabaopark/v6/completedTask", token, payload, custom_path)
    
    # if success:
    #     print(f"✅ 任务【{task_name}】提交完成")
    #     return True
    # else:
    #     print(f"❌ 任务【{task_name}】提交失败")
    #     return False
    return success


def receive_task_reward(token, task_id, task_name):
    payload = {"id": task_id}
    custom_path = "pages/home/home#pages/shoppingMall/huaBaoPark/huaBaoHome/index#1256"
    success, _ = make_request("POST", "/miniprogram/api/huabaopark/v6/receiveTaskIntegral", token, payload, custom_path)
    
    # if success:
    #     print(f"✅ 任务【{task_name}】奖励领取成功")
    #     return True
    # else:
    #     print(f"❌ 任务【{task_name}】奖励领取失败")
    #     return False
    return success


def get_final_integral(token, name, initial_integral=0):
    success, data = make_request("GET", "/miniprogram/api/integral/v2/getSignInfo", token)
    if success and data:
        total_integral = data.get("totalIntegral", 0)
        earned_integral = total_integral - initial_integral
        print(f"🎉 【{name}】今日新增{earned_integral}积分，当前总积分{total_integral}")
        return total_integral
    return 0


def process_account(token):
    print("=" * 35)
    
    # 1. 获取用户昵称
    name = get_user_name(token)
    masked_name = mask_name(name)
    print(f"👤 当前账号: 【{masked_name}】")
    
    # 2. 检查签到状态并获取初始积分
    is_signed, initial_integral = check_sign_status(token)
    if is_signed:
        print(f"✅ 【{masked_name}】今日已签到")
    else:
        print(f"⏰ 【{masked_name}】今日未签到")
        # 执行签到
        do_sign(token)
    
    # 3. 获取任务列表
    task_data = get_task_list(token)
    if not task_data:
        print("❌ 获取任务列表失败")
        return
    
    # 4. 提交未完成的任务
    tasks_to_submit = []
    
    for i in range(1, 4):
        task_key = f"showTask{i}"
        task = task_data.get(task_key)
        if task and task.get("status") == 0:
            if task.get("taskType") == 4 and task.get("pointStrategyId") == 9:
                print(f"🖕 跳过任务【{task.get('taskName')}】（无法自动完成）")
                continue
            tasks_to_submit.append({
                "taskType": task.get("taskType"),
                "pointStrategyId": task.get("pointStrategyId"),
                "taskName": task.get("taskName")
            })
    
    show_task_list = task_data.get("showTaskList", [])
    for task in show_task_list:
        if task.get("status") == 0:
            if task.get("taskType") == 4 and task.get("pointStrategyId") == 9:
                # print(f"🖕 跳过任务【{task.get('taskName')}】（无法自动完成）")
                continue
            tasks_to_submit.append({
                "taskType": task.get("taskType"),
                "pointStrategyId": task.get("pointStrategyId"),
                "taskName": task.get("taskName")
            })
    
    if tasks_to_submit:
        print(f"📝 发现{len(tasks_to_submit)}个待提交任务")
        print("⏳ 正在提交任务中，请稍后...")
        for task in tasks_to_submit:
            submit_task(token, task["taskType"], task["pointStrategyId"], task["taskName"])
            time.sleep(1)
    else:
        print("✅ 没有待提交的任务")
    
    # 5. 再次获取任务列表,领取奖励
    # print("🎁 开始领取任务奖励...")
    wait_time = random.uniform(3, 5)
    # print(f"⏳ 等待{wait_time:.1f}秒")
    time.sleep(wait_time)
    task_data = get_task_list(token)
    
    if task_data:
        tasks_to_receive = []
        
        for i in range(1, 4):
            task_key = f"showTask{i}"
            task = task_data.get(task_key)
            if task and task.get("status") == 2:
                tasks_to_receive.append({
                    "id": task.get("id"),
                    "taskName": task.get("taskName")
                })
        
        show_task_list = task_data.get("showTaskList", [])
        for task in show_task_list:
            if task.get("status") == 2:
                tasks_to_receive.append({
                    "id": task.get("id"),
                    "taskName": task.get("taskName")
                })
        
        # 领取奖励
        if tasks_to_receive:
            print(f"🎁 发现{len(tasks_to_receive)}个待领取奖励")
            print("⏳ 正在领取任务奖励，请稍后...")
            for task in tasks_to_receive:
                receive_task_reward(token, task["id"], task["taskName"])
                time.sleep(1)
        else:
            print("✅ 没有待领取的奖励")
    
    # 6. 获取最终积分
    get_final_integral(token, masked_name, initial_integral)
    print("=" * 35)


@capture_output("中华保自动任务")
def main():
    try:
        print("💪 中华保自动任务脚本")
        print(f"⏰ 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 35)
        
        env_tokens = os.getenv("zhb", "")
        if not env_tokens:
            print("❌ 未找到环境变量zhb，请先配置")
            return
        
        tokens = [t.strip() for t in env_tokens.split("\n") if t.strip()]
        
        if not tokens:
            print("❌ 环境变量zhb为空，请先配置")
            return
        
        print(f"🚩 共找到{len(tokens)}个账号")
        print("=" * 35)
        
        for idx, token in enumerate(tokens, 1):
            print(f"\n🔌 开始处理第{idx}个账号")
            try:
                process_account(token)
            except TokenExpiredException as e:
                print(f"⚠️ 跳过第{idx}个账号（Token失效）")
                print("=" * 35)
                continue

            time.sleep(2)
        
        print("\n✅ 所有账号处理完成!")
        
    except Exception as e:
        print(f"❌ 脚本运行出错: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

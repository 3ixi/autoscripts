#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
捷停车自动任务脚本
脚本作者: 3iXi
创建日期: 2025-07-09
需要依赖：pyjwt
抓包描述: 开启抓包，打开小程序“捷停车”，进去后抓包域名https://www.jslife.com.cn/wxhttp/weixin/xcx/get_openid_by_code ，复制响应数据中的token字段值作为环境变量值
环境变量：
        变量名：jtc
        变量值：token
        多账号之间用#分隔：token1#token2
脚本奖励：积分（抵扣停车费或优惠券）
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

try:
    import jwt
except ImportError:
    print("错误：未安装pyjwt依赖")
    sys.exit(1)

BASE_URL = "https://sytgate.jslife.com.cn"
HEADERS = {
    "Host": "sytgate.jslife.com.cn",
    "Connection": "keep-alive",
    "applicationVersion": "1.0.0",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) MicroMessenger/7.0.20.1781(0x6700143B)",
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Referer": "https://servicewechat.com/wx24b70f0ad2a9a89a/280/page-frame.html",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9"
}

def check_response(response_data):
    """检查响应是否正常"""
    if response_data.get("code") != "0" and response_data.get("resultCode") != "0":
        error_msg = response_data.get("message", "未知错误")
        print(f"请求失败：{error_msg}")
        return False
    return True

def parse_jwt(token):
    """解析JWT获取用户信息"""
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        sub_data = json.loads(decoded.get("sub", "{}"))
        user_id = sub_data.get("userId")
        open_id = sub_data.get("id")
        exp = decoded.get("exp")
        
        return user_id, open_id, exp
    except Exception as e:
        print(f"JWT解析失败：{e}")
        return None, None, None

def format_phone(phone):
    """格式化手机号，中间打码"""
    if len(phone) == 11:
        return f"{phone[:3]}****{phone[-4:]}"
    return phone

def format_timestamp(timestamp):
    """格式化时间戳为本地时间"""
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y/%m/%d %H:%M:%S")

def make_request(url, payload, token=None):
    """发送HTTP请求"""
    headers = HEADERS.copy()
    
    payload_str = json.dumps(payload, separators=(',', ':'))
    headers["Content-Length"] = str(len(payload_str.encode('utf-8')))
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"请求失败：{e}")
        return None

def get_user_info(open_id):
    """获取用户信息"""
    url = f"{BASE_URL}/core-gateway/user/query/attention/info"
    payload = {
        "h5Source": "WX_XCX_JTC",
        "openId": open_id
    }
    
    response_data = make_request(url, payload)
    if response_data and check_response(response_data):
        return response_data.get("obj", {})
    return None

def sign_in_task_query(user_id):
    """签到任务查询"""
    url = f"{BASE_URL}/base-gateway/integral/v2/sign-in-task/query"
    payload = {
        "userId": user_id,
        "platformType": "WX_XCX_JTC"
    }

    response_data = make_request(url, payload)
    if response_data and check_response(response_data):
        print("签到任务查询成功")
        return True
    else:
        print("签到任务查询失败")
        return False

def header_pop_query(user_id):
    """气泡奖励查询"""
    url = f"{BASE_URL}/base-gateway/integral/v2/show/header-pop/query"
    payload = {
        "userId": user_id,
        "platformType": "WX_XCX_JTC",
        "osType": "WINDOWS",
        "reqVersion": "V2.0"
    }

    response_data = make_request(url, payload)
    if response_data and check_response(response_data):
        # print("气泡奖励查询成功")
        return True
    else:
        print("气泡奖励查询失败")
        return False

def receive_sign_in_reward(user_id, token):
    """领取签到奖励"""
    url = f"{BASE_URL}/base-gateway/integral/v2/task/receive"
    payload = {
        "userId": user_id,
        "taskNo": "T00",
        "reqSource": "WX_XCX_JTC",
        "platformType": "WX_XCX_JTC",
        "osType": "WINDOWS",
        "token": token
    }

    response_data = make_request(url, payload)
    if response_data and check_response(response_data):
        reward = response_data.get("data", 0)
        if reward > 0:
            print(f"签到成功，获得{reward}捷停币")
        return reward
    else:
        print("签到奖励领取失败")
        return 0

def perform_sign_in(user_id, token):
    """执行签到操作"""
    print("开始执行签到...")

    if not sign_in_task_query(user_id):
        return False

    time.sleep(1)

    if not header_pop_query(user_id):
        return False

    time.sleep(1)

    reward = receive_sign_in_reward(user_id, token)

    print("签到操作完成")
    return True

def get_task_list(user_id):
    """获取任务列表"""
    url = f"{BASE_URL}/base-gateway/integral/v2/task/query"
    payload = {
        "userId": user_id,
        "platformType": "WX_XCX_JTC",
        "osType": "WINDOWS",
        "reqVersion": "V2.0"
    }

    response_data = make_request(url, payload)
    if response_data and check_response(response_data):
        return response_data.get("data", [])
    return []

def receive_task_reward(user_id, task_no, token):
    """领取任务奖励"""
    url = f"{BASE_URL}/base-gateway/integral/v2/task/receive"
    payload = {
        "userId": user_id,
        "taskNo": task_no,
        "reqSource": "WX_XCX_JTC",
        "platformType": "WX_XCX_JTC",
        "osType": "WINDOWS",
        "token": token
    }
    
    response_data = make_request(url, payload)
    if response_data and check_response(response_data):
        return response_data.get("data", 0)
    return 0

def complete_task(user_id, task_no, token):
    """完成任务"""
    url = f"{BASE_URL}/base-gateway/integral/v2/task/complete"
    payload = {
        "userId": user_id,
        "taskNo": task_no,
        "receiveTag": False,
        "reqSource": "WX_XCX_JTC",
        "platformType": "WX_XCX_JTC",
        "osType": "ANDROID",
        "token": token
    }
    
    response_data = make_request(url, payload)
    if response_data and check_response(response_data):
        return True
    return False

def get_balance(user_id, open_id):
    """获取账户余额"""
    url = f"{BASE_URL}/base-gateway/integral/v2/balance/query"
    payload = {
        "reqSource": "WX_XCX_JTC",
        "userId": user_id,
        "openId": open_id
    }
    
    response_data = make_request(url, payload)
    if response_data and check_response(response_data):
        return response_data.get("data", {})
    return {}

def process_account(token):
    """处理单个账号"""
    print(f"\n{'='*50}")
    
    user_id, open_id, exp = parse_jwt(token)
    if not user_id or not open_id:
        print("JWT解析失败，跳过此账号")
        return
    
    user_info = get_user_info(open_id)
    if not user_info:
        print("获取用户信息失败，跳过此账号")
        return
    
    telephone = user_info.get("telephone", "未知")
    formatted_phone = format_phone(telephone)
    exp_time = format_timestamp(exp)
    
    print(f"{formatted_phone}账号有效，过期时间{exp_time}")

    if not perform_sign_in(user_id, token):
        print("签到失败，但继续处理任务")

    time.sleep(1)

    task_data = get_task_list(user_id)
    if not task_data:
        print("获取任务列表失败")
        return
    
    receivable_tasks = []
    incomplete_tasks = []
    
    for task_group in task_data:
        task_type = task_group.get("taskType", "")
        task_list = task_group.get("taskList", [])
        
        for task in task_list:
            task_no = task.get("taskNo")
            task_status = task.get("taskStatus")
            show_title = task.get("showTitle", "")
            
            if task_status == "RECEIVE":
                receivable_tasks.append((task_no, show_title))
            elif task_status == "GOTO":
                # 新人任务排除T04（因为无法直接完成，接口会报错）
                if task_type == "新人任务" and task_no == "T04":
                    continue
                if task_type in ["新人任务", "每日任务"]:
                    incomplete_tasks.append((task_no, show_title))
    
    if receivable_tasks:
        print(f"发现{len(receivable_tasks)}个任务可以领取奖励")
        for task_no, show_title in receivable_tasks:
            reward = receive_task_reward(user_id, task_no, token)
            if reward > 0:
                print(f"成功领取{show_title}任务奖励{reward}个捷停币")
            time.sleep(1)
    
    if incomplete_tasks:
        print(f"开始完成{len(incomplete_tasks)}个未完成任务")
        completed_tasks = []
        
        for task_no, show_title in incomplete_tasks:
            if complete_task(user_id, task_no, token):
                print(f"成功完成任务：{show_title}")
                completed_tasks.append((task_no, show_title))
            time.sleep(1)
        
        if completed_tasks:
            print("开始领取新完成任务的奖励")
            for task_no, show_title in completed_tasks:
                reward = receive_task_reward(user_id, task_no, token)
                if reward > 0:
                    print(f"成功领取{show_title}任务奖励{reward}个捷停币")
                time.sleep(1)
    
    balance_info = get_balance(user_id, open_id)
    if balance_info:
        account_amt = balance_info.get("accountAmt", 0)
        deduct_amount = balance_info.get("deductAmount", 0)
        print(f"任务奖励领取完成，当前有{account_amt}个捷停币，最少可抵扣{deduct_amount}元")

def main():
    """主函数"""
    print("捷停车自动任务脚本启动")
    
    jtc_tokens = os.getenv("jtc")
    if not jtc_tokens:
        print("错误：未找到名为'jtc'的环境变量")
        print("请设置环境变量，多个Token用#分隔")
        sys.exit(1)
    
    tokens = [token.strip() for token in jtc_tokens.split("#") if token.strip()]
    
    if not tokens:
        print("错误：环境变量'jtc'为空")
        sys.exit(1)
    
    print(f"共找到{len(tokens)}个账号凭证")
    
    for i, token in enumerate(tokens, 1):
        print(f"\n处理第{i}个账号...")
        try:
            process_account(token)
        except Exception as e:
            print(f"处理第{i}个账号时出错：{e}")
        
        if i < len(tokens):
            time.sleep(2)
    
    print(f"\n{'='*50}")
    print("所有账号处理完成")

if __name__ == "__main__":
    main()

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
------------------------
更新日期：
【2025-09-01】修复无法自动做任务的问题
"""

import os
import sys
import json
import time
import random
import hashlib
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import binascii

# 默认需要跳过的任务TaskNo
SKIP_TASKS = {"T05", "T03", "T01"}

try:
    import jwt
    import httpx
except ImportError:
    print("错误：未安装必要依赖，请安装：pyjwt httpx[http2] pycryptodome")
    sys.exit(1)

BASE_URL = "https://sytgate.jslife.com.cn"
HEADERS = {
    "Host": "sytgate.jslife.com.cn",
    "Connection": "keep-alive",
    "applicationVersion": "1.0.1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) MicroMessenger/7.0.20.1781(0x6700143B)",
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Referer": "https://servicewechat.com/wx24b70f0ad2a9a89a/284/page-frame.html",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9"
}

LONGITUDE = None
LATITUDE = None

class DataReportGenerator:
    """数据上报生成器"""

    def __init__(self):
        # k04密钥
        self.secret_key = "GaT92Kf6cbDc1Pea9S720GJnL56A14x3R"

    def generate_nonce(self, timestamp=None):
        """生成nonce:7位随机数+13位时间戳"""
        if timestamp is None:
            timestamp = int(time.time() * 1000)

        random_7_digits = str(random.randint(1000000, 9999999))
        nonce = f"{random_7_digits}{timestamp}"

        return nonce, timestamp

    def generate_sign(self, data):
        """生成签名"""
        sorted_params = []
        for key in sorted(data.keys()):
            value = data[key]
            if value is not None:
                sorted_params.append(f"{key}={value}")

        sign_string = "&".join(sorted_params) + "&" + self.secret_key

        sign = hashlib.md5(sign_string.encode('utf-8')).hexdigest().upper()

        return sign

    def create_report_data(self, user_id, open_id, event_name="ShowGoToClaim", page_event_name="RentalPage", task_info=None, extra_props=None):
        """创建埋点上报数据"""
        timestamp = int(time.time() * 1000)
        nonce, _ = self.generate_nonce(timestamp)

        event_property = {"pageEventName": page_event_name}

        if extra_props and isinstance(extra_props, dict):
            event_property.update(extra_props)

        if event_name == "GoToFinishClick" and task_info:
            event_property.update({
                "TaskName": task_info.get("showTitle", ""),
                "TaskNo": task_info.get("taskNo", ""),
                "pageEventName": "PointsTaskPage",
                "referrer": "pages/my/my",
                "curPgUrl": "subPkg/tcb/index"
            })
        elif event_name in ("TaskStart", "TaskAction", "TaskProgress", "TaskFinish", "TaskReceive") and task_info:
            event_property.update({
                "TaskName": task_info.get("showTitle", ""),
                "TaskNo": task_info.get("taskNo", ""),
                "stage": event_name,
                "pageEventName": "PointsTaskPage",
            })
        elif event_name == "ShowGoToClaim":
            event_property.update({
                "referrer": "pages/search-stall/search-stall",
                "curPgUrl": "pages/search-stall/search-stall"
            })
        elif event_name == "GoToClaimClick":
            event_property.update({
                "referrer": "subPkg/tcb/index",
                "curPgUrl": "subPkg/tcb/index"
            })
        elif event_name == "ClaimClick":
            event_property.update({
                "referrer": "subPkg/tcb/index",
                "curPgUrl": "subPkg/tcb/index"
            })

        data = {
            "opSystem": "windows",
            "opSystemVersion": "Windows 10 x64",
            "phoneModel": "microsoft",
            "brand": "microsoft",
            "language": "zh_CN",
            "userAgent": "",
            "deviceId": "",
            "screenResolution": "415*800",
            "longitude": LONGITUDE,
            "latitude": LATITUDE,
            "serviceProviders": "",
            "netType": "unknown",
            "productName": "捷停车微信小程序",
            "productVersion": "4.0.6.26",
            "dataSourceType": "JTC_WX_MINI",
            "userId": user_id,
            "openId": open_id,
            "eventStartTime": timestamp,
            "MaterialId": "",
            "SourceId": "",
            "eventType": "activity",
            "eventName": event_name,
            "eventProperty": json.dumps(event_property, ensure_ascii=False),
            "signType": "MD5",
            "timestamp": timestamp,
            "nonce": nonce
        }

        sign = self.generate_sign(data)
        data["sign"] = sign

        return data

def send_data_report(user_id, open_id, event_name="ShowGoToClaim", task_info=None, extra_props=None):
    """埋点数据上报"""
    try:
        generator = DataReportGenerator()
        report_data = generator.create_report_data(user_id, open_id, event_name, "RentalPage", task_info, extra_props)

        headers = {
            "Host": "etgw.jparking.cn",
            "applicationVersion": "1.0.0",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf254061a) XWEB/16203",
            "xweb_xhr": "1",
            "Content-Type": "application/json",
            "uc_id": open_id,
            "Accept": "*/*",
            "sec-fetch-site": "cross-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "Referer": "https://servicewechat.com/wx24b70f0ad2a9a89a/281/page-frame.html",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "priority": "u=1, i"
        }

        with httpx.Client(http2=True, timeout=30, verify=False) as client:
            response = client.post(
                "https://etgw.jparking.cn/data-report-gateway/syt-data-report/receive",
                headers=headers,
                json=report_data
            )
            response.raise_for_status()
            # 不处理埋点返回值，只要成功发送即认为埋点触达
            # print(f"埋点上报成功：{event_name}")
            return True

    except Exception as e:
        print(f"埋点上报失败：{e}")
        return False

def check_response(response_data):
    """检查响应是否正常"""
    if response_data.get("code") != "0" and response_data.get("resultCode") != "0":
        error_msg = response_data.get("message", "未知错误")
        print(f"请求失败：{error_msg}")
        return False
    return True

def safe_get_reward(data, default=0):
    """从响应的data字段中提取数值奖励"""
    if data is None:
        return default

    if isinstance(data, (int, float)):
        try:
            return int(data)
        except Exception:
            return default

    if isinstance(data, str):
        try:
            return int(float(data))
        except Exception:
            return default

    if isinstance(data, dict):
        for key in ("amount", "value", "points", "integral", "data", "reward", "cnt", "count"):
            if key in data:
                return safe_get_reward(data.get(key), default)

    return default

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
    """发送HTTP2请求"""
    headers = HEADERS.copy()

    if "Content-Length" in headers:
        del headers["Content-Length"]

    try:
        with httpx.Client(http2=True, timeout=30, verify=False) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"请求失败：{e}")
        return None

def get_location_info():
    """获取经纬度坐标信息"""
    global LONGITUDE, LATITUDE

    try:
        with httpx.Client(http2=True, timeout=30, verify=False) as client:
            response = client.get("https://ipinfo.io/json")
            response.raise_for_status()
            data = response.json()

            loc = data.get("loc", "")
            if loc and "," in loc:
                lat_str, lon_str = loc.split(",")
                base_lat = float(lat_str.strip())
                base_lon = float(lon_str.strip())

                lon_random = random.randint(0, 9999999999999)
                LONGITUDE = base_lon + lon_random / 10**16

                lat_random = random.randint(0, 999999999999999)
                LATITUDE = base_lat + lat_random / 10**18

                print("经纬度坐标已补全")
                print(f"经度: {LONGITUDE}")
                print(f"维度: {LATITUDE}")
                return True
            else:
                print("无法解析经纬度信息，使用默认坐标")
                # 使用北京的默认坐标
                LONGITUDE = 116.4133836971231
                LATITUDE = 39.910924547299565
                return True

    except Exception as e:
        print(f"获取经纬度信息失败：{e}")
        print("使用默认坐标")
        # 使用北京的默认坐标
        LONGITUDE = 116.4133836971231
        LATITUDE = 39.910924547299565
        return True

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
        "osType":"ANDROID",
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
        "osType":"WINDOWS",
        "token": token
    }

    response_data = make_request(url, payload)
    if response_data and check_response(response_data):
        reward = safe_get_reward(response_data.get("data", 0))
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
        "osType":"ANDROID",
        "reqVersion": "V2.0"
    }

    response_data = make_request(url, payload)
    if response_data and check_response(response_data):
        return response_data.get("data", [])
    return []

def receive_task_reward(user_id, task_no, token, open_id, task_info=None):
    """领取任务奖励。接受一个可选的 task_info 字典以确保能获取任务标题。"""
    show_title = ""
    if isinstance(task_info, dict):
        show_title = task_info.get("showTitle", "")
    elif isinstance(task_info, str):
        show_title = task_info

    fake_task_info = {"taskNo": task_no, "showTitle": show_title}
    send_data_report(user_id, open_id, "GoToClaimClick", fake_task_info)
    time.sleep(0.2)

    send_data_report(user_id, open_id, "TaskReceive", fake_task_info, extra_props={"step":"receive_start"})
    time.sleep(0.2)

    send_data_report(user_id, open_id, "ClaimClick", fake_task_info)
    time.sleep(0.3)

    url = f"{BASE_URL}/base-gateway/integral/v2/task/receive"
    payload = {
        "userId": user_id,
        "taskNo": task_no,
        "reqSource": "WX_XCX_JTC",
        "platformType": "WX_XCX_JTC",
        "osType":"ANDROID"
    }

    response_data = make_request(url, payload)
    if response_data and check_response(response_data):
        return safe_get_reward(response_data.get("data", 0))
    return 0

def simulate_task_action(user_id, open_id, task_no):
    """模拟任务相关的操作"""
    send_data_report(user_id, open_id, "TaskStart", {"taskNo": task_no, "showTitle": ""}, extra_props={"step":"start"})
    time.sleep(0.2)
    if task_no == "T01":  # 去找优惠
        send_data_report(user_id, open_id, "PageView")
        time.sleep(1)
        send_data_report(user_id, open_id, "FindDiscountClick")
        time.sleep(1)
        send_data_report(user_id, open_id, "TaskAction", {"taskNo": task_no}, extra_props={"action":"find_discount"})
        time.sleep(0.5)
    elif task_no == "T46":  # 邀请好友一起找优惠
        send_data_report(user_id, open_id, "ShareClick")
        time.sleep(1)
        send_data_report(user_id, open_id, "InviteFriendClick")
        time.sleep(1)
        send_data_report(user_id, open_id, "TaskAction", {"taskNo": task_no}, extra_props={"action":"invite"})
        time.sleep(0.5)
    send_data_report(user_id, open_id, "TaskProgress", {"taskNo": task_no}, extra_props={"progress":"50%"})
    time.sleep(0.2)

def complete_task(user_id, task_no, token, open_id, task_info=None):
    """完成任务"""
    start_ts = time.time()
    simulate_task_action(user_id, open_id, task_no)

    # 对于T01，需要确保在浏览（模拟）阶段至少停留5秒【目前仍无法通过埋点验证，默认跳过这个任务】
    if task_no == "T01":
        elapsed = time.time() - start_ts
        min_wait = 5.0
        if elapsed < min_wait:
            to_sleep = min_wait - elapsed
            # 打印提示并睡眠补足
            print(f"任务{task_no}需浏览至少5秒，已浏览{elapsed:.2f}s，补足等待{to_sleep:.2f}s...")
            time.sleep(to_sleep)

    if task_info:
        send_data_report(user_id, open_id, "GoToFinishClick", task_info)
        time.sleep(0.5)

    fake_info = task_info or {"taskNo": task_no, "showTitle": ""}
    send_data_report(user_id, open_id, "TaskProgress", fake_info, extra_props={"progress":"near_finish"})
    time.sleep(0.3)

    url = f"{BASE_URL}/base-gateway/integral/v2/task/complete"
    payload = {
        "userId": user_id,
        "taskNo": task_no,
        "receiveTag": True,
        "reqSource": "WX_XCX_JTC",
        "platformType": "WX_XCX_JTC",
        "osType": "IOS",
        "token": token
    }

    response_data = make_request(url, payload)
    if response_data and check_response(response_data):
        time.sleep(0.5)
        send_data_report(user_id, open_id, "TaskFinish", fake_info, extra_props={"stage":"finish"})
        time.sleep(0.2)
        send_data_report(user_id, open_id, "ShowGoToClaim", fake_info)

        reward = safe_get_reward(response_data.get("data", 0))
        if reward > 0:
            print(f"直接获得任务奖励：{reward}个捷停币")

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
        print("JWT解析失败，跳过此账号，请检查是不是没有绑定手机号")
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
    task_info_map = {}

    for task_group in task_data:
        task_type = task_group.get("taskType", "")
        task_list = task_group.get("taskList", [])

        for task in task_list:
            task_no = task.get("taskNo")
            task_status = task.get("taskStatus")
            show_title = task.get("showTitle", "")

            task_info_map[task_no] = task

            if task_no in SKIP_TASKS:
                print(f"跳过任务：{show_title} ({task_no})")
                continue

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
            task_info = task_info_map.get(task_no)
            reward = receive_task_reward(user_id, task_no, token, open_id, task_info)
            if reward > 0:
                title = task_info.get("showTitle", show_title) if task_info else show_title
                print(f"成功领取{title}任务奖励{reward}个捷停币")
            time.sleep(1)
    
    if incomplete_tasks:
        print(f"开始完成{len(incomplete_tasks)}个未完成任务")
        completed_tasks = []
        
        for task_no, show_title in incomplete_tasks:
            task_info = task_info_map.get(task_no)
            print(f"尝试完成任务：{show_title} ({task_no})")
            success = complete_task(user_id, task_no, token, open_id, task_info)
            if success:
                print(f"成功完成任务：{show_title}")
                completed_tasks.append((task_no, show_title))
            else:
                print(f"未能完成任务：{show_title} ({task_no})")
            time.sleep(1)
        
        if completed_tasks:
            print("开始领取新完成任务的奖励")
            # 任务完成后需要等待一段时间，让服务器状态同步
            print("等待服务器状态同步...")
            time.sleep(5)

            # 重新查询任务状态，确认任务是否真的完成
            print("重新查询任务状态...")
            updated_task_data = get_task_list(user_id)
            if updated_task_data:
                updated_receivable_tasks = []
                for task_group in updated_task_data:
                    task_list = task_group.get("taskList", [])
                    for task in task_list:
                        task_no = task.get("taskNo")
                        task_status = task.get("taskStatus")
                        show_title = task.get("showTitle", "")
                        if task_status == "RECEIVE":
                            updated_receivable_tasks.append((task_no, show_title))

                print(f"更新后发现{len(updated_receivable_tasks)}个可领取任务")
                for task_no, show_title in updated_receivable_tasks:
                    if any(ct[0] == task_no for ct in completed_tasks):
                        print(f"尝试领取刚完成的任务：{show_title}")
                        task_info = task_info_map.get(task_no)
                        reward = receive_task_reward(user_id, task_no, token, open_id, task_info)
                        if reward > 0:
                            title = task_info.get("showTitle", show_title) if task_info else show_title
                            print(f"成功领取{title}任务奖励{reward}个捷停币")
                        time.sleep(3)
            else:
                # 如果重新查询失败，仍然尝试原来的方式
                for task_no, show_title in completed_tasks:
                    task_info = task_info_map.get(task_no)
                    reward = receive_task_reward(user_id, task_no, token, open_id, task_info)
                    if reward > 0:
                        title = task_info.get("showTitle", show_title) if task_info else show_title
                        print(f"成功领取{title}任务奖励{reward}个捷停币")
                    time.sleep(3)
    
    balance_info = get_balance(user_id, open_id)
    if balance_info:
        account_amt = balance_info.get("accountAmt", 0)
        deduct_amount = balance_info.get("deductAmount", 0)
        print(f"任务奖励领取完成，当前有{account_amt}个捷停币，最少可抵扣{deduct_amount}元")

def main():
    """主函数"""
    print("捷停车自动任务脚本启动")

    print("正在获取经纬度坐标...")
    if not get_location_info():
        print("获取经纬度坐标失败，脚本退出")
        sys.exit(1)

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

"""
脚本: 中通小程序自动签到
作者: 3iXi
创建日期: 2025-06-24
修改日期: 2025-06-27
更新内容：更换为账号密码登录，Token永不过期
----------------------
描述: 使用账号密码登录中通快递，自动签到获取积分；访问网页zto.com登录后在“个人中心”-“账户绑定”里设置密码。
环境变量：
        变量名：ztozm
        变量值：手机号&密码，多个账号用#分隔
签到奖励：积分，可兑东西
"""

import os
import time
import requests
from datetime import datetime, timedelta

def parse_account_credentials(credentials):
    """解析账号密码信息"""
    try:
        if '&' not in credentials:
            print("账号密码格式错误，应为：手机号&密码")
            return None
        
        username, password = credentials.split('&', 1)
        if not username or not password:
            print("账号或密码不能为空")
            return None
            
        return {
            "username": username.strip(),
            "password": password.strip()
        }
    except Exception as e:
        print(f"解析账号密码失败: {e}")
        return None

def get_timestamp():
    """获取当前13位时间戳"""
    return str(int(time.time() * 1000))

def get_date_range():
    """获取查询签到记录的日期范围"""
    today = datetime.now()
    start_date = (today - timedelta(days=3)).strftime("%Y-%m-%d 00:00:00")
    end_date = (today + timedelta(days=3)).strftime("%Y-%m-%d 23:59:59")
    return start_date, end_date

def get_today_date():
    """获取今天的日期"""
    return datetime.now().strftime("%Y-%m-%d")

def login_with_password(username, password):
    """使用账号密码登录获取Token"""
    url = "https://hdgateway.zto.com/auth_account_loginByPassword"
    
    headers = {
        "Host": "hdgateway.zto.com",
        "Connection": "keep-alive",
        "Content-Type": "application/json;charset=UTF-8",
        "x-clientCode": "pc",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://auth.zto.com",
        "Referer": "https://auth.zto.com/",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    
    payload = {
        "userName": username,
        "password": password,
        "isAgainBind": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        
        if data.get("status") == True:
            token = data["result"]["token"]
            print(f"账号 {username} 登录成功")
            return token
        else:
            print(f"账号 {username} 登录失败: {data.get('message', '未知错误')}")
            return None
    except Exception as e:
        print(f"账号 {username} 登录请求失败: {e}")
        return None

def check_today_sign_status(token):
    """检查今日是否签到"""
    url = "https://membergateway.zto.com/member/activity/queryRecentSign"
    
    start_date, end_date = get_date_range()
    
    headers = {
        "Host": "membergateway.zto.com",
        "Connection": "keep-alive",
        "x-version": "V8.93.2",
        "x-token": token,
        "x-clientCode": "wechatMiniZtoHelper",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) XWEB/13871",
        "Content-Type": "application/json",
        "x-sv-v": "0.22.0",
        "Accept": "*/*",
        "Referer": "https://servicewechat.com/wx7ddec43d9d27276a/553/page-frame.html",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    
    payload = {
        "startDate": start_date,
        "endDate": end_date
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        
        if data.get("status"):
            daily_list = data["result"]["dailyList"]
            today_date = get_today_date()
            
            for day_info in daily_list:
                if day_info["date"] == today_date:
                    return {
                        "is_signed": day_info["isSigned"],
                        "total_points": data["result"]["totalPoints"]
                    }
            return None
        else:
            print(f"查询签到状态失败: {data.get('message', '未知错误')}")
            return None
    except Exception as e:
        print(f"查询签到状态请求失败: {e}")
        return None

def sign_in(token):
    """开始签到"""
    url = "https://membergateway.zto.com/member/activity/signIn"
    
    headers = {
        "Host": "membergateway.zto.com",
        "Connection": "keep-alive",
        "x-version": "V8.93.2",
        "x-token": token,
        "x-clientCode": "wechatMiniZtoHelper",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) XWEB/13871",
        "Content-Type": "application/json",
        "x-sv-v": "0.22.0",
        "Accept": "*/*",
        "Referer": "https://servicewechat.com/wx7ddec43d9d27276a/553/page-frame.html",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    
    payload = {
        "signType": "TODAY_SIGN",
        "signDate": f"{get_today_date()} 00:00:00",
        "supplementaryScene": None
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        
        if data.get("status"):
            points_earned = data["result"]["pointsEarned"]
            print(f"签到成功，得到{points_earned}积分")
            return True
        else:
            print(f"签到失败: {data.get('message', '未知错误')}")
            return False
    except Exception as e:
        print(f"签到请求失败: {e}")
        return False

def check_and_claim_resign_card(token):
    """检查并领取补签卡（每月1次）"""
    url = "https://membergateway.zto.com/member/activity/getMyActivityProps"
    
    headers = {
        "Host": "membergateway.zto.com",
        "Connection": "keep-alive",
        "x-version": "V8.93.2",
        "x-token": token,
        "x-clientCode": "wechatMiniZtoHelper",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) XWEB/13871",
        "Content-Type": "application/json",
        "x-sv-v": "0.22.0",
        "Accept": "*/*",
        "Referer": "https://servicewechat.com/wx7ddec43d9d27276a/553/page-frame.html",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    
    payload = {"propsType": "RESIGN_CARD"}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        
        if data.get("status"):
            monthly_collection_status = data["result"]["monthlyCollectionStatus"]
            if monthly_collection_status == 1:
                # 领取补签卡，如果这个月领了的话就什么都不做
                claim_url = "https://membergateway.zto.com/member/activity/issueProps"
                claim_payload = {
                    "propsType": "RESIGN_CARD",
                    "taskType": "MONTHLY_COLLECTION"
                }
                
                claim_response = requests.post(claim_url, headers=headers, json=claim_payload, timeout=30)
                claim_data = claim_response.json()
                
                if claim_data.get("status"):
                    print("每月免费领取补签卡*1成功")
        
    except Exception as e:
        print(f"检查/领取补签卡失败: {e}")

def get_member_points(token):
    """获取积分"""
    url = "https://membergateway.zto.com/member/getMemberPoints"
    
    headers = {
        "Host": "membergateway.zto.com",
        "Connection": "keep-alive",
        "x-version": "V8.93.2",
        "x-token": token,
        "x-clientCode": "wechatMiniZtoHelper",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) XWEB/13871",
        "Content-Type": "application/json",
        "x-sv-v": "0.22.0",
        "Accept": "*/*",
        "Referer": "https://servicewechat.com/wx7ddec43d9d27276a/553/page-frame.html",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    
    payload = {}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        
        if data.get("success"):
            total_point = data["data"]["totalPoint"]
            over_due_point = data["data"]["overDuePoint"]
            over_due_message = data["data"]["overDueMessage"]
            
            if over_due_point:
                print(f"当前积分{total_point}，{over_due_message}")
            else:
                print(f"当前积分{total_point}")
        
    except Exception as e:
        print(f"获取积分信息失败: {e}")

def process_account(credentials):
    """处理单个账户的签到流程"""
    # 解析账号密码
    account_info = parse_account_credentials(credentials)
    if not account_info:
        print("解析账号密码失败，跳过此账户")
        return
    
    username = account_info["username"]
    password = account_info["password"]
    
    print(f"\n开始处理账户: {username}")
    
    # 使用账号密码登录获取Token
    token = login_with_password(username, password)
    if not token:
        print("登录失败，跳过此账户")
        return
    
    # 检查今天是否签到
    sign_status = check_today_sign_status(token)
    if not sign_status:
        print("无法获取签到状态，跳过此账户")
        return
    
    if sign_status["is_signed"]:
        print(f"今天已签到，当前积分{sign_status['total_points']}")
    else:
        print("今天未签到，开始签到...")
        sign_in(token)
    
    # 检查并领取补签卡
    check_and_claim_resign_card(token)
    
    # 获取积分信息
    get_member_points(token)

def main():
    """主函数"""
    print("中通快递自动签到脚本启动...")
    
    # 获取环境变量
    zto_credentials = os.getenv("ztozm")
    if not zto_credentials:
        print("未找到环境变量'ztozm'，请先设置")
        print("格式：手机号&密码，多个账号用#分隔")
        return
    
    # 分割多个账号密码
    credentials_list = zto_credentials.split("#")
    print(f"共找到{len(credentials_list)}个账号")
    
    # 处理每个账户
    for i, credentials in enumerate(credentials_list, 1):
        credentials = credentials.strip()
        if not credentials:
            continue
        
        print(f"\n{'='*30}")
        print(f"处理第{i}个账户")
        print(f"{'='*30}")
        
        process_account(credentials)
        
        # 为避免请求过于频繁，添加延时
        if i < len(credentials_list):
            time.sleep(2)
    
    print(f"\n{'='*30}")
    print("所有账户处理完成！")
    print(f"{'='*30}")

if __name__ == "__main__":
    main()

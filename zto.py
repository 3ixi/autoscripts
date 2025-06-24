"""
脚本: 中通小程序自动签到
作者: 3iXi
创建日期: 2025-06-24
----------------------
描述: 打开“中通快递”APP，开启抓包，登录，抓包域名https://yddapp.zto.com 请求头中的X-Token参数值。一定要注意，这里是用APP抓包，不是小程序。
环境变量：
        变量名：zto
        变量值：抓包的X-Token参数值
        多账号之间用#分隔
需要依赖：PyJWT
签到奖励：积分，可兑东西
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timedelta

def check_pyjwt():
    """检查PyJWT库是否已安装"""
    try:
        import jwt
        return True
    except ImportError:
        print("缺少PyJWT库，请使用以下命令安装：")
        print("pip install PyJWT")
        return False

def parse_jwt_token(token):
    """解析JWT令牌获取payload信息"""
    try:
        import jwt
        decoded = jwt.decode(token, options={"verify_signature": False})
        return decoded
    except Exception as e:
        print(f"你填写的Token不正确，请重新抓包: {e}")
        return None

def is_token_expired(exp_timestamp):
    """检查Token是否已过期"""
    current_time = int(time.time())
    return current_time >= exp_timestamp

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

def transfer_token(token):
    """将APP Token转换为小程序Token"""
    url = "https://yddapp.zto.com/transferTokenB2C"
    
    headers = {
        "Host": "yddapp.zto.com",
        "x-timestamp": get_timestamp(),
        "Accept": "*/*",
        "X-Ca-Version": "1",
        "X-Token": token,
        "Accept-Encoding": "gzip;q=1.0, compress;q=0.5",
        "x-iam-token": token,
        "clientsource": "ios",
        "User-Agent": "ztoExpressClient/6.12.12 (cn.zto.ztoExpress; build:614; iOS 18.3.0) Alamofire/4.9.1",
        "Accept-Language": "zh-Hans-CN;q=1.0, en-CN;q=0.9",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "mspappversion": "6.12.12"
    }
    
    payload = {"channel": "iosApp"}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        data = response.json()
        
        if data.get("statusCode") == 200:
            return data["result"]["cToken"]
        else:
            print(f"交换Token失败，原因：{data.get('message', '未知错误')}")
            return None
    except Exception as e:
        print(f"交换Token请求失败: {e}")
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

def process_account(token):
    """处理单个账户的签到流程"""
    # 解析JWT获取账户信息
    payload = parse_jwt_token(token)
    if not payload:
        print("解析JWT失败，请检查Token是否填写错误，跳过此账户")
        return
    
    mobile = payload.get("mobile", "未知")
    exp = payload.get("exp", 0)
    
    # 检查Token是否过期
    if is_token_expired(exp):
        print(f"手机号{mobile}的Token已过期，请更新")
        return
    
    print(f"\n开始处理账户: {mobile}")
    
    # 尝试更新Token
    new_token = transfer_token(token)
    if new_token:
        print("Token更新成功")
        active_token = new_token
    else:
        print("将尝试使用APP Token进行请求")
        active_token = token
    
    # 检查今天是否签到
    sign_status = check_today_sign_status(active_token)
    if not sign_status:
        print("无法获取签到状态，跳过此账户")
        return
    
    if sign_status["is_signed"]:
        print(f"今天已签到，当前积分{sign_status['total_points']}")
    else:
        print("今天未签到，开始签到...")
        sign_in(active_token)
    
    # 检查并领取补签卡
    check_and_claim_resign_card(active_token)
    
    # 获取积分信息
    get_member_points(active_token)

def main():
    """主函数"""
    print("中通快递自动签到脚本启动...")
    
    # 检查PyJWT库
    if not check_pyjwt():
        return
    
    # 获取环境变量
    zto_tokens = os.getenv("zto")
    if not zto_tokens:
        print("未找到环境变量'zto'，请先设置")
        return
    
    # 分割多个Token
    tokens = zto_tokens.split("#")
    print(f"共找到{len(tokens)}个Token")
    
    # 处理每个账户
    for i, token in enumerate(tokens, 1):
        token = token.strip()
        if not token:
            continue
        
        print(f"\n{'='*30}")
        print(f"处理第{i}个账户")
        print(f"{'='*30}")
        
        process_account(token)
        
        # 为避免请求过于频繁，添加延时
        if i < len(tokens):
            time.sleep(2)
    
    print(f"\n{'='*30}")
    print("所有账户处理完成！")
    print(f"{'='*30}")

if __name__ == "__main__":
    main()
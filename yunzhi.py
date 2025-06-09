import os
import json
import time
import datetime
import httpx
import random

"""
脚本: 云知积分有礼小程序自动任务
作者: 3iXi
创建日期: 2025-06-19
描述: 先开启抓包，再打开“云知积分有礼”小程序，抓域名https://pointsmall.hezimao.top/api/getOpenid 响应数据中的openid
环境变量：
        变量名：yunzhi
        变量格式：openid
        多账号之间用#分隔：openid#openid2
需要依赖：httpx[http2]
任务奖励：积分
补充说明：当openid数量大于2时会触发自动助力任务，会自动将所有添加的openid互相助力（实验功能，可能逻辑不完善）
"""

def get_content_length(payload):
    """计算请求体的字节长度"""
    json_str = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    return str(len(json_str.encode('utf-8')))

def get_headers(payload=None):
    """获取统一请求头"""
    headers = {
        'host': 'pointsmall.hezimao.top',
        'user-agent': 'MicroMessenger/7.0.20.1781(0x6700143B)',
        'content-type': 'application/json',
        'accept': '*/*',
        'referer': 'https://servicewechat.com/wxaeaf440ebf0dada9/4/page-frame.html',
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'zh-CN,zh;q=0.9'
    }
    
    if payload:
        headers['content-length'] = get_content_length(payload)
    
    return headers

def get_user_info(client, userid):
    """获取用户信息"""
    url = "https://pointsmall.hezimao.top/api/userInfo"
    payload = {"openid": userid}
    headers = get_headers(payload)
    
    response = client.post(url, json=payload, headers=headers)
    return response.json()

def do_checkin(client, userid, date):
    """执行签到任务"""
    # 签到
    url = "https://pointsmall.hezimao.top/api/addPoints"
    payload = {
        "totalPoints": 100,
        "userID": userid,
        "type": "Checkintask",
        "date": date,
        "show": 1,
        "signature": "1ad2758120af3f3d2d18526ce5164b791beea1a75035a43d201d260e03701a0a"
    }
    headers = get_headers(payload)
    response = client.post(url, json=payload, headers=headers)
    result = response.json()
    points = result.get("points", "0")
    print(f"签到成功，获得积分{points}")
    
    # 添加任务记录
    url = "https://pointsmall.hezimao.top/api/addPointsRecord"
    payload = {
        "Id": 1,
        "userID": userid,
        "date": date,
        "maxCompletions": 1
    }
    headers = get_headers(payload)
    client.post(url, json=payload, headers=headers)
    
    # 添加积分历史记录
    now = datetime.datetime.now()
    formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
    timestamp = int(time.time() * 1000)
    
    url = "https://pointsmall.hezimao.top/api/integralHistory"
    payload = {
        "userID": userid,
        "taskID": 1,
        "totalPoints": 100,
        "formattedTime": formatted_time,
        "timestamp": timestamp,
        "type": "add"
    }
    headers = get_headers(payload)
    client.post(url, json=payload, headers=headers)

def do_task(client, userid, task_id, points, signature, task_name):
    """执行任务"""
    # 添加积分
    url = "https://pointsmall.hezimao.top/api/addPoints"
    payload = {
        "totalPoints": points,
        "userID": userid,
        "type": task_id,
        "signature": signature
    }
    headers = get_headers(payload)
    response = client.post(url, json=payload, headers=headers)
    result = response.json()
    message = result.get("message", "未知结果")
    print(f"{task_name}完成，{message}")
    
    # 添加任务记录
    url = "https://pointsmall.hezimao.top/api/addPointsRecord"
    payload = {
        "Id": task_id,
        "userID": userid,
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "maxCompletions": 1
    }
    headers = get_headers(payload)
    client.post(url, json=payload, headers=headers)
    
    # 添加积分历史记录
    now = datetime.datetime.now()
    formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
    timestamp = int(time.time() * 1000)
    
    url = "https://pointsmall.hezimao.top/api/integralHistory"
    payload = {
        "userID": userid,
        "taskID": task_id,
        "totalPoints": points,
        "formattedTime": formatted_time,
        "timestamp": timestamp,
        "type": "add"
    }
    headers = get_headers(payload)
    client.post(url, json=payload, headers=headers)

def get_points(client, userid):
    """获取用户积分余额"""
    url = f"https://pointsmall.hezimao.top/api/getUserSigninInfo?openid={userid}"
    headers = get_headers()
    
    response = client.get(url, headers=headers)
    return response.json()

def do_help_friend(client, from_userid, to_userid, date):
    """执行助力任务"""
    # 添加积分
    url = "https://pointsmall.hezimao.top/api/addPoints"
    payload = {
        "totalPoints": 200,
        "userID": to_userid,
        "type": "type",
        "date": date,
        "show": "show",
        "Id": "3",
        "signature": "f7e3f3ec375409737dc64c9b88d8134e4744875af36456ae63178827769edbda"
    }
    headers = get_headers(payload)
    response = client.post(url, json=payload, headers=headers)
    result = response.json()
    points = result.get("totalPoints", "200")
    print(f"助力成功，获得{points}")
    
    # 添加任务记录
    url = "https://pointsmall.hezimao.top/api/addPointsRecord"
    payload = {
        "Id": "3",
        "userID": to_userid,
        "date": date,
        "maxCompletions": "5"
    }
    headers = get_headers(payload)
    client.post(url, json=payload, headers=headers)
    
    # 添加积分历史记录
    now = datetime.datetime.now()
    formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
    timestamp = int(time.time() * 1000)
    
    url = "https://pointsmall.hezimao.top/api/integralHistory"
    payload = {
        "userID": to_userid,
        "totalPoints": "200",
        "formattedTime": formatted_time,
        "timestamp": timestamp,
        "type": "add"
    }
    headers = get_headers(payload)
    client.post(url, json=payload, headers=headers)

def main():
    # 获取环境变量中的用户ID列表
    userids = os.environ.get('yunzhi', '')
    if not userids:
        print("未找到yunzhi环境变量，请设置后重试")
        return
    
    userids = userids.split('#')
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 为每个用户执行任务
    for userid in userids:
        userid = userid.strip()
        if not userid:
            continue
            
        print(f"开始处理用户: {userid}")
        
        # 使用HTTP2协议
        with httpx.Client(http2=True) as client:
            # 获取用户信息
            user_info = get_user_info(client, userid)
            nickname = user_info.get('nickName', '未知用户')
            # print(f"用户昵称: {nickname}")
            
            # 执行签到
            do_checkin(client, userid, today)
            
            # 执行任务1：逛一逛读书笔记
            do_task(client, userid, 4, 100, "1ad2758120af3f3d2d18526ce5164b791beea1a75035a43d201d260e03701a0a", "逛一逛读书笔记")
            
            # 执行任务2：逛一逛历史题库
            do_task(client, userid, 7, 100, "1ad2758120af3f3d2d18526ce5164b791beea1a75035a43d201d260e03701a0a", "逛一逛历史题库")
            
            # 执行任务3：逛一逛图集
            do_task(client, userid, 6, 100, "1ad2758120af3f3d2d18526ce5164b791beea1a75035a43d201d260e03701a0a", "逛一逛图集")
            
            # 执行任务4：逛一逛笔友星球
            do_task(client, userid, 8, 50, "69e97be010159d2aa337ffa38cf5ea4e01fc63b2a7f0d934ea24d1740f0d16ff", "逛一逛笔友星球")
            
            # 执行任务5：逛一逛答题挑战
            do_task(client, userid, 5, 100, "1ad2758120af3f3d2d18526ce5164b791beea1a75035a43d201d260e03701a0a", "逛一逛答题挑战")
            
            # 获取积分余额
            points_info = get_points(client, userid)
            if points_info and len(points_info) > 0:
                points = points_info[0].get('points', '0')
                print(f"{nickname}当前积分余额：{points}")
            else:
                print(f"{nickname}获取积分余额失败")
        
        print("=" * 30)
    
    # 如果有多个账号，执行助力任务
    if len(userids) > 1:
        print("开始执行助力任务...")
        
        # 为每个用户执行助力任务
        for i, userid in enumerate(userids):
            userid = userid.strip()
            if not userid:
                continue
                
            # 获取其他用户ID列表（不包括自己）
            other_userids = [uid.strip() for uid in userids if uid.strip() and uid.strip() != userid]
            
            # 如果没有其他用户，跳过
            if not other_userids:
                continue
                
            print(f"用户 {userid} 开始助力其他用户")
            
            with httpx.Client(http2=True) as client:
                # 为每个其他用户提供助力（最多5次，有多少个助力多少个）
                help_count = 0
                max_help = min(5, len(other_userids))
                
                # 随机打乱用户列表顺序
                random.shuffle(other_userids)
                
                # 只助力实际可用的用户数量
                for i in range(max_help):
                    to_userid = other_userids[i]
                    
                    # 执行助力任务
                    do_help_friend(client, userid, to_userid, today)
                    
                    help_count += 1
                    
                    # 添加短暂延迟，避免请求过快
                    time.sleep(1)
                
                print(f"用户 {userid} 完成助力任务，共助力{help_count}次")
            
            print("=" * 30)

if __name__ == "__main__":
    main() 
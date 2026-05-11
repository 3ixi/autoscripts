#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本: 海底捞小程序自动签到
作者: 3iXi
创建日期: 2025-05-15
描述: 先开启抓包，再打开“海底捞”小程序，抓域名https://superapp-public.kiwa-tech.com/api/gateway/login/center/login/wechatLogin 请求体(payload)中的openId和uid
环境变量：变量名：hdl变量格式：openId&uid多账号之间用#分隔：openId1&uid1#openId2&uid2
需要依赖：httpx[http2]
签到奖励：碎片（用于抽奖[暂未开放]、兑换菜品）、成长值、菜品券
"""

import os


try:
    from SendNotify import capture_output
except Exception as exc:
    print(f"[警告] 通知模块 SendNotify.py 导入失败：{exc}，将跳过通知推送。")

    def capture_output(title: str = "脚本运行结果"):
        def decorator(func):
            return func

        return decorator


import httpx


@capture_output("海底捞自动签到运行结果")
def main():
    hdl_env = os.getenv('hdl', '')
    if not hdl_env:
        print('未找到hdl环境变量')
        return
    
    accounts = hdl_env.split('#')
    for idx, account in enumerate(accounts, start=1):
        try:
            open_id, uid = account.split('&')
            payload_login = {
                "type": 1,
                "country": "CN",
                "codeType": 1,
                "business": "登录",
                "terminal": "会员小程序",
                "openId": open_id,
                "uid": uid
            }
            headers_login = {
                "host": "superapp-public.kiwa-tech.com",
                "platformname": "wechat",
                "user-agent": "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf254032b) XWEB/13655",
                "content-type": "application/json",
                "appname": "HDLMember",
                "appid": "15",
                "appversion": "3.257.0",
                "accept": "*/*",
                "referer": "https://servicewechat.com/wx1ddeb67115f30d1a/236/page-frame.html",
                "accept-encoding": "gzip, deflate, br",
                "accept-language": "zh-CN,zh;q=0.9"
            }
            
            with httpx.Client(http2=True) as client:
                response_login = client.post("https://superapp-public.kiwa-tech.com/api/gateway/login/center/login/wechatLogin", json=payload_login, headers=headers_login)
                response_login.raise_for_status()
                data_login = response_login.json()
                
                if data_login.get('success'):
                    token = data_login['data']['token']
                    nick_name = data_login['data']['nickName']
                    print(f"{nick_name} 获取Token成功")
                    
                    # 签到请求
                    payload_signin = {"signinSource": "MiniApp"}
                    headers_signin = {
                        "host": "superapp-public.kiwa-tech.com",
                        "deviceid": "null",
                        "accept": "application/json, text/plain, */*",
                        "content-type": "application/json",
                        "user-agent": "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf254032b) XWEB/13655",
                        "reqtype": "APPH5",
                        "_haidilao_app_token": token,
                        "origin": "https://superapp-public.kiwa-tech.com",
                        "referer": "https://superapp-public.kiwa-tech.com/app-sign-in/?SignInToken=" + token + "&source=MiniApp",
                        "accept-encoding": "gzip, deflate, br",
                        "accept-language": "zh-CN,zh;q=0.9"
                    }
                    
                    response_signin = client.post("https://superapp-public.kiwa-tech.com/activity/wxapp/signin/signin", json=payload_signin, headers=headers_signin)
                    response_signin.raise_for_status()
                    data_signin = response_signin.json()
                    
                    if data_signin.get('success'):
                        signin_list = data_signin.get('data', {}).get('signinQueryDetailList', [])
                        if len(signin_list) >= 2:
                            today = signin_list[0]
                            tomorrow = signin_list[1]
                            print(f"{nick_name} 签到成功，今日签到奖励：")
                            if 'fragment' in today: print(f"碎片{today['fragment']}")
                            if 'growthSeries' in today: print(f"成长值{today['growthSeries']}")
                            if 'dishes' in today: print(f"菜品{today['dishes']}")
                            print("明日签到奖励:")
                            if 'fragment' in tomorrow: print(f"碎片{tomorrow['fragment']}")
                            if 'growthSeries' in tomorrow: print(f"成长值{tomorrow['growthSeries']}")
                            if 'dishes' in tomorrow: print(f"菜品{tomorrow['dishes']}")
                    else:
                        print(f"{nick_name} 签到失败，原因：{data_signin.get('msg')}")
                    
                    # 获取碎片余额
                    response_fragment = client.post("https://superapp-public.kiwa-tech.com/activity/wxapp/signin/queryFragment", headers=headers_signin)
                    response_fragment.raise_for_status()
                    data_fragment = response_fragment.json()
                    if data_fragment.get('success'):
                        total = data_fragment['data']['total']
                        expire_date = data_fragment['data']['expireDate']
                        
                        # 查询账号详情
                        payload_member = {"type": 1}
                        response_member = client.post("https://superapp-public.kiwa-tech.com/activity/wxapp/applet/queryMemberCacheInfo", json=payload_member, headers=headers_signin)
                        response_member.raise_for_status()
                        data_member = response_member.json()
                        if data_member.get('success'):
                            coin_num = data_member['data']['coinNum']
                            member_age = data_member['data']['memberAge']
                            growth_value = data_member['data']['growthValue']
                            print(f"{nick_name} 背包：")
                            print(f"碎片：{total}（{expire_date}过期）")
                            print(f"捞币：{coin_num}")
                            print(f"捞龄：{member_age}年")
                            print(f"成长值：{growth_value}")
                            print(f"======账号 {nick_name} 执行完成======\n")
                else:
                    print(f"账号{idx} 获取背包数据失败，原因：{data_login.get('msg')}")
        except Exception as e:
            print(f"账号{idx} 处理错误：{str(e)}")

if __name__ == "__main__":
    main() 

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
伊的家自动任务脚本
脚本作者: 3iXi
创建日期: 2025-09-16
需要依赖：httpx[http2]
抓包描述: 开启抓包，打开小程序“伊的家”，进去后抓包域名https://cim-api.yidejia.com/mall/api/user/login-by-wxa/v2 ，复制返回数据中的app_token字段值作为环境变量值（是app_token，不是new_token）
环境变量：
        变量名：ydj
        变量值：app_token的值（是app_token，不是new_token）
        多账号之间用#分隔：app_token1#app_token2
脚本奖励：伊币、消费积分
"""

import os
import sys
import json
import asyncio
from typing import List, Dict, Any, Optional

try:
    import httpx
except ImportError:
    print("请先安装依赖httpx[http2]")
    sys.exit(1)


class YiDeJiaClient:

    def __init__(self, token: str):
        self.base_url = "https://cim-api.yidejia.com"
        self.token = token
        self.headers = {
            "host": "cim-api.yidejia.com",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541022) XWEB/16467",
            "xweb_xhr": "1",
            "content-type": "application/json",
            "token": token,
            "version": "5.3.8",
            "platform": "wxa",
            "accept": "*/*",
            "sec-fetch-site": "cross-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://servicewechat.com/wx5d2eb35c8cf1c873/1110/page-frame.html",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "zh-CN,zh;q=0.9",
            "priority": "u=1, i"
        }
    
    async def _request(self, method: str, endpoint: str, payload: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        headers = self.headers.copy()
        
        async with httpx.AsyncClient(http2=True) as client:
            if method.upper() == "POST":
                if payload:
                    json_data = json.dumps(payload, separators=(',', ':'))
                    headers["content-length"] = str(len(json_data.encode('utf-8')))
                    response = await client.post(url, headers=headers, content=json_data)
                else:
                    headers["content-length"] = "0"
                    response = await client.post(url, headers=headers)
            else:
                response = await client.get(url, headers=headers)
            
            return response.json()
    
    def _check_response(self, response: Dict[str, Any]) -> bool:
        if response.get("code") != 0:
            print(f"请求失败: {response.get('message', '未知错误')}")
            return False
        return True
    
    async def sign_in(self) -> bool:
        print("开始签到...")
        payload = {"source": "小程序签到"}
        response = await self._request("POST", "/community/user/sign", payload)
        
        if self._check_response(response):
            date = response["data"]["date"]
            print(f"{date}签到成功")
            return True
        return False
    
    async def get_missions(self) -> List[str]:
        print("获取任务列表...")
        response = await self._request("GET", "/community/mission")
        
        if not self._check_response(response):
            return []
        
        # 需要排除的任务（这些任务只能在APP完成，这里提交了也领不到奖励）
        excluded_actions = {
            "daily_ai_join",
            "daily_comment_debate", 
            "daily_manor_water",
            "daily_treehole_explore"
        }
        
        incomplete_actions = []
        data = response["data"]
        
        for mission in data.get("daily", []):
            if not mission.get("complete", True):
                action = mission["action"]
                if action not in excluded_actions:
                    incomplete_actions.append(action)
                else:
                    print(f"跳过排除的任务:{action}")
        
        for mission in data.get("stage", []):
            if not mission.get("complete", True):
                action = mission["action"]
                if action not in excluded_actions:
                    incomplete_actions.append(action)
                else:
                    print(f"跳过排除的任务:{action}")
        
        print(f"发现{len(incomplete_actions)}个未完成任务")
        return incomplete_actions
    
    async def complete_mission(self, action: str) -> bool:
        print(f"完成任务: {action}")
        payload = {"action": action}
        response = await self._request("POST", "/community/mission/complete", payload)
        
        if self._check_response(response):
            return await self.claim_reward()
        return False
    
    async def claim_reward(self) -> bool:
        response = await self._request("GET", "/community/mission/user-score")
        
        if self._check_response(response):
            data = response["data"]
            score = data.get("score", "0")
            coin = data.get("coin", "0")
            experience = data.get("experience", "0")
            missions = data.get("mission", [])
            mission_text = "、".join(missions) if missions else "未知任务"
            
            print(f"完成任务{mission_text}成功，获得{score}消费积分、{coin}伊币、{experience}任务成长值")
            return True
        return False
    
    async def get_score_info(self) -> Optional[float]:
        response = await self._request("GET", "/mall/api/v1/user/score/info")
        
        if self._check_response(response):
            return response["data"]["can_use_score"]
        return None
    
    async def get_user_info(self) -> Optional[int]:
        response = await self._request("GET", "/user/center/mine")
        
        if self._check_response(response):
            return response["data"]["ycoin"]
        return None
    
    async def run_all_tasks(self):
        print(f"开始执行账号任务，Token: {self.token[:20]}...")
        
        # 1. 签到
        await self.sign_in()
        
        # 2. 获取并完成任务
        incomplete_actions = await self.get_missions()
        for action in incomplete_actions:
            await self.complete_mission(action)
            await asyncio.sleep(1)
        
        # 3. 获取最终状态
        score = await self.get_score_info()
        ycoin = await self.get_user_info()
        
        if score is not None and ycoin is not None:
            print(f"任务完成，当前可用购物积分{score}、伊币{ycoin}")
        
        print("-" * 50)


async def main():
    ydj_tokens = os.getenv("ydj")
    if not ydj_tokens:
        print("错误: 未找到环境变量'ydj'")
        return
    
    tokens = [token.strip() for token in ydj_tokens.split("#") if token.strip()]
    if not tokens:
        print("错误: 环境变量'ydj'为空或格式不正确")
        return
    
    print(f"找到{len(tokens)}个账号token")
    
    for i, token in enumerate(tokens, 1):
        print(f"\n{'='*20} 账号{i}{'='*20}")
        client = YiDeJiaClient(token)
        try:
            await client.run_all_tasks()
        except Exception as e:
            print(f"账号{i}执行失败: {str(e)}")
        
        # 账号间添加延迟
        if i < len(tokens):
            await asyncio.sleep(2)
    
    print("\n所有账号任务执行完成！")


if __name__ == "__main__":
    asyncio.run(main())
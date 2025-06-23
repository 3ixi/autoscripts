import os
import json
import asyncio
import httpx
from typing import List, Dict, Any, Optional

"""
脚本: 文明积分平台小程序自动任务
作者: 3iXi
创建日期: 2025-06-23
----------------------
描述: 打开并登录“文明积分平台”小程序，开启抓包，抓包域名https://wlt.xysyhkj.com/funsion-api/ 任意请求头中的ixyappauthorization的值，只复制Bearer后的字符串(ey开头的)。
环境变量：
        变量名：wmjf
        多账号之间用#分隔
需要依赖：httpx[http2] 版本0.25.0以上
签到奖励：积分仅限在江西省新余市内使用。
每天可得物质积分200+，可在“余快停”、“渝铃汇”小程序用积分抵扣停车费、团购优惠，100积分=1元。
"""

class WMJFClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://wlt.xysyhkj.com"
        self.headers = {
            "host": "wlt.xysyhkj.com",
            "user-agent": "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) XWEB/13871",
            "ixyappauthorization": f"Bearer {token}",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "zh-CN,zh;q=0.9"
        }
        
    async def make_request(self, method: str, endpoint: str, payload: Optional[Dict] = None) -> Optional[Dict]:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        headers = self.headers.copy()
        
        async with httpx.AsyncClient(http2=True) as client:
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers)
                elif method.upper() == "POST":
                    if payload:
                        json_data = json.dumps(payload, separators=(',', ':'))
                        headers["Content-Length"] = str(len(json_data.encode('utf-8')))
                        headers["Content-Type"] = "application/json"
                        response = await client.post(url, headers=headers, json=payload)
                    else:
                        response = await client.post(url, headers=headers)
                else:
                    print(f"不支持的HTTP方法: {method}")
                    return None
                
                result = response.json()
                
                if result.get("code") != 200:
                    msg = result.get("message", result.get("msg", ""))
                    print(f"请求失败: {msg}")
                    return None
                    
                return result
                
            except Exception as e:
                print(f"请求异常: {str(e)}")
                return None
    
    async def check_token_validity(self) -> Optional[str]:
        """检查Token有效性并获取用户昵称"""
        result = await self.make_request("GET", "/funsion-api/userauth/app/user")
        if result and result.get("code") == 200:
            nickname = result.get("data", {}).get("user", {}).get("memberNickName", "")
            return nickname
        else:
            msg = result.get("message", result.get("msg", "")) if result else ""
            print(f"Token已过期: {msg}")
            return None
    
    async def get_balance_info(self) -> Optional[Dict]:
        """获取积分余额信息"""
        result = await self.make_request("GET", "/funsion-api/integral/applet/wallet/info")
        if result and result.get("code") == 200:
            data = result.get("data", {})
            return {
                "moralPoint": data.get("moralPoint", 0),
                "balancePoint": data.get("balancePoint", 0)
            }
        return None
    
    async def get_attendance_activity(self) -> Optional[str]:
        """获取签到活动ID"""
        payload = {"activeTypeKey": "active_attendance"}
        result = await self.make_request("POST", "/funsion-api/marketing/applet/active/lottery-attendance", payload)
        if result and result.get("code") == 200:
            return result.get("data", {}).get("activeCode")
        return None
    
    async def do_attendance(self, active_code: str) -> Optional[str]:
        """执行签到"""
        payload = {"activeCode": active_code}
        result = await self.make_request("POST", "/funsion-api/marketing/applet/active/save-attendance", payload)
        if result and result.get("code") == 200:
            return result.get("data", {}).get("prizeName", "")
        return None
    
    async def get_lottery_activity(self) -> Optional[str]:
        """获取抽奖活动ID"""
        payload = {"activeTypeKey": "active_lottery"}
        result = await self.make_request("POST", "/funsion-api/marketing/applet/active/lottery-attendance", payload)
        if result and result.get("code") == 200:
            return result.get("data", {}).get("activeCode")
        return None
    
    async def get_lottery_count(self, active_code: str) -> int:
        """获取剩余抽奖次数"""
        result = await self.make_request("GET", f"/funsion-api/marketing/applet/active/user/participate-num/{active_code}")
        if result and result.get("code") == 200:
            return result.get("data", {}).get("activeNum", 0)
        return 0
    
    async def do_lottery(self, active_code: str) -> Optional[str]:
        """执行抽奖"""
        payload = {"activeCode": active_code}
        result = await self.make_request("POST", "/funsion-api/marketing/applet/active/save-lottery", payload)
        if result and result.get("code") == 200:
            return result.get("data", {}).get("prizeName", "")
        return None
    
    async def get_quiz_activities(self) -> List[Dict]:
        """获取可参与的答题活动"""
        payload = {"activeTypeKey": "active_quiz"}
        result = await self.make_request("POST", "/funsion-api/marketing/applet/question/list", payload)
        if result and result.get("code") == 200:
            activities = []
            for activity in result.get("data", []):
                if activity.get("activeNum") == 1:
                    activities.append({
                        "activeCode": activity.get("activeCode"),
                        "activeName": activity.get("activeName")
                    })
            return activities
        return []
    
    async def get_quiz_questions(self, active_code: str) -> int:
        """获取答题活动的题目数量"""
        result = await self.make_request("GET", f"/funsion-api/marketing/applet/question/quiz-question/{active_code}")
        if result and result.get("code") == 200:
            questions = result.get("data", {}).get("questionDTOList", [])
            return len(questions)
        return 0
    
    async def submit_quiz(self, active_code: str, question_count: int) -> Optional[str]:
        """提交答题"""
        payload = {"activeCode": active_code, "userScore": question_count}
        result = await self.make_request("POST", "/funsion-api/marketing/applet/question/save-quiz", payload)
        if result and result.get("code") == 200:
            return result.get("data", {}).get("prizeName", "")
        return None


async def process_account(token: str):
    """处理单个账号"""
    client = WMJFClient(token)
    
    # 1. 检查Token有效性
    nickname = await client.check_token_validity()
    if not nickname:
        return
    
    # 2. 获取初始积分信息
    balance_info = await client.get_balance_info()
    if not balance_info:
        print("获取积分信息失败")
        return
    
    print(f"账号{nickname}Token检查通过，品德积分{balance_info['moralPoint']}/物质积分{balance_info['balancePoint']}")
    
    # 3. 签到
    attendance_code = await client.get_attendance_activity()
    if attendance_code:
        prize_name = await client.do_attendance(attendance_code)
        if prize_name:
            print(f"签到成功，{prize_name}")
        else:
            print("签到失败")
    else:
        print("获取签到活动失败")
    
    # 4. 抽奖
    lottery_code = await client.get_lottery_activity()
    if lottery_code:
        lottery_count = await client.get_lottery_count(lottery_code)
        print(f"当前剩余{lottery_count}次抽奖次数")
        
        for i in range(lottery_count):
            prize_name = await client.do_lottery(lottery_code)
            if prize_name:
                print(f"抽奖成功，获得{prize_name}")
            else:
                print(f"第{i+1}次抽奖失败")
    else:
        print("获取抽奖活动失败")
    
    # 5. 答题
    quiz_activities = await client.get_quiz_activities()
    if quiz_activities:
        activity_names = [activity["activeName"] for activity in quiz_activities]
        print(f"今日可参与答题活动有{len(quiz_activities)}个：{'、'.join(activity_names)}")
        
        for activity in quiz_activities:
            active_code = activity["activeCode"]
            active_name = activity["activeName"]
            
            question_count = await client.get_quiz_questions(active_code)
            if question_count > 0:
                prize_name = await client.submit_quiz(active_code, question_count)
                if prize_name:
                    print(f'答题"{active_name}"完成，获得{prize_name}')
                else:
                    print(f'答题"{active_name}"提交失败')
            else:
                print(f'获取答题"{active_name}"题目失败')
    else:
        print("今日无可参与的答题活动")
    
    # 6. 获取最终积分信息
    final_balance = await client.get_balance_info()
    if final_balance:
        print(f"今日任务完成，当前品德积分{final_balance['moralPoint']}/物质积分{final_balance['balancePoint']}")
    else:
        print("获取最终积分信息失败")


async def main():
    """主函数"""
    # 获取环境变量
    wmjf_tokens = os.getenv("wmjf")
    if not wmjf_tokens:
        print("未找到环境变量wmjf")
        return
    
    # 分割多个Token
    tokens = [token.strip() for token in wmjf_tokens.split("#") if token.strip()]
    if not tokens:
        print("环境变量wmjf中没有有效的Token")
        return
    
    print(f"共找到{len(tokens)}个账号Token")
    
    # 依次处理每个账号
    for i, token in enumerate(tokens, 1):
        print(f"\n=== 处理第{i}个账号 ===")
        await process_account(token)
        print(f"=== 第{i}个账号处理完成 ===")


if __name__ == "__main__":
    asyncio.run(main())

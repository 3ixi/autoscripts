"""
脚本: iKuuu爱坤机场签到脚本
作者: 3iXi
创建时间: 2025-03-12
版本: 1.0.6
需要依赖：beautifulsoup4
描述:打开网站https://ikuuu.org 注册账号，环境变量填写邮箱和密码（密码不要带&和#符号）
环境变量：
        变量名：ikuuu
        变量值：email&passwd
        多账号之间用#分隔：email&passwd#email2&passwd2#email3&passwd3
签到奖励：VPN流量
----------------------
更新记录: 
【2025-09-02】修复无法获取剩余流量的问题
【2025-07-18】修复无法登录的问题
【2025-05-25】增加剩余流量获取
"""

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("错误：未检测到需要的依赖，请安装依赖：beautifulsoup4")
    exit(1)

import requests
import json
import os
import yaml
import base64

def get_accounts_from_env():
    accounts_str = os.getenv('ikuuu', '')
    if not accounts_str:
        raise ValueError("未找到环境变量 'ikuuu'")
    
    accounts = []
    account_pairs = accounts_str.split('#')
    for pair in account_pairs:
        if '&' in pair:
            email, passwd = pair.split('&', 1)
            accounts.append({'email': email.strip(), 'passwd': passwd.strip()})
    
    print(f"本轮获取到 {len(accounts)} 个账号")
    return accounts

DOMAINS = ['ikuuu.de', 'ikuuu.one', 'ikuuu.pw', 'ikuuu.org']

header = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'x-requested-with': 'XMLHttpRequest',
    'referer': '',
    'origin': ''
}

def get_available_domain():
    for domain in DOMAINS:
        try:
            test_url = f'https://{domain}'
            response = requests.get(test_url, headers={'User-Agent': header['user-agent']}, timeout=5)
            if response.status_code == 200:
                print(f'检测到域名 {domain} 可用')
                return domain
        except Exception as e:
            print(f'域名 {domain} 不可用: {e}')
            continue
    raise Exception('所有域名都不可用，请检查网络连接')

def check_in(email, passwd):
    data = {
        'email': email,
        'passwd': passwd
    }

    try:
        domain = get_available_domain()
        login_url = f'https://{domain}/auth/login'
        check_url = f'https://{domain}/user/checkin'
        user_url = f'https://{domain}/user'
        
        current_header = header.copy()
        current_header['origin'] = f'https://{domain}'
        current_header['referer'] = f'https://{domain}/auth/login'
        
        print(f'[{email}] 使用域名 {domain} 进行登录...')
        
        session = requests.session()
        
        response = session.post(
            url=login_url, 
            headers=current_header, 
            data=data,
            timeout=15
        )
        
        if response.status_code != 200:
            raise Exception(f'登录失败，状态码: {response.status_code}')
            
        response_data = response.json()
        print(response_data['msg'])
        
        result = session.post(
            url=check_url, 
            headers=current_header,
            timeout=15
        )
        
        if result.status_code != 200:
            raise Exception(f'签到失败，状态码: {result.status_code}')
            
        result_data = result.json()
        content = result_data['msg']
        
        user_page = session.get(
            url=user_url,
            headers=current_header,
            timeout=15
        )

        html_content = None
        raw_text = user_page.text or ''

        try:
            j = user_page.json()
            if isinstance(j, dict):
                for v in j.values():
                    if not isinstance(v, str):
                        continue
                    s = v.strip()
                    if not s:
                        continue
                    try:
                        decoded = base64.b64decode(s)
                        if b'<' in decoded[:120]:
                            html_content = decoded.decode('utf-8', errors='ignore')
                            break
                    except Exception:
                        continue
        except Exception:
            # not json -> ignore
            pass

        if html_content is None:
            import re
            m = re.search(r'originBody\s*=\s*["\']([A-Za-z0-9+/=\n\r]+)["\']', raw_text, re.S)
            if m:
                b64 = m.group(1).replace('\n', '').replace('\r', '')
                try:
                    decoded = base64.b64decode(b64)
                    if b'<' in decoded[:120]:
                        html_content = decoded.decode('utf-8', errors='ignore')
                except Exception:
                    html_content = None

        if html_content is None:
            import re
            m2 = re.search(r'data-clipboard(?:-text)?=["\']([A-Za-z0-9+/=]+)["\']', raw_text)
            if m2:
                b64 = m2.group(1)
                try:
                    decoded = base64.b64decode(b64)
                    if b'<' in decoded[:120]:
                        html_content = decoded.decode('utf-8', errors='ignore')
                except Exception:
                    html_content = None

        if html_content is None:
            try:
                decoded = base64.b64decode(raw_text)
                if b'<' in decoded[:120]:
                    html_content = decoded.decode('utf-8', errors='ignore')
            except Exception:
                html_content = None

        if not html_content:
            html_content = raw_text

        soup = BeautifulSoup(html_content, 'html.parser')
        flow = None
        flow_unit = None

        cards = soup.find_all('div', class_='card card-statistic-2')
        for card in cards:
            h4 = card.find('h4')
            if h4 and '剩余流量' in h4.text:
                counter_span = card.find('span', class_='counter')
                if counter_span:
                    flow = counter_span.text.strip()
                    unit_text = ''
                    if counter_span.next_sibling and isinstance(counter_span.next_sibling, str):
                        unit_text = counter_span.next_sibling.strip()
                    if not unit_text:
                        small = card.find('small')
                        if small:
                            unit_text = small.text.strip()
                    flow_unit = unit_text
                    break
        return content, flow, flow_unit
    except Exception as e:
        print(f'发生错误: {e}')
        return '签到失败', None, None

def main():
    try:
        accounts = get_accounts_from_env()
        for account in accounts:
            email = account['email']
            passwd = account['passwd']
            print(f"\n开始处理账号: {email}")
            content, flow, flow_unit = check_in(email, passwd)
            print(f'签到结果: {content}')
            if flow:
                print(f'账号剩余流量: {flow}{flow_unit if flow_unit else ""}')
            else:
                print('未能获取账号流量信息')
    except Exception as e:
        print(f'程序出错: {e}')

if __name__ == '__main__':
    main()
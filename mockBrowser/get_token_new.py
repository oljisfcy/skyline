import urllib.parse
from pathlib import Path
import time
import os
import sys
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

USERNAME = "3125358040"
PASSWORD = "Xjtu3095@"
PLATFORM_HOST = "pahw.xjtu.edu.cn"
SKILL_DIR = Path("/home/oljisfcy/.openclaw/workspace/skills/xjtu-labor-activities")
TOKEN_FILE = SKILL_DIR / "token.txt"

def build_target_url():
    return (
        "https://org.xjtu.edu.cn/openplatform/oauth/authorize"
        "?appId=1733"
        "&redirectUri=https://pahw.xjtu.edu.cn/sso/callback"
        "&responseType=code"
        "&scope=user_info"
        "&state=1234"
    )

TARGET_URL = build_target_url()

def get_token():
    with sync_playwright() as p:
        print("\n[步骤 1] 正在启动无头浏览器...")
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        extracted_token = []

        def handle_request(request):
            if "api/v1/course/courseinfo" in request.url:
                post_data = request.post_data
                if post_data and "token=" in post_data:
                    parsed = urllib.parse.parse_qs(post_data)
                    if "token" in parsed:
                        token_found = parsed["token"][0].strip('"')
                        if token_found not in extracted_token:
                            extracted_token.append(token_found)

        page.on("request", handle_request)
        print(f"[步骤 2] 正在访问登录目标页面: {TARGET_URL}")
        page.goto(TARGET_URL, wait_until="load")

        if "login.xjtu.edu.cn" in page.url:
            print("[步骤 3] 成功进入 CAS 统一登录页，准备输入账号密码...")
            page.wait_for_selector('input[type="text"]', state="visible")
            page.fill('input[type="text"]', USERNAME)
            page.fill('input[type="password"]', PASSWORD)
            
            login_btn = page.locator('button:has-text("LOGIN"), button:has-text("登录"), .login-btn').first
            login_btn.click()
            
            print("[步骤 4] 已提交账号密码，正在等待验证跳转（或等待手机验证码拦截）...")
            time.sleep(4)
            
            mfa_input = page.locator("input[placeholder*='验证码']").first
            if mfa_input.is_visible():
                print("\n[!] 触发二次身份验证（手机验证码检测）！")
                
                # 勾选设为可信设备
                print("[步骤 5] 正在勾选『设为可信设备 / 可信客户端』...")
                try:
                    trusted_label = page.locator("text=设为可信客户端").first
                    if trusted_label.is_visible():
                        trusted_label.click(force=True)
                        print("[成功] 已勾选可信设备。")
                    else:
                        print("[警告] 未能找到可信设备的勾选项。")
                except Exception as e:
                    print(f"[警告] 勾选可信设备异常: {e}")
                
                time.sleep(1)

                # 点击发送验证码
                print("[步骤 6] 正在点击发送验证码按钮...")
                send_btn = page.locator("button:has-text('获取'), button:has-text('发送'), :text('获取验证码')").first
                if send_btn.is_visible():
                    send_btn.click(force=True)
                    print("[成功] 已点击『发送验证码』，验证码应已发送至您的手机/邮箱。等待 2 秒以确保界面更新...")
                    time.sleep(2)
                else:
                    print("[错误] 未能找到发送验证码按钮。")
                
                # 截图留证
                print("[步骤 7] 正在截图以确保验证码已发送...")
                debug_img = SKILL_DIR / "mfa_waiting.png"
                page.screenshot(path=str(debug_img), full_page=True)
                print(f"[截图保存成功] 当前屏幕截图路径: {debug_img}")
                
                # 等待用户输入
                print("\n" + "="*50)
                print(">>> ⚠️ 需要人工介入 ⚠️ <<<")
                sms_code = input("[交互] 请输入您收到的 6 位验证码 (直接按回车退出): ").strip()
                print("="*50 + "\n")

                if sms_code:
                    print(f"[步骤 8] 正在自动填充验证码: {sms_code}")
                    mfa_input.fill(sms_code)
                    
                    print("[步骤 9] 正在点击提交/确认按钮...")
                    # 绝大多数表单在输入框内按回车最有效
                    mfa_input.press("Enter")
                    time.sleep(1)
                    
                    # 强力点击逻辑 1：使用 Playwright 的正则文本匹配，找到最后一个可见的按钮并强制点击
                    try:
                        confirm_btn = page.locator("text=/(确\\s*定|确\\s*认|提\\s*交|验\\s*证)/").locator("visible=true").last
                        if confirm_btn.is_visible():
                            confirm_btn.click(force=True)
                            print("[调试] 强力点击1：已使用 Playwright 强制点击文本按钮")
                    except Exception as e:
                        print(f"[调试] 强力点击1异常: {e}")

                    # 强力点击逻辑 2：无差别全量 DOM 扫描点击（去除所有空格干扰，不限制标签类型）
                    try:
                        page.evaluate("""() => {
                            const elements = Array.from(document.querySelectorAll('*'));
                            // 倒序遍历，通常弹窗在 DOM 树最末尾
                            for (let i = elements.length - 1; i >= 0; i--) {
                                const el = elements[i];
                                // 如果该元素包含子元素且也有同样的文本，跳过父元素，只点最内层
                                if (el.children.length > 1) continue;
                                
                                const text = (el.textContent || '').replace(/\\s+/g, '');
                                if (['确定', '确认', '验证', '提交'].includes(text)) {
                                    const style = window.getComputedStyle(el);
                                    if (style.display !== 'none' && style.visibility !== 'hidden' && el.offsetHeight > 0) {
                                        el.click(); // 原生 click
                                        // 触发 Vue/React 的绑定事件
                                        el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                                        el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                                        break;
                                    }
                                }
                            }
                        }""")
                        print("[调试] 强力点击2：已执行无差别 DOM 扫描并派发底层 MouseEvent 事件")
                    except Exception as e:
                        print(f"[调试] 强力点击2异常: {e}")
                        
                    print("[步骤 10] 提交成功，正在等待页面验证并跳转进入劳育系统...")
                    time.sleep(5)
                    
                    # 截图保存提交后的状态，方便排查
                    submit_img = SKILL_DIR / "after_submit.png"
                    page.screenshot(path=str(submit_img), full_page=True)
                    print(f"[调试] 提交后的页面状态已截图保存至: {submit_img}")
                else:
                    print("[退出] 用户取消输入，退出脚本。")
                    browser.close()
                    return False
            else:
                print("\n[跳过] 未触发验证码，直接跳转...")

        print("[步骤 11] 等待进入最终系统并抓取 Token...")
        try:
            page.wait_for_url("https://pahw.xjtu.edu.cn/**", timeout=20000)
            print("[成功] 已顺利进入劳育平台首页。")
            page.wait_for_timeout(3000)
        except Exception:
            print("[警告] 跳转检测超时，尝试强制从当前页面提取 localStorage...")

        if not extracted_token:
            token_val = page.evaluate("() => window.localStorage.getItem('token')")
            if token_val:
                extracted_token.append(token_val.strip('"'))

        browser.close()
        
        if extracted_token:
            final_token = extracted_token[0]
            with open(TOKEN_FILE, "w") as f:
                f.write(final_token)
            print(f"\n========================================")
            print(f"✅ 抓取成功！Token 已成功保存至: {TOKEN_FILE}")
            print(f"========================================\n")
            return True
        else:
            print("\n❌ 抓取失败：未能在系统页面中发现 Token。")
            return False

if __name__ == "__main__":
    get_token()

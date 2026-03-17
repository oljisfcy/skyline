import urllib.parse
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

USERNAME = "3125358040"
PASSWORD = "Xjtu3095@"
PLATFORM_HOST = "pahw.xjtu.edu.cn"
DEBUG_SCREENSHOT = Path("mockBrowser_debug.png")


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


def is_platform_url(url):
    return urllib.parse.urlparse(url).netloc == PLATFORM_HOST


def read_local_storage_token(page):
    token = page.evaluate("() => window.localStorage.getItem('token')")
    return token.strip('"') if token else None


def save_debug_snapshot(page):
    print(f"当前 URL: {page.url}")
    print(f"当前标题: {page.title()}")
    try:
        storage_keys = page.evaluate("() => Object.keys(window.localStorage)")
        print(f"localStorage keys: {storage_keys}")
    except Exception as exc:
        print(f"读取 localStorage 失败: {exc}")

    try:
        page.screenshot(path=str(DEBUG_SCREENSHOT), full_page=True)
        print(f"调试截图已保存: {DEBUG_SCREENSHOT.resolve()}")
    except Exception as exc:
        print(f"保存调试截图失败: {exc}")


def wait_for_platform_token(page, timeout_ms=30000):
    page.wait_for_url("https://pahw.xjtu.edu.cn/**", timeout=timeout_ms)
    page.wait_for_function(
        "() => !!window.localStorage.getItem('token')",
        timeout=timeout_ms,
    )


def get_token():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        extracted_token = []

        def handle_request(request):
            if "api/v1/course/courseinfo" not in request.url:
                return

            post_data = request.post_data
            if not post_data or "token=" not in post_data:
                return

            parsed = urllib.parse.parse_qs(post_data)
            if "token" in parsed:
                extracted_token.append(parsed["token"][0].strip('"'))

        page.on("request", handle_request)
        page.goto(TARGET_URL, wait_until="load")

        if "login.xjtu.edu.cn" in page.url:
            print("正在自动填写账号密码...")
            page.fill('input[type="text"]', USERNAME)
            page.fill('input[type="password"]', PASSWORD)
            page.click(".login-btn")

        print("等待登录成功并获取 Token...")

        try:
            wait_for_platform_token(page)
        except PlaywrightTimeoutError:
            print("未能在预期时间内进入平台首页。")
            save_debug_snapshot(page)

        if not extracted_token and is_platform_url(page.url):
            token_val = read_local_storage_token(page)
            if token_val:
                extracted_token.append(token_val)

        browser.close()

        if extracted_token:
            print(f"成功提取到最新的 Token: {extracted_token[0]}")
        else:
            print("未能提取到 Token，请根据上面的 URL、标题和截图继续排查。")


if __name__ == "__main__":
    get_token()

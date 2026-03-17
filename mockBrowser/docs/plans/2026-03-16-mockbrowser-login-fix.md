# MockBrowser Login Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `mockBrowser.py` enter the correct XJTU OAuth login flow, wait for the pahw platform to finish loading, and surface useful debug evidence on failure.

**Architecture:** Keep the script as a single file, but extract a few small helpers so the URL selection and success detection are testable without launching a browser. Keep token extraction in Playwright, but replace `networkidle` with condition-based waiting on the pahw host and `localStorage.token`.

**Tech Stack:** Python, Playwright sync API, `unittest`

---

### Task 1: Add regression tests for the login entry URL and platform detection

**Files:**
- Create: `tests/test_mockBrowser.py`
- Test: `mockBrowser.py`

**Step 1: Write the failing test**

```python
import unittest
import mockBrowser


class MockBrowserTests(unittest.TestCase):
    def test_build_target_url_uses_oauth_entrypoint(self):
        url = mockBrowser.build_target_url()
        self.assertIn("org.xjtu.edu.cn/openplatform/oauth/authorize", url)
        self.assertIn("redirectUri=https://pahw.xjtu.edu.cn/sso/callback", url)

    def test_is_platform_url_only_accepts_pahw_host(self):
        self.assertTrue(mockBrowser.is_platform_url("https://pahw.xjtu.edu.cn/index"))
        self.assertFalse(mockBrowser.is_platform_url("https://login.xjtu.edu.cn/cas/login"))
```

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: FAIL because `build_target_url` and `is_platform_url` do not exist yet.

**Step 3: Write minimal implementation**

```python
def build_target_url():
    return (
        "https://org.xjtu.edu.cn/openplatform/oauth/authorize"
        "?appId=1733"
        "&redirectUri=https://pahw.xjtu.edu.cn/sso/callback"
        "&responseType=code"
        "&scope=user_info"
        "&state=1234"
    )


def is_platform_url(url):
    return urllib.parse.urlparse(url).netloc == "pahw.xjtu.edu.cn"
```

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: PASS

### Task 2: Update the Playwright flow to use the correct entry URL and condition-based waiting

**Files:**
- Modify: `mockBrowser.py`
- Test: `tests/test_mockBrowser.py`

**Step 1: Write the failing test**

Reuse Task 1 tests as the regression guard before changing runtime behavior.

**Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: FAIL until helpers are implemented and wired in.

**Step 3: Write minimal implementation**

```python
TARGET_URL = build_target_url()
page.goto(TARGET_URL, wait_until="load")
page.wait_for_url("https://pahw.xjtu.edu.cn/**", timeout=30000)
page.wait_for_function(
    "() => !!window.localStorage.getItem('token')",
    timeout=30000,
)
```

Add lightweight debug output on failure:

```python
print(f"当前 URL: {page.url}")
print(f"当前标题: {page.title()}")
page.screenshot(path="mockBrowser_debug.png", full_page=True)
```

**Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: PASS

### Task 3: Verify the script against the real site

**Files:**
- Modify: `mockBrowser.py`

**Step 1: Run the script manually**

Run: `$env:PYTHONIOENCODING='utf-8'; python .\mockBrowser.py`

**Step 2: Verify runtime behavior**

Expected:
- Browser reaches `https://pahw.xjtu.edu.cn/index` or another `pahw.xjtu.edu.cn` page
- `localStorage.token` is present and printed
- If it still fails, output includes current URL/title and saves `mockBrowser_debug.png`

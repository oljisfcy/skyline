import unittest

import mockBrowser.mockBrowser as mockBrowser


class MockBrowserTests(unittest.TestCase):
    def test_build_target_url_uses_oauth_entrypoint(self):
        url = mockBrowser.build_target_url()
        self.assertIn("org.xjtu.edu.cn/openplatform/oauth/authorize", url)
        self.assertIn("redirectUri=https://pahw.xjtu.edu.cn/sso/callback", url)
        self.assertIn("scope=user_info", url)

    def test_is_platform_url_only_accepts_pahw_host(self):
        self.assertTrue(mockBrowser.is_platform_url("https://pahw.xjtu.edu.cn/index"))
        self.assertFalse(mockBrowser.is_platform_url("https://login.xjtu.edu.cn/cas/login"))


if __name__ == "__main__":
    unittest.main()

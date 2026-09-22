import unittest
from handfont.web import host_name, origin_allowed, ui_command


class ServeTest(unittest.TestCase):
    def test_vite_origin_on_localhost_is_allowed(self):
        self.assertTrue(origin_allowed(None, "127.0.0.1:8788"))
        self.assertTrue(origin_allowed("http://127.0.0.1:8788", "127.0.0.1:8788"))
        self.assertTrue(origin_allowed("http://127.0.0.1:5173", "127.0.0.1:8788"))
        self.assertTrue(origin_allowed("http://localhost:5173", "127.0.0.1:8788"))
        self.assertFalse(origin_allowed("http://evil.example", "127.0.0.1:8788"))

    def test_host_name_strips_port(self):
        self.assertEqual(host_name("127.0.0.1:8788"), "127.0.0.1")
        self.assertEqual(host_name("[::1]:5173"), "::1")

    def test_ui_command_pins_vite_port(self):
        self.assertEqual(
            ui_command("127.0.0.1", 5173),
            ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
        )

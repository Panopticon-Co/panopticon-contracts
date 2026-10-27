"""Regression checks for real process calls versus observed execution facts."""
import tempfile
import unittest
from pathlib import Path

from validate_fixtures import BANNED_PATTERNS, grep_repos


class ExecutionScanTests(unittest.TestCase):
    def findings(self, text, suffix):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ("response" + suffix)).write_text(text, encoding="utf-8")
            return grep_repos([root])

    def test_telemetry_identifiers_and_sqlite_wrapper_are_not_execution(self):
        for text, suffix in [
            ("void on_exec(int pid); int execve_count;", ".hpp"),
            ("static void exec(sqlite3* db, const char* sql); exec(db, sql);", ".cpp"),
            ("def _chain_at_exec(events): return events", ".py"),
            ("// The kernel path is what execve() was given.\nint pid;", ".cpp"),
            ("/* Observed execve(path, argv, env) */\nint pid;", ".hpp"),
        ]:
            with self.subTest(text=text):
                self.assertEqual(self.findings(text, suffix), [])

    def test_native_and_python_execution_calls_are_still_flagged(self):
        for text, suffix in [
            ('std::system ("cmd");', ".cpp"),
            ('os.system("command")', ".py"),
            ('popen ("command", "r");', ".cpp"),
            ('exec (user_input)', ".py"),
            ('execve (path, argv, env);', ".cpp"),
            ('execvp(path, argv);', ".cpp"),
            ('const char* url = "https://example.com"; execve(path, argv, env);', ".cpp"),
            ('const char* shell = "/bin/sh";', ".cpp"),
            ('action = "EXECUTE_COMMAND"', ".py"),
        ]:
            with self.subTest(text=text):
                self.assertTrue(self.findings(text, suffix))

    def test_original_native_exec_family_and_extensions_are_covered(self):
        for name in ["execl", "execlp", "execle", "execv", "execvp", "execve", "execvpe"]:
            self.assertIn(name, BANNED_PATTERNS)
            self.assertTrue(self.findings(name + "(path, argv);", ".cpp"))


if __name__ == "__main__":
    unittest.main()

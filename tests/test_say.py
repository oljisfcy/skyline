import tempfile
import unittest
from subprocess import CompletedProcess, TimeoutExpired
from pathlib import Path

from say.cli import (
    build_remote_script,
    build_remote_worker_script,
    build_ordered_filenames,
    main,
    parse_args,
    run_remote_sequence,
    run_sequence,
    tokenize_text,
)


class SayToolTests(unittest.TestCase):
    def test_tokenize_text_splits_words_and_punctuation(self):
        self.assertEqual(
            tokenize_text("how about today?"),
            ["how", "about", "today", "?"],
        )

    def test_parse_args_defaults_to_three_quarter_second_interval(self):
        args = parse_args(["hello?"])

        self.assertEqual(args.interval, 0.75)

    def test_build_ordered_filenames_keeps_question_mark_on_linux(self):
        self.assertEqual(
            build_ordered_filenames(["how", "about", "today", "?"], system="Linux"),
            ["a-how", "b-about", "c-today", "d-?"],
        )

    def test_build_ordered_filenames_replaces_invalid_windows_characters(self):
        self.assertEqual(
            build_ordered_filenames(["how", "about", "today", "?"], system="Windows"),
            ["a-how", "b-about", "c-today", "d-\uFF1F"],
        )

    def test_run_sequence_creates_waits_then_deletes_directories_in_order(self):
        sleeps = []
        events = []

        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir)

            run_sequence(
                ["how", "about", "today", "?"],
                target_dir,
                interval=0.25,
                hold=3,
                system="Windows",
                sleeper=sleeps.append,
                event_hook=lambda action, path: events.append(
                    (
                        action,
                        path.name,
                        path.is_dir() if action == "created" else path.exists(),
                    )
                ),
            )

            self.assertEqual(
                events,
                [
                    ("created", "a-how", True),
                    ("created", "b-about", True),
                    ("created", "c-today", True),
                    ("created", "d-\uFF1F", True),
                    ("deleted", "a-how", False),
                    ("deleted", "b-about", False),
                    ("deleted", "c-today", False),
                    ("deleted", "d-\uFF1F", False),
                ],
            )
            self.assertEqual(sleeps, [0.25, 0.25, 0.25, 3, 0.25, 0.25, 0.25])
            self.assertEqual(list(target_dir.iterdir()), [])

    def test_run_sequence_refuses_to_overwrite_existing_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir)
            existing_path = target_dir / "a-how"
            existing_path.mkdir()

            with self.assertRaises(FileExistsError):
                run_sequence(["how"], target_dir, interval=0, hold=0)

            self.assertTrue(existing_path.is_dir())

    def test_run_sequence_cleanup_does_not_delete_replacement_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir)
            replacement_path = target_dir / "a-how"

            def replace_directory_then_fail(action, path):
                if action == "created":
                    path.rmdir()
                    path.write_text("do not delete\n", encoding="utf-8")
                    raise RuntimeError("stop after replacement")

            with self.assertRaises(RuntimeError):
                run_sequence(
                    ["how"],
                    target_dir,
                    interval=0,
                    hold=0,
                    event_hook=replace_directory_then_fail,
                )

            self.assertEqual(
                replacement_path.read_text(encoding="utf-8"),
                "do not delete\n",
            )

    def test_run_sequence_cleanup_does_not_delete_replacement_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir)
            replacement_path = target_dir / "a-how"

            def replace_directory_then_fail(action, path):
                if action == "created":
                    path.rmdir()
                    path.write_text("do not delete\n", encoding="utf-8")
                    raise RuntimeError("stop after replacement")

            with self.assertRaises(RuntimeError):
                run_sequence(
                    ["how"],
                    target_dir,
                    interval=0,
                    hold=0,
                    event_hook=replace_directory_then_fail,
                )

            self.assertEqual(
                replacement_path.read_text(encoding="utf-8"),
                "do not delete\n",
            )

    def test_main_accepts_dir_option_and_cleans_up_after_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            exit_code = main(
                [
                    "--dir",
                    temp_dir,
                    "--interval",
                    "0",
                    "--hold",
                    "0",
                    "how",
                    "about",
                    "today?",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    def test_run_remote_sequence_uploads_worker_with_ssh_cat_by_default(self):
        calls = []

        def fake_runner(command, **kwargs):
            calls.append((command, kwargs))
            return CompletedProcess(command, 0)

        run_remote_sequence(
            "cys",
            ["hello", "?"],
            "/tmp/say-demo",
            interval=0.25,
            hold=3,
            worker_id="testworker",
            runner=fake_runner,
        )

        self.assertEqual(len(calls), 2)
        upload_command, upload_kwargs = calls[0]
        ssh_command, ssh_kwargs = calls[1]

        self.assertEqual(
            upload_command[:-1],
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-p",
                "22804",
                "root@180.163.219.95",
            ],
        )
        self.assertEqual(upload_command[-1], "cat > /tmp/say_remote_worker_testworker.py")
        self.assertIn("def main():", upload_kwargs["input"])
        self.assertEqual(upload_kwargs["timeout"], 15)
        self.assertTrue(upload_kwargs["capture_output"])
        self.assertTrue(upload_kwargs["text"])

        self.assertEqual(
            ssh_command[:-1],
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-p",
                "22804",
                "root@180.163.219.95",
            ],
        )
        self.assertIn("python3 /tmp/say_remote_worker_testworker.py", ssh_command[-1])
        self.assertIn('"/tmp/say-demo"', ssh_command[-1])
        self.assertIn('"a-hello"', ssh_command[-1])
        self.assertIn('"b-?"', ssh_command[-1])
        self.assertGreaterEqual(ssh_kwargs["timeout"], 18.5)
        self.assertTrue(ssh_kwargs["capture_output"])
        self.assertTrue(ssh_kwargs["text"])

    def test_run_remote_sequence_uses_xb_ssh_target(self):
        calls = []

        def fake_runner(command, **kwargs):
            calls.append((command, kwargs))
            return CompletedProcess(command, 0)

        run_remote_sequence(
            "xb",
            ["hello", "?"],
            "/tmp/say-demo",
            interval=0,
            hold=0,
            worker_id="testworker",
            runner=fake_runner,
        )

        upload_command, _ = calls[0]
        ssh_command, _ = calls[1]
        self.assertIn("22806", upload_command)
        self.assertIn("22806", ssh_command)
        self.assertIn("root@180.163.219.95", upload_command)
        self.assertIn("root@180.163.219.95", ssh_command)

    def test_run_remote_sequence_includes_stderr_when_ssh_fails(self):
        calls = []

        def fake_runner(command, **kwargs):
            calls.append(command)
            if len(calls) == 1:
                return CompletedProcess(command, 0)
            return CompletedProcess(command, 255, stderr="Permission denied")

        with self.assertRaisesRegex(RuntimeError, "Permission denied"):
            run_remote_sequence(
                "xb",
                ["hello"],
                "/tmp/say-demo",
                interval=0,
                hold=0,
                worker_id="testworker",
                runner=fake_runner,
            )

    def test_run_remote_sequence_reports_transfer_timeout(self):
        def fake_runner(command, **kwargs):
            raise TimeoutExpired(command, kwargs["timeout"])

        with self.assertRaisesRegex(RuntimeError, "remote worker upload timed out"):
            run_remote_sequence(
                "xb",
                ["hello"],
                "/tmp/say-demo",
                interval=0,
                hold=0,
                worker_id="testworker",
                runner=fake_runner,
            )

    def test_remote_workers_do_not_unlink_replacement_files(self):
        payload = {
            "target_dir": "/tmp/say-demo",
            "items": [{"filename": "a-how", "token": "how"}],
            "interval": 0,
            "hold": 0,
            "verbose": False,
        }

        self.assertNotIn("path.unlink()", build_remote_script(payload))
        self.assertNotIn("path.unlink()", build_remote_worker_script())

    def test_run_remote_sequence_rejects_unknown_remote_alias(self):
        with self.assertRaises(ValueError):
            run_remote_sequence("missing", ["hello"], "/tmp/say-demo")


if __name__ == "__main__":
    unittest.main()

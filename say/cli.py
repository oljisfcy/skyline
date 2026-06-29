import argparse
import json
import math
import platform
import re
import shlex
import string
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path


TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
WINDOWS_REPLACEMENTS = {
    "<": "\uFF1C",
    ">": "\uFF1E",
    ":": "\uFF1A",
    '"': "\uFF02",
    "/": "\uFF0F",
    "\\": "\uFF3C",
    "|": "\uFF5C",
    "?": "\uFF1F",
    "*": "\uFF0A",
    "\0": "",
}
POSIX_REPLACEMENTS = {
    "/": "\uFF0F",
    "\0": "",
}
SSH_OPTIONS = [
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=8",
    "-o",
    "StrictHostKeyChecking=accept-new",
]
REMOTE_WORKER_PREFIX = "/tmp/say_remote_worker_"
REMOTE_TARGETS = {
    "cys": {
        "host": "root@180.163.219.95",
        "port": 22804,
        "system": "Linux",
    },
    "xb": {
        "host": "root@180.163.219.95",
        "port": 22806,
        "system": "Linux",
    },
}


def tokenize_text(text):
    return TOKEN_PATTERN.findall(text)


def _label_width(count):
    if count <= 0:
        return 1
    return max(1, math.ceil(math.log(count, len(string.ascii_lowercase))))


def _alphabetic_label(index, width):
    alphabet = string.ascii_lowercase
    chars = []
    value = index

    for _ in range(width):
        chars.append(alphabet[value % len(alphabet)])
        value //= len(alphabet)

    return "".join(reversed(chars))


def sanitize_token(token, system=None):
    system_name = system or platform.system()
    replacements = (
        WINDOWS_REPLACEMENTS
        if system_name.lower().startswith("win")
        else POSIX_REPLACEMENTS
    )

    safe = "".join(replacements.get(char, char) for char in token)
    return safe or "blank"


def build_ordered_filenames(tokens, system=None):
    width = _label_width(len(tokens))
    return [
        f"{_alphabetic_label(index, width)}-{sanitize_token(token, system=system)}"
        for index, token in enumerate(tokens)
    ]


def build_remote_worker_path(worker_id=None):
    identifier = worker_id or uuid.uuid4().hex
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", identifier):
        raise ValueError("remote worker id contains unsafe characters")
    return f"{REMOTE_WORKER_PREFIX}{identifier}.py"


def _validate_sequence_options(tokens, interval, hold):
    if interval < 0:
        raise ValueError("interval must be non-negative")
    if hold < 0:
        raise ValueError("hold must be non-negative")
    if not tokens:
        raise ValueError("no words or punctuation to say")


def run_sequence(
    tokens,
    target_dir,
    interval=0.25,
    hold=3,
    system=None,
    sleeper=time.sleep,
    event_hook=None,
):
    _validate_sequence_options(tokens, interval, hold)

    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)

    filenames = build_ordered_filenames(tokens, system=system)
    paths = [target_path / filename for filename in filenames]
    existing_paths = [path for path in paths if path.exists()]
    if existing_paths:
        names = ", ".join(path.name for path in existing_paths)
        raise FileExistsError(f"refusing to overwrite existing path(s): {names}")

    created_paths = []
    try:
        for index, (path, token) in enumerate(zip(paths, tokens)):
            path.mkdir()
            created_paths.append(path)
            if event_hook:
                event_hook("created", path)
            if index < len(paths) - 1:
                sleeper(interval)

        sleeper(hold)

        for index, path in enumerate(paths):
            path.rmdir()
            if event_hook:
                event_hook("deleted", path)
            if index < len(paths) - 1:
                sleeper(interval)
    except Exception:
        for path in reversed(created_paths):
            if path.is_dir():
                path.rmdir()
        raise


def build_remote_script(payload):
    payload_literal = repr(json.dumps(payload, ensure_ascii=True))
    return f"""\
import json
import time
from pathlib import Path

payload = json.loads({payload_literal})
target_path = Path(payload["target_dir"])
target_path.mkdir(parents=True, exist_ok=True)

paths = [target_path / item["filename"] for item in payload["items"]]
existing_paths = [path for path in paths if path.exists()]
if existing_paths:
    names = ", ".join(path.name for path in existing_paths)
    raise FileExistsError(f"refusing to overwrite existing path(s): {{names}}")

created_paths = []
try:
    for index, item in enumerate(payload["items"]):
        path = target_path / item["filename"]
        path.mkdir()
        created_paths.append(path)
        if index < len(paths) - 1:
            time.sleep(payload["interval"])

    time.sleep(payload["hold"])

    for index, path in enumerate(paths):
        path.rmdir()
        if index < len(paths) - 1:
            time.sleep(payload["interval"])
except Exception:
    for path in reversed(created_paths):
        if path.is_dir():
            path.rmdir()
    raise
"""


def build_remote_worker_script():
    return """\
import json
import sys
import time
from pathlib import Path


def main():
    payload = json.loads(sys.argv[1])
    target_path = Path(payload["target_dir"])
    target_path.mkdir(parents=True, exist_ok=True)

    paths = [target_path / item["filename"] for item in payload["items"]]
    existing_paths = [path for path in paths if path.exists()]
    if existing_paths:
        names = ", ".join(path.name for path in existing_paths)
        raise FileExistsError(f"refusing to overwrite existing path(s): {names}")

    def log(action, path):
        if payload.get("verbose"):
            print(f"{action} {path}", flush=True)

    created_paths = []
    try:
        for index, item in enumerate(payload["items"]):
            path = target_path / item["filename"]
            path.mkdir()
            created_paths.append(path)
            log("created", path)
            if index < len(paths) - 1:
                time.sleep(payload["interval"])

        time.sleep(payload["hold"])

        for index, path in enumerate(paths):
            path.rmdir()
            log("deleted", path)
            if index < len(paths) - 1:
                time.sleep(payload["interval"])
    except Exception:
        for path in reversed(created_paths):
            if path.is_dir():
                path.rmdir()
        raise

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _run_checked(command, runner, description, timeout=None, **kwargs):
    try:
        result = runner(
            command,
            text=True,
            capture_output=True,
            timeout=timeout,
            **kwargs,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"{description} timed out after {error.timeout}s"
        ) from error

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        message = f"{description} failed with exit code {result.returncode}"
        if detail:
            message = f"{message}: {detail}"
        raise RuntimeError(message)

    return result


def run_remote_sequence(
    remote,
    tokens,
    target_dir,
    interval=0.25,
    hold=3,
    transfer="ssh-cat",
    remote_timeout=15,
    verbose=False,
    worker_id=None,
    runner=subprocess.run,
):
    if remote not in REMOTE_TARGETS:
        known_remotes = ", ".join(sorted(REMOTE_TARGETS))
        raise ValueError(f"unknown remote alias '{remote}' (known: {known_remotes})")

    target = REMOTE_TARGETS[remote]
    _validate_sequence_options(tokens, interval, hold)
    filenames = build_ordered_filenames(tokens, system=target["system"])
    payload = {
        "target_dir": str(target_dir),
        "items": [
            {"filename": filename, "token": token}
            for filename, token in zip(filenames, tokens)
        ],
        "interval": interval,
        "hold": hold,
        "verbose": verbose,
    }

    animation_duration = hold + (max(0, len(tokens) - 1) * interval * 2)
    run_timeout = max(remote_timeout, animation_duration + remote_timeout)
    remote_worker_path = build_remote_worker_path(worker_id)

    if transfer == "stdin":
        command = [
            "ssh",
            *SSH_OPTIONS,
            "-p",
            str(target["port"]),
            target["host"],
            "python3",
            "-",
        ]
        result = _run_checked(
            command,
            runner,
            "remote say",
            timeout=run_timeout,
            input=build_remote_script(payload),
        )
    elif transfer == "ssh-cat":
        upload_command = [
            "ssh",
            *SSH_OPTIONS,
            "-p",
            str(target["port"]),
            target["host"],
            f"cat > {shlex.quote(remote_worker_path)}",
        ]
        _run_checked(
            upload_command,
            runner,
            "remote worker upload",
            timeout=remote_timeout,
            input=build_remote_worker_script(),
        )

        payload_json = json.dumps(payload, ensure_ascii=True)
        remote_command = (
            f"python3 {shlex.quote(remote_worker_path)} {shlex.quote(payload_json)}"
        )
        command = [
            "ssh",
            *SSH_OPTIONS,
            "-p",
            str(target["port"]),
            target["host"],
            remote_command,
        ]
        result = _run_checked(command, runner, "remote say", timeout=run_timeout)
    elif transfer == "scp":
        with tempfile.TemporaryDirectory() as temp_dir:
            worker_path = Path(temp_dir) / "say_remote_worker.py"
            worker_path.write_text(build_remote_worker_script(), encoding="utf-8")
            scp_command = [
                "scp",
                "-q",
                *SSH_OPTIONS,
                "-P",
                str(target["port"]),
                str(worker_path),
                f"{target['host']}:{remote_worker_path}",
            ]
            _run_checked(
                scp_command,
                runner,
                "remote worker upload",
                timeout=remote_timeout,
            )

        payload_json = json.dumps(payload, ensure_ascii=True)
        remote_command = (
            f"python3 {shlex.quote(remote_worker_path)} {shlex.quote(payload_json)}"
        )
        command = [
            "ssh",
            *SSH_OPTIONS,
            "-p",
            str(target["port"]),
            target["host"],
            remote_command,
        ]
        result = _run_checked(command, runner, "remote say", timeout=run_timeout)
    else:
        raise ValueError("remote transfer must be 'ssh-cat', 'scp', or 'stdin'")

    if verbose and result.stdout:
        print(result.stdout, end="")


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="say",
        description="Create ordered word directories, pause, then delete them.",
    )
    parser.add_argument(
        "-r",
        "--remote",
        choices=sorted(REMOTE_TARGETS),
        help="run on a configured remote target instead of this machine",
    )
    parser.add_argument(
        "text",
        nargs="+",
        help="text to split into word and punctuation directory names",
    )
    parser.add_argument(
        "-d",
        "--dir",
        default=".",
        help="directory where the temporary directories appear",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.75,
        help="seconds between each directory appearing or disappearing",
    )
    parser.add_argument(
        "--hold",
        type=float,
        default=3,
        help="seconds to keep the full sentence visible before deletion starts",
    )
    parser.add_argument(
        "--remote-transfer",
        choices=["ssh-cat", "scp", "stdin"],
        default="ssh-cat",
        help="how to send remote code before execution",
    )
    parser.add_argument(
        "--remote-timeout",
        type=float,
        default=15,
        help="base seconds before remote upload/connect operations time out",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print create/delete events while running",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    tokens = tokenize_text(" ".join(args.text))

    try:
        if args.remote:
            run_remote_sequence(
                args.remote,
                tokens,
                args.dir,
                interval=args.interval,
                hold=args.hold,
                transfer=args.remote_transfer,
                remote_timeout=args.remote_timeout,
                verbose=args.verbose,
            )
        else:
            event_hook = None
            if args.verbose:
                event_hook = lambda action, path: print(f"{action} {path}")
            run_sequence(
                tokens,
                args.dir,
                interval=args.interval,
                hold=args.hold,
                event_hook=event_hook,
            )
    except Exception as error:
        print(f"say: {error}", file=sys.stderr)
        return 1

    return 0

"""Authenticated guest execution over libvirt's serial console using stdlib only.

The guest agent remains confined by SELinux. Administrative commands instead
run in the guest's normal PAM login session; credentials never enter argv.
"""

from __future__ import annotations

import os
import pty
import re
import select
import secrets
import shlex
import subprocess
import time


def execute(uri: str, name: str, user: str, password: str, args: list[str], timeout: int) -> tuple[int, str, str]:
    master, slave = pty.openpty()
    process = subprocess.Popen(
        ["virsh", "-c", uri, "console", name], stdin=slave, stdout=slave, stderr=slave,
        close_fds=True, env={**os.environ, "LC_ALL": "C"},
    )
    os.close(slave)
    buffer = ""
    deadline = time.monotonic() + min(timeout, 60)

    def send(value: str) -> None:
        os.write(master, value.encode())

    def expect(pattern: str, *, refresh_prompt: bool = False) -> re.Match[str]:
        nonlocal buffer
        last_probe = time.monotonic()
        while time.monotonic() < deadline:
            match = re.search(pattern, buffer)
            if match:
                return match
            if process.poll() is not None:
                raise RuntimeError("The owned VM serial console disconnected.")
            if select.select([master], [], [], min(1, max(0, deadline - time.monotonic())))[0]:
                buffer += os.read(master, 65536).decode(errors="replace")
            elif refresh_prompt and time.monotonic() - last_probe >= 1:
                # libvirt may print its banner before forwarding the first
                # input byte. A blank line safely refreshes login/shell prompts.
                send("\n")
                last_probe = time.monotonic()
        raise RuntimeError("Timed out waiting for the owned VM serial console.")

    try:
        match = expect(r"Escape character is[^\r\n]*[\r\n]")
        buffer = buffer[match.end():]
        send("\n")
        match = expect(r"login:|(?:^|[\r\n])[^\r\n]*[$#] ", refresh_prompt=True)
        buffer = buffer[match.end():]
        if match.group() == "login:":
            send(user + "\n")
            match = expect("Password:")
            buffer = buffer[match.end():]
            send(password + "\n")
            match = expect(r"(?:^|[\r\n])[^\r\n]*[$#] ")
            buffer = buffer[match.end():]
        token = "LOOFI_" + secrets.token_hex(12)
        prompt = token + "# "
        send("export PS1=" + shlex.quote(prompt) + "; stty -echo\n")
        match = expect(re.escape(prompt) + r"(?!')")
        buffer = buffer[match.end():]
        sudo_prompt = token + "_PASSWORD"
        end = token + "_EXIT:"
        command = shlex.join(args)
        deadline = time.monotonic() + timeout
        # sudo reads its password from the console; shell arguments contain no secret.
        send("sudo -S -p " + shlex.quote(sudo_prompt) + " -- " + command + "; printf '\\n" + end + "%s\\n' \"$?\"\n")
        output = ""
        while True:
            match = expect(re.escape(sudo_prompt) + "|" + re.escape(end) + r"(\d+)\r?\n")
            output += buffer[:match.start()]
            buffer = buffer[match.end():]
            if match.group(1) is not None:
                # Strip terminal escape sequences and redact even unexpectedly echoed input.
                output = output.replace(password, "[redacted]")
                output = re.sub(r"\x1b\].*?(?:\x1b\\|\x07)", "", output, flags=re.S)
                output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
                return int(match.group(1)), output, ""
            send(password + "\n")
    finally:
        try:
            send("\x1d")
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            process.terminate()
            process.wait(timeout=5)
        os.close(master)

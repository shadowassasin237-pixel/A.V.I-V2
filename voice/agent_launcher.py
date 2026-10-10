"""
A.V.I. LiveKit agent launcher.

Starts the LiveKit AgentServer as a child process so the user can
continue to launch the whole desktop application with:

    python app.py

The child process runs voice/livekit_agent.py, where the Inworld
Ashley TTS plugin is safely created inside the LiveKit agent job.

Supports both script mode and PyInstaller-frozen mode (where the
agent is built as a separate exe next to the GUI exe).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


class AVIAgentLauncher:
    def __init__(self):
        self.process: subprocess.Popen | None = None

    def start(self) -> bool:
        if self.process is not None and self.process.poll() is None:
            return True

        # Resolve paths differently for frozen vs script mode.
        if _is_frozen():
            # When the GUI is built into AVI.exe, look for the
            # separately-built AVI_Agent.exe next to it.
            exe_dir = Path(sys.executable).resolve().parent
            agent_exe = exe_dir / "AVI_Agent.exe"
            if not agent_exe.exists():
                print(
                    "A.V.I. LiveKit agent not found at "
                    f"{agent_exe}. Place AVI_Agent.exe next to AVI.exe."
                )
                return False
            cmd = [str(agent_exe), "start"]
            project_root = exe_dir
        else:
            project_root = Path(__file__).resolve().parent.parent
            agent_file = project_root / "voice" / "livekit_agent.py"
            if not agent_file.exists():
                print(f"A.V.I. LiveKit agent script not found: {agent_file}")
                return False
            cmd = [sys.executable, str(agent_file), "start"]

        env = os.environ.copy()

        # Make sure the agent subprocess sees the current voice + model
        # even if the parent process hasn't reloaded them from .env.
        try:
            import config as _avi_config
            env.setdefault("AVI_VOICE", getattr(_avi_config, "AVI_VOICE", "Arjun"))
            env.setdefault("AVI_LLM_MODEL", getattr(_avi_config, "LLM_MODEL", ""))
            env.setdefault("OPENROUTER_API_KEY", getattr(_avi_config, "OPENROUTER_API_KEY", ""))
            env.setdefault("LIVEKIT_URL", getattr(_avi_config, "LIVEKIT_URL", ""))
            env.setdefault("LIVEKIT_API_KEY", getattr(_avi_config, "LIVEKIT_API_KEY", ""))
            env.setdefault("LIVEKIT_API_SECRET", getattr(_avi_config, "LIVEKIT_API_SECRET", ""))
        except Exception:
            pass

        # Capture agent stdout/stderr to a log file so we can see
        # what the LiveKit worker is doing (job dispatch, model
        # loading, errors). Without this, the agent's output is
        # invisible from the GUI process.
        logs_dir = project_root / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        agent_log_path = logs_dir / "livekit_agent.log"
        agent_log = open(agent_log_path, "ab", buffering=0)

        creationflags = 0
        if os.name == "nt":
            # Separate console is useful for debugging the LiveKit worker.
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=str(project_root),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=agent_log,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
            self._agent_log = agent_log
        except Exception as exc:
            print(f"A.V.I. LiveKit launcher error: {exc}")
            self.process = None
            try:
                agent_log.close()
            except Exception:
                pass
            return False

        # Wait up to ~15s for the agent to register with LiveKit
        # Cloud. Without this, the desktop can join the room before
        # the worker is online, and the project never dispatches a
        # job to it — leaving voice_ready stuck at False.
        deadline = time.monotonic() + 15.0
        registered = False
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                print(
                    "A.V.I. LiveKit agent exited immediately. "
                    f"See logs/livekit_agent.log for details."
                )
                return False
            try:
                with open(agent_log_path, "rb") as fh:
                    fh.seek(0, os.SEEK_END)
                    # only check newly written bytes
                    pos = fh.tell()
                    if pos > 0:
                        fh.seek(0)
                        data = fh.read()
                        if b"registered worker" in data:
                            registered = True
                            break
            except Exception:
                pass
            time.sleep(0.5)

        if registered:
            print(
                "A.V.I. LiveKit voice agent registered with LiveKit Cloud."
            )
        else:
            print(
                "A.V.I. LiveKit voice agent started (registration not "
                "confirmed yet — see logs/livekit_agent.log)."
            )
        return True

    def stop(self):
        if self.process is None:
            return

        if self.process.poll() is None:
            try:
                if os.name == "nt":
                    # Kills the worker along with all child subprocesses it spawned
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                        capture_output=True,
                    )
                else:
                    self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass

        self.process = None
        print("A.V.I. LiveKit voice agent stopped.")
#!/usr/bin/env python3
"""LidKeepAwake - macOS menu bar utility to keep the lid closed laptop awake."""

import atexit
import plistlib
import subprocess
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

try:
    import rumps
except ImportError:
    raise SystemExit("Please install first: pip3 install rumps")

TIMER_OPTIONS = [
    ("5 min", 5),
    ("15 min", 15),
    ("20 min", 20),
    ("25 min", 25),
    ("30 min", 30),
    ("45 min", 45),
    ("1 h", 60),
]


class LidKeepAwake(rumps.App):
    def __init__(self):
        super().__init__("OFF", quit_button=None)

        self.pmset_active = False
        self._authenticated = False
        self.mode = "off"  # off | manual | timed
        self.end_time = None

        self.toggle_item = rumps.MenuItem("Enable", callback=self.on_toggle)
        self.duration_menu = rumps.MenuItem("Keep awake for:")
        for title, _ in TIMER_OPTIONS:
            self.duration_menu.add(rumps.MenuItem(title, callback=self.on_duration))

        self.autostart_item = rumps.MenuItem(
            "Auto-Start at Login: OFF", callback=self.on_autostart
        )
        self.menu = [
            self.toggle_item,
            None,
            self.duration_menu,
            None,
            self.autostart_item,
            None,
            rumps.MenuItem("Quit", callback=self.on_quit),
        ]

    # pmset
    def _run_pmset_silent(self, value: int) -> bool:
        """Set pmset via sudo without password prompt."""
        try:
            result = subprocess.run(
                ["sudo", "-n", "pmset", "-a", "disablesleep", str(value)],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _run_pmset_auth(self, value: int) -> bool:
        """Set pmset with password prompt."""
        script = (
            f'do shell script "pmset -a disablesleep {value}" '
            f'with administrator privileges'
        )
        try:
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, timeout=120
            )
            return result.returncode == 0
        except Exception as exc:
            print(f"pmset error: {exc}")
            return False

    def _start_credential_refresh(self):
        """Refresh sudo timestamp every 2 min so password is never needed again."""
        def _loop():
            while True:
                try:
                    subprocess.run(["sudo", "-n", "-v"], capture_output=True, timeout=5)
                except Exception:
                    pass
                threading.Event().wait(120)
        threading.Thread(target=_loop, daemon=True).start()

    def _activate(self) -> bool:
        if not self.pmset_active:
            if not self._authenticated:
                if not self._run_pmset_silent(1):
                    if not self._run_pmset_auth(1):
                        return False
                    self._authenticated = True
                    self._start_credential_refresh()
                else:
                    self._authenticated = True
                    self._start_credential_refresh()
            self.pmset_active = True
        return True

    def _deactivate(self):
        if self.pmset_active:
            self._run_pmset_silent(0)
            self.pmset_active = False

    # Autostart
    PLIST_NAME = "com.lidkeepawake"

    @property
    def _plist_path(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{self.PLIST_NAME}.plist"

    @property
    def autostart_enabled(self) -> bool:
        return self._plist_path.exists()

    @staticmethod
    def _running_as_bundle() -> bool:
        return getattr(sys, "frozen", False) and Path(sys.executable).suffix == ""

    def _set_autostart(self, enabled: bool):
        if enabled:
            if self._running_as_bundle():
                app_path = Path(sys.executable).resolve().parent.parent.parent
                program_args = ["open", str(app_path)]
            else:
                script = Path(__file__).resolve()
                program_args = ["/usr/bin/env", "python3", str(script)]

            plist = {
                "Label": self.PLIST_NAME,
                "ProgramArguments": program_args,
                "RunAtLoad": True,
                "KeepAlive": False,
                "StandardOutPath": str(Path.home() / ".lidkeepawake.log"),
                "StandardErrorPath": str(Path.home() / ".lidkeepawake.log"),
            }
            try:
                self._plist_path.parent.mkdir(parents=True, exist_ok=True)
                self._plist_path.write_bytes(plistlib.dumps(plist))
            except Exception as exc:
                print(f"Autostart error: {exc}")
        else:
            try:
                subprocess.run(
                    ["launchctl", "unload", str(self._plist_path)],
                    capture_output=True, timeout=10,
                )
                self._plist_path.unlink(missing_ok=True)
            except Exception as exc:
                print(f"Autostart error: {exc}")
        self._refresh_ui()

    # State
    def _set_mode(self, mode: str, minutes: int | None = None):
        self._deactivate()
        self.mode = mode
        if mode == "timed":
            self.end_time = datetime.now() + timedelta(minutes=minutes)
            if not self._activate():
                self.mode = "off"
        elif mode == "manual":
            if not self._activate():
                self.mode = "off"
        self._refresh_ui()

    def _refresh_ui(self):
        if self.mode == "manual":
            self.title = "ON"
            self.toggle_item.title = "Disable"
        elif self.mode == "timed":
            self.title = "TMR"
            self.toggle_item.title = "Disable"
        else:
            self.title = "OFF"
            self.toggle_item.title = "Enable"

        try:
            self.autostart_item.title = (
                "Auto-Start at Login: ON"
                if self.autostart_enabled
                else "Auto-Start at Login: OFF"
            )
        except AttributeError:
            pass

    # Callbacks
    def on_toggle(self, sender):
        if self.mode in ("manual", "timed"):
            self._set_mode("off")
        else:
            self._set_mode("manual")

    def on_duration(self, sender):
        for title, minutes in TIMER_OPTIONS:
            if title == sender.title:
                self._set_mode("timed", minutes)
                return

    def on_autostart(self, sender):
        self._set_autostart(not self.autostart_enabled)

    def on_quit(self, sender):
        self._set_mode("off")
        rumps.quit_application()

    @rumps.timer(2)
    def tick(self, sender):
        if self.mode == "timed" and self.end_time and datetime.now() >= self.end_time:
            self._set_mode("off")


if __name__ == "__main__":
    app = LidKeepAwake()
    atexit.register(app._deactivate)
    app.run()

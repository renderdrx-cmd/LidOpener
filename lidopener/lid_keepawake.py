#!/usr/bin/env python3
"""
LidKeepAwake – macOS menu bar utility

Keeps your MacBook awake with the lid closed, for example so an AI assistant
can keep writing in the background.

Features:
  - Toggle on/off from the menu bar
  - "AI Detection" mode: activates automatically after a few seconds of no
    user input (the AI is probably writing), pauses again once you return.
  - Timer: 5 / 15 / 20 / 25 / 30 / 45 min or 1 h – lid closed, laptop stays
    awake for the chosen duration.
  - Sleep settings are reset when deactivating.

IMPORTANT:
  - Only works reliably while plugged in (Apple Clamshell rule).
  - Requires a one-time admin password prompt to set/reset pmset disablesleep.

Installation:
  pip3 install rumps pyobjc-framework-Quartz
  python3 lid_keepawake.py
"""

import atexit
import os
import plistlib
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import rumps
except ImportError:
    raise SystemExit("Please install first: pip3 install rumps pyobjc-framework-Quartz")

try:
    from Quartz import (
        CGEventSourceSecondsSinceLastEventType,
        kCGEventSourceStateCombinedSessionState,
        kCGAnyInputEventType,
    )

    HAS_QUARTZ = True
except ImportError:
    HAS_QUARTZ = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
IDLE_THRESHOLD_SEC = 15      # seconds without input -> AI is probably writing
GRACE_SEC = 10               # wait this long after user returns before disabling
CHECK_INTERVAL_SEC = 2       # background timer interval

TIMER_OPTIONS = [            # (Label, minutes)
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
        self.mode = "off"             # off | manual | timed | auto
        self.end_time = None          # datetime – end time in timed mode
        self.auto_active_since = None # when auto mode started keeping awake
        self.input_seen_at = None     # timestamp of last user input

        # --- Build menu ---------------------------------------------------
        self.toggle_item = rumps.MenuItem("Enable", callback=self.on_toggle)
        self.auto_item = rumps.MenuItem(
            "AI Detection (automatic)", callback=self.on_auto_mode
        )
        self.duration_menu = rumps.MenuItem("Keep awake for:")
        for title, _ in TIMER_OPTIONS:
            sub = rumps.MenuItem(title, callback=self.on_duration)
            self.duration_menu.add(sub)

        self.autostart_item = rumps.MenuItem(
            "Auto-Start at Login: OFF", callback=self.on_autostart
        )
        self.menu = [
            self.toggle_item,
            None,
            self.auto_item,
            self.duration_menu,
            None,
            self.autostart_item,
            None,
            rumps.MenuItem("Quit", callback=self.on_quit),
        ]

    # ------------------------------------------------------------------ pmset
    def _run_pmset(self, value: int) -> bool:
        """Set pmset disablesleep with admin privileges (one-time password
        prompt via the macOS dialog)."""
        script = f'do shell script "pmset -a disablesleep {value}" with administrator privileges'
        try:
            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, timeout=120
            )
        except Exception as exc:  # noqa: BLE001
            print(f"pmset error: {exc}")
            return False
        if result.returncode != 0:
            print(f"pmset failed: {result.stderr.strip()}")
            return False
        return True

    def _activate(self) -> bool:
        if not self.pmset_active:
            if not self._run_pmset(1):
                return False
            self.pmset_active = True
        return True

    def _deactivate(self):
        if self.pmset_active:
            self._run_pmset(0)
            self.pmset_active = False

    # --------------------------------------------------------------- Autostart
    PLIST_NAME = "com.lidkeepawake"

    @property
    def _plist_path(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{self.PLIST_NAME}.plist"

    @property
    def autostart_enabled(self) -> bool:
        return self._plist_path.exists()

    @staticmethod
    def _running_as_bundle() -> bool:
        """True if running as a .app bundle (py2app)."""
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

    # ------------------------------------------------------------ State logic
    def _set_mode(self, mode: str, minutes: int | None = None):
        self._deactivate()
        self.mode = mode
        self.auto_active_since = None
        if mode == "timed":
            self.end_time = datetime.now() + timedelta(minutes=minutes)
            if not self._activate():
                self.mode = "off"
        elif mode == "manual":
            if not self._activate():
                self.mode = "off"
        elif mode == "auto":
            self.end_time = None
        self._refresh_ui()

    # ------------------------------------------------------------------ UI
    def _refresh_ui(self):
        if self.mode == "manual":
            self.title = "ON"
            self.toggle_item.title = "Disable"
        elif self.mode == "timed":
            self.title = "TMR"
            self.toggle_item.title = "Disable"
        elif self.mode == "auto" and self.auto_active_since:
            self.title = "AI!"
            self.toggle_item.title = "Disable"
        elif self.mode == "auto":
            self.title = "AI"
            self.toggle_item.title = "Enable"
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

    # ------------------------------------------------------------------ Callbacks
    def on_toggle(self, sender):
        if self.mode in ("manual", "timed") or (
            self.mode == "auto" and self.auto_active_since
        ):
            self._set_mode("off")
        else:
            self._set_mode("manual")

    def on_auto_mode(self, sender):
        if self.mode == "auto":
            self._set_mode("off")
        else:
            self._set_mode("auto")

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

    # ------------------------------------------------------------------ Tick
    @rumps.timer(CHECK_INTERVAL_SEC)
    def tick(self, sender):
        now = datetime.now()

        if self.mode == "timed" and self.end_time and now >= self.end_time:
            self._set_mode("off")
            return

        if self.mode != "auto" or not HAS_QUARTZ:
            return

        try:
            idle_sec = CGEventSourceSecondsSinceLastEventType(
                kCGEventSourceStateCombinedSessionState, kCGAnyInputEventType
            )
        except Exception:
            return

        if idle_sec < IDLE_THRESHOLD_SEC:
            if self.input_seen_at is None:
                self.input_seen_at = now
            if self.auto_active_since and (now - self.input_seen_at).total_seconds() >= GRACE_SEC:
                self.auto_active_since = None
                self.input_seen_at = None
                self._deactivate()
                self._refresh_ui()
            elif self.auto_active_since is None:
                self._refresh_ui()
        else:
            self.input_seen_at = None
            if self.auto_active_since is None:
                if self._activate():
                    self.auto_active_since = now
                    self._refresh_ui()


if __name__ == "__main__":
    app = LidKeepAwake()
    atexit.register(app._deactivate)
    app.run()

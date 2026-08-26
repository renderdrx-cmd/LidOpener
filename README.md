# LidKeepAwake

A macOS menu bar utility that keeps your MacBook **awake with the lid closed** —
for example so an AI assistant (ChatGPT, Claude, etc.) can keep working in the background.

## Requirements

**Python 3.10+** and the following packages (install once):

```bash
pip3 install rumps
```

## Usage

```bash
python3 lid_keepawake.py
```

The app appears as a text label in the menu bar (OFF, ON, or TMR). On first launch macOS will ask for your **admin password** (required for `pmset`). You only need to enter it once — the password is cached in the background so you never have to type it again.

## Modes

| Menu item | Description |
|---|---|
| **Enable / Disable** | Manually toggle keep-awake on or off |
| **Keep awake for a duration** | Timer: 5 / 15 / 20 / 25 / 30 / 45 min or 1 h |

## Important

- **Use while plugged in!** Running on battery will drain it quickly.
- The app sets `pmset disablesleep 1`. It is automatically reset on exit
  (also on crash via `atexit`).
- **Only one password prompt:** You enter your admin password once on the very first launch. It is cached in the background and never asked again (until a system restart).
- Compatible with Apple Silicon and Intel Macs.

## Uninstallation

Delete the script — the sleep setting is automatically reset on exit.
To verify:

```bash
pmset -g | grep disablesleep   # should be 0
```

## License

[MIT](LICENSE)

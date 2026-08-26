from setuptools import setup

APP = ["lid_keepawake.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "iconfile": None,
    "plist": {
        "CFBundleName": "LidKeepAwake",
        "CFBundleDisplayName": "LidKeepAwake",
        "CFBundleIdentifier": "com.lidkeepawake",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "LSUIElement": True,
    },
    "packages": ["rumps"],
    "excludes": ["tkinter", "_tkinter", "Tkinter", "Tcl", "Tk"],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)

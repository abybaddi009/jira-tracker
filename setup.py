import os
import sys

from cx_Freeze import Executable, setup


# Helper function to get all files from static directory
def get_static_files():
    static_files = []
    for root, dirs, files in os.walk("static"):
        for file in files:
            source = os.path.join(root, file)
            # Preserve the directory structure in the build
            destination = source  # This will maintain the same path in the build
            static_files.append((source, destination))
    return static_files


# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {
    "packages": [
        "os",
        "sys",
        "PyQt6",
        "sqlalchemy",
        "environs",
        "plyer",
        "requests",
        "json",
        "urllib",
        "datetime",
        "logging",
    ],
    "excludes": [],
    "include_files": [*get_static_files(), "tasks_new.json", ".env.example"],
    "includes": ["jira_integration"],  # Include the jira_integration module
    "build_exe": "dist",  # Output directory
    "optimize": 2,
    "include_msvcr": True,  # Include Microsoft Visual C++ runtime
}

# GUI applications require a different base on Windows
base = None
if sys.platform == "win32":
    base = "Win32GUI"
else:
    build_exe_options["packages"].append("dbus")

setup(
    name="TimeTracker",
    version="0.1",
    description="Time Tracking Application",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "main.py",
            base=base,
            icon="static/icon.png",
            target_name="TimeTracker",
            shortcut_name="TimeTracker",
            shortcut_dir="DesktopFolder",
        )
    ],
)

"""Local machine controls: active-window actions and a system report.

Deliberately small and explicit — every action here is triggered by a direct
owner command, never autonomously by the LLM.
"""


def window_action(action: str) -> str:
    """maximize | minimize | restore the currently focused window (Windows)."""
    try:
        import pygetwindow
    except ImportError as exc:
        raise RuntimeError("Window control needs pygetwindow: pip install pygetwindow") from exc

    win = pygetwindow.getActiveWindow()
    if win is None:
        raise RuntimeError("No active window detected.")
    title = (win.title or "window").strip()[:60]
    if action == "maximize":
        win.maximize()
    elif action == "minimize":
        win.minimize()
    elif action == "restore":
        win.restore()
    else:
        raise RuntimeError(f"Unknown window action: {action}")
    return title


def system_status() -> dict:
    try:
        import psutil
    except ImportError as exc:
        raise RuntimeError("System report needs psutil: pip install psutil") from exc

    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    battery = None
    if hasattr(psutil, "sensors_battery"):
        try:
            b = psutil.sensors_battery()
            if b:
                battery = {"percent": round(b.percent), "plugged": bool(b.power_plugged)}
        except Exception:
            pass
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.3),
        "ram_percent": vm.percent,
        "ram_used_gb": round(vm.used / 1e9, 1),
        "ram_total_gb": round(vm.total / 1e9, 1),
        "disk_percent": disk.percent,
        "battery": battery,
    }

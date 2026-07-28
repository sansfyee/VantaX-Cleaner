import os
import re
import sys
import glob
import time
import shutil
import ctypes
import platform
import threading
import traceback
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum, auto
from typing import List, Dict, Optional, Tuple, Set, Callable, Any
from dataclasses import dataclass

import customtkinter as ctk
from tkinter import messagebox

# ====================== CONSTANTS & CONFIGURATION ======================

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# UI palette
ACCENT       = "#D60000"
ACCENT_HOVER = "#D60000"
BG_MAIN      = "#000000"
BG_CARD      = "#303030"
BG_PANEL     = "#303030"
BG_SEGBTN    = "#303030"

MAX_LOG_LINES    = 500
MAX_OUTPUT_LINES = 1000

CHOCO_INSTALL_URL    = "https://community.chocolatey.org/install.ps1"
CHOCO_INSTALL_SHA256 = "4324AB50A3CF5F560C294F3924B5BC5B1ECC6E82140CB09B7D4154C6277868EB"
EDGE_INSTALLER_URL   = (
    "https://go.microsoft.com/fwlink/?linkid=2109047&Channel=Stable"
    "&language=en&Consent=1"
)

# Packages where checksum verification is known to fail
CHECKSUM_SKIP_ALLOWLIST: Set[str] = {"winrar", "etcher"}

# Regex for basic registry path/value validation
_REG_PATH_RE = re.compile(r'^[A-Za-z0-9\\_ :\-\.]+$')
_REG_NAME_RE = re.compile(r'^[A-Za-z0-9_\- ]+$')


class AppState(Enum):
    IDLE       = auto()
    RUNNING    = auto()
    RESTORING  = auto()


class AdvOption(Enum):
    """Advanced system optimisation options."""
    COPILOT    = auto()
    EDGE       = auto()
    ONEDRIVE   = auto()
    TELEMETRY  = auto()
    WUPDATE    = auto()
    DEFENDER   = auto()
    HIBERFIL   = auto()
    SUPERFETCH = auto()
    PREFETCH   = auto()
    TMPCLEAN   = auto()
    DNS        = auto()
    GAMINGMODE = auto()


REG_POLICIES: Dict[str, str] = {
    "COPILOT":    r"SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot",
    "ONEDRIVE":   r"SOFTWARE\Policies\Microsoft\Windows\OneDrive",
    "TELEMETRY":  r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
    "WUPDATE":    r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU",
    "GAMING":     r"SOFTWARE\Microsoft\GameBar",
}


def get_windows_version() -> Tuple[int, int, int]:
    """Return (major, minor, build) of the running Windows."""
    parts = platform.version().split(".")
    return int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0


IS_WIN11 = get_windows_version()[2] >= 22000


# ====================== APPLICATION CATALOGUE ======================
APPS_TO_INSTALL: Dict[str, Dict[str, str]] = {
    "🌐 Browsers": {
        "Google Chrome":          "googlechrome",
        "Mozilla Firefox":        "firefox",
        "Brave Browser":          "brave",
        "Opera":                  "opera",
        "Opera GX":               "opera-gx",
        "Vivaldi":                "vivaldi",
        "Tor Browser":            "tor-browser",
    },
    "🛠️ Essential Tools": {
        "7-Zip":                  "7zip.install",
        "WinRAR":                 "winrar",
        "VLC Media Player":       "vlc",
        "Notepad++":              "notepadplusplus.install",
        "PowerToys":              "powertoys",
        "Everything":             "everything.install",
        "TreeSize Free":          "treesizefree",
        "WinDirStat":             "windirstat",
        "CrystalDiskInfo":        "crystaldiskinfo",
        "HWiNFO":                 "hwinfo",
        "CPU-Z":                  "cpu-z",
        "GPU-Z":                  "gpu-z",
        "Speccy":                 "speccy",
        "Rufus":                  "rufus",
        "Ventoy":                 "ventoy",
        "Balena Etcher":          "etcher",
        "WizTree":                "wiztree",
    },
    "💬 Communication": {
        "Discord":                "discord",
        "WhatsApp":               "whatsapp",
        "Telegram":               "telegram.install",
        "Signal":                 "signal",
        "Slack":                  "slack",
        "Zoom":                   "zoom",
        "Microsoft Teams":        "microsoft-teams",
        "Skype":                  "skype",
        "Viber":                  "viber",
    },
    "🎵 Media & Entertainment": {
        "Spotify":                "spotify",
        "Steam":                  "steam",
        "Epic Games Launcher":    "epicgameslauncher",
        "GOG Galaxy":             "goggalaxy",
        "Ubisoft Connect":        "ubisoft-connect",
        "EA App":                 "ea-app",
        "qBittorrent":            "qbittorrent",
        "OBS Studio":             "obs-studio",
        "Handbrake":              "handbrake",
        "MPC-HC":                 "mpc-hc",
        "AIMP":                   "aimp",
        "foobar2000":             "foobar2000",
        "Kodi":                   "kodi",
        "Plex Media Server":      "plex",
    },
    "💻 Development": {
        "VS Code":                "vscode",
        "Git":                    "git.install",
        "Python 3":               "python3",
        "Node.js LTS":            "nodejs-lts",
        "Java JDK 21":            "openjdk",
        "Docker Desktop":         "docker-desktop",
        "Postman":                "postman",
        "HeidiSQL":               "heidisql",
        "Windows Terminal":       "microsoft-windows-terminal",
        "WinSCP":                 "winscp.install",
        "PuTTY":                  "putty.install",
        "Notepad3":               "notepad3",
        "Vim":                    "vim",
        "NASM":                   "nasm",
        "CMake":                  "cmake",
    },
    "🎨 Graphics & Design": {
        "GIMP":                   "gimp",
        "Inkscape":               "inkscape",
        "Krita":                  "krita",
        "Blender":                "blender",
        "paint.net":              "paint.net",
        "IrfanView":              "irfanview",
        "ShareX":                 "sharex",
        "Greenshot":              "greenshot",
    },
    "📄 Office": {
        "LibreOffice":            "libreoffice",
        "Foxit PDF Reader":       "foxitreader",
        "Adobe Acrobat Reader":   "adobereader",
        "SumatraPDF":             "sumatrapdf",
        "Obsidian":               "obsidian",
        "Notion":                 "notion",
        "Joplin":                 "joplin",
    },
    "🔒 Security & Network": {
        "Malwarebytes":           "malwarebytes",
        "Bitwarden":              "bitwarden",
        "KeePassXC":              "keepassxc",
        "ProtonVPN":              "protonvpn",
        "Wireshark":              "wireshark",
        "Nmap":                   "nmap",
        "Advanced IP Scanner":    "advanced-ip-scanner",
        "TeamViewer":             "teamviewer",
        "AnyDesk":                "anydesk.install",
    },
}


# ====================== UTILITIES ======================

@dataclass
class InstallResult:
    """Result of a package installation attempt."""
    package: str
    success: bool
    error_msg: str = ""


class Logger:
    """Thread-safe logger that forwards messages to the UI callback."""
    def __init__(self, log_callback: Callable[[str], None]):
        self._callback = log_callback

    def info(self, msg: str) -> None:    self._callback(f"[INFO] {msg}")
    def warning(self, msg: str) -> None: self._callback(f"[WARN] {msg}")
    def error(self, msg: str) -> None:   self._callback(f"[ERROR] {msg}")


class ProcessRunner:
    """
    Robust, cancellable process runner with output capture.
    """
    @staticmethod
    def run_powershell(command: str,
                       timeout: int = 60,
                       stop_event: Optional[threading.Event] = None,
                       extra_env: Optional[Dict[str, str]] = None) -> Tuple[int, str, str]:
        if platform.system() != "Windows":
            return -1, "", "Non-Windows system"
        full_cmd = (
            "$OutputEncoding = [System.Text.Encoding]::UTF8; "
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
            + command
        )
        args = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-NonInteractive", "-Command", full_cmd]
        return ProcessRunner._run(args, timeout, stop_event, extra_env)

    @staticmethod
    def _run(args: List[str],
             timeout: int,
             stop_event: Optional[threading.Event] = None,
             extra_env: Optional[Dict[str, str]] = None) -> Tuple[int, str, str]:
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env,
                creationflags=creationflags
            )
        except Exception as e:
            return -2, "", str(e)

        stdout_lines: List[str] = []
        stderr_lines: List[str] = []

        def drain(stream, collector):
            try:
                for line in iter(stream.readline, ''):
                    if len(collector) < MAX_OUTPUT_LINES:
                        collector.append(line)
            except Exception:
                pass
            finally:
                try:
                    stream.close()
                except Exception:
                    pass

        t1 = threading.Thread(target=drain, args=(proc.stdout, stdout_lines), daemon=True)
        t2 = threading.Thread(target=drain, args=(proc.stderr, stderr_lines), daemon=True)
        t1.start(); t2.start()

        start = time.monotonic()
        while True:
            try:
                proc.wait(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                if stop_event and stop_event.is_set():
                    _kill(proc)
                    return -3, "", "Cancelled"
                if time.monotonic() - start > timeout:
                    _kill(proc)
                    return -4, "", "Timeout"

        t1.join(2); t2.join(2)
        return proc.returncode, ''.join(stdout_lines), ''.join(stderr_lines)


def _kill(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# ====================== SYSTEM MANAGER ======================

class SystemManager:
    """Low‑level Windows operations (registry, choco detection, admin check)."""

    @staticmethod
    def is_admin() -> bool:
        if platform.system() != "Windows":
            return False
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    @staticmethod
    def _validate_registry_inputs(key_path: str, value_name: str) -> None:
        if not _REG_PATH_RE.match(key_path):
            raise ValueError(f"Invalid registry path: {key_path!r}")
        if not _REG_NAME_RE.match(value_name):
            raise ValueError(f"Invalid value name: {value_name!r}")

    @staticmethod
    def _normalize_ps_path(key_path: str) -> str:
        if ":\\" in key_path:
            return key_path
        for hive in ("HKLM", "HKCU", "HKCR", "HKU", "HKCC"):
            if key_path.upper().startswith(hive + "\\"):
                return hive + ":\\" + key_path[len(hive) + 1:]
        return "HKLM:\\" + key_path

    @staticmethod
    def set_registry_policy(key_path: str,
                            value_name: str,
                            value_data: Any,
                            value_type: str = "DWORD",
                            stop_event: Optional[threading.Event] = None) -> bool:
        if not SystemManager.is_admin():
            return False
        try:
            SystemManager._validate_registry_inputs(key_path, value_name)
        except ValueError:
            return False

        type_map = {"DWORD": "DWord", "QWORD": "QWord", "STRING": "String"}
        prop_type = type_map.get(value_type.upper(), "DWord")
        ps_path = SystemManager._normalize_ps_path(key_path)
        safe_path = ps_path.replace("'", "''")
        safe_name = value_name.replace("'", "''")
        safe_type = prop_type.replace("'", "''")

        env = {"__REG_VALUE": str(value_data)}
        ps_cmd = f"""
        $path  = '{safe_path}'
        $vname = '{safe_name}'
        $vdata = $env:__REG_VALUE
        $vtype = '{safe_type}'
        try {{
            if (-not (Test-Path $path)) {{ New-Item -Path $path -Force | Out-Null }}
            Set-ItemProperty -Path $path -Name $vname -Value $vdata -Type $vtype -Force
            $true
        }} catch {{ $false; Write-Error $_.Exception.Message }}
        """
        code, _, _ = ProcessRunner.run_powershell(ps_cmd, timeout=30,
                                                  stop_event=stop_event, extra_env=env)
        return code == 0

    @staticmethod
    def remove_registry_value(key_path: str,
                              value_name: str,
                              stop_event: Optional[threading.Event] = None) -> bool:
        if not SystemManager.is_admin():
            return False
        try:
            SystemManager._validate_registry_inputs(key_path, value_name)
        except ValueError:
            return False
        ps_path = SystemManager._normalize_ps_path(key_path)
        safe_path = ps_path.replace("'", "''")
        safe_name = value_name.replace("'", "''")
        cmd = f"Remove-ItemProperty -Path '{safe_path}' -Name '{safe_name}' -ErrorAction SilentlyContinue"
        code, _, _ = ProcessRunner.run_powershell(cmd, timeout=20, stop_event=stop_event)
        return code == 0

    @staticmethod
    def find_choco() -> Optional[str]:
        candidates = [
            shutil.which("choco.exe"),
            os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"),
                         "chocolatey", "bin", "choco.exe"),
            os.path.join(os.environ.get("ALLUSERSPROFILE", r"C:\ProgramData"),
                         "chocolatey", "bin", "choco.exe"),
        ]
        for path in candidates:
            if path and os.path.isfile(path):
                return path
        return None


# ====================== PACKAGE INSTALLER ======================

class PackageInstaller:
    """Installs Chocolatey packages with retries and cancellation."""

    def __init__(self, choco_path: str, stop_event: threading.Event, logger: Logger):
        self.choco_path = choco_path
        self.stop_event = stop_event
        self.logger = logger
        self._current_proc: Optional[subprocess.Popen] = None
        self._proc_lock = threading.Lock()

    def install(self, package: str, retry: int = 2) -> InstallResult:
        cmd = [self.choco_path, "install", package, "-y", "--limit-output", "--no-progress"]
        if package in CHECKSUM_SKIP_ALLOWLIST:
            cmd.append("--ignore-checksums")
            self.logger.warning(f"{package}: checksum skipped (known issue)")

        for attempt in range(retry + 1):
            if self.stop_event.is_set():
                return InstallResult(package, False, "Cancelled")
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
                with self._proc_lock:
                    self._current_proc = proc

                stdout_lines, stderr_lines = [], []
                def _drain(stream, collector):
                    try:
                        for line in iter(stream.readline, ''):
                            if len(collector) < MAX_OUTPUT_LINES:
                                collector.append(line)
                    except Exception:
                        pass
                    finally:
                        try:
                            stream.close()
                        except Exception:
                            pass

                t1 = threading.Thread(target=_drain, args=(proc.stdout, stdout_lines), daemon=True)
                t2 = threading.Thread(target=_drain, args=(proc.stderr, stderr_lines), daemon=True)
                t1.start(); t2.start()

                start = time.monotonic()
                while True:
                    try:
                        proc.wait(timeout=0.25)
                        break
                    except subprocess.TimeoutExpired:
                        if self.stop_event.is_set():
                            _kill(proc)
                            return InstallResult(package, False, "Cancelled")
                        if time.monotonic() - start > 600:
                            _kill(proc)
                            return InstallResult(package, False, "Timeout")

                t1.join(2); t2.join(2)

                if proc.returncode == 0:
                    return InstallResult(package, True)

                err_txt = f"RC={proc.returncode}"
                stderr_str = ''.join(stderr_lines)
                if stderr_str.strip():
                    err_txt += " | " + stderr_str.strip()[:200]

                if attempt < retry:
                    self.logger.warning(f"{package}: retry {attempt+1}/{retry} ...")
                    time.sleep(3)
                    continue
                return InstallResult(package, False, err_txt)

            except Exception as exc:
                self.logger.error(f"Install error ({package}): {exc}")
                if attempt < retry:
                    time.sleep(3)
                    continue
                return InstallResult(package, False, str(exc))
            finally:
                with self._proc_lock:
                    self._current_proc = None

        return InstallResult(package, False, "Unknown error")

    def stop(self) -> None:
        with self._proc_lock:
            proc = self._current_proc
        if proc and proc.poll() is None:
            _kill(proc)


# ====================== SYSTEM OPTIMISER ======================

class SystemOptimizer:
    """Implements all system tweaks (Edge, telemetry, services, etc.)."""

    # ------------------ Edge Management ------------------
    @staticmethod
    def remove_edge(stop_event: threading.Event, logger: Logger) -> bool:
        logger.info("Removing Microsoft Edge completely...")
        if stop_event.is_set():
            return False

        for exe in ("msedge.exe", "MicrosoftEdgeUpdate.exe"):
            try:
                subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True, timeout=10)
            except Exception:
                pass

        bitness = "x64" if platform.machine().endswith('64') else "x86"
        setup_name = f"setup.{bitness}.exe"
        try:
            base = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(os.path.abspath(__file__))
        except Exception:
            base = os.getcwd()
        setup_path = os.path.join(base, setup_name)

        if os.path.exists(setup_path):
            logger.info("Running official Edge uninstaller...")
            for extra in [[], ["--msedgewebview"]]:
                if stop_event.is_set():
                    return False
                try:
                    p = subprocess.Popen(
                        [setup_path, "--uninstall", "--system-level", "--force-uninstall"] + extra,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    try:
                        p.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        p.terminate()
                except Exception:
                    pass

        patterns = [
            r"C:\Program Files (x86)\Microsoft\Edge",
            r"C:\Program Files (x86)\Microsoft\EdgeWebView",
            r"C:\Program Files\Microsoft\Edge",
            r"C:\Program Files\Microsoft\EdgeUpdate",
            r"C:\Windows\SystemApps\Microsoft.MicrosoftEdge*",
        ]
        for pat in patterns:
            if stop_event.is_set():
                return False
            paths = glob.glob(pat) or ([pat] if os.path.exists(pat) else [])
            for p in paths:
                logger.info(f"Deleting: {p}")
                for cmd in [
                    ["takeown", "/F", p, "/R", "/D", "Y"],
                    ["icacls", p, "/grant", "Administrators:F", "/T"],
                    ["cmd", "/c", "rd", "/s", "/q", p],
                ]:
                    try:
                        subprocess.run(cmd, capture_output=True, timeout=30)
                    except Exception:
                        pass

        logger.info("Edge removal completed.")
        return True

    @staticmethod
    def restore_edge(stop_event: threading.Event, logger: Logger) -> bool:
        logger.info("Downloading and reinstalling Microsoft Edge...")
        ps = f"""
        $url    = '{EDGE_INSTALLER_URL}'
        $output = Join-Path $env:TEMP 'MicrosoftEdgeSetup.exe'
        try {{
            (New-Object System.Net.WebClient).DownloadFile($url, $output)
            $sig = Get-AuthenticodeSignature $output
            if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notlike '*Microsoft*') {{
                throw "Authenticode verification failed: $($sig.Status)"
            }}
            $proc = Start-Process $output -ArgumentList '/silent','/install' -Wait -PassThru
            if ($proc.ExitCode -ne 0) {{ throw "Installer exit code: $($proc.ExitCode)" }}
            'SUCCESS'
        }} catch {{
            Write-Error $_.Exception.Message
        }} finally {{
            if (Test-Path $output) {{ Remove-Item $output -Force -ErrorAction SilentlyContinue }}
        }}
        """
        code, out, err = ProcessRunner.run_powershell(ps, timeout=300, stop_event=stop_event)
        if code != 0:
            logger.error(f"Edge restore failed: {err[:300]}")
            return False
        if "SUCCESS" not in out:
            logger.warning("Edge installer did not report SUCCESS.")
            return False
        return True

    # ------------------ Copilot ------------------
    @staticmethod
    def disable_copilot(stop_event=None, logger=None) -> bool:
        if not IS_WIN11:
            if logger:
                logger.info("Copilot policy skipped (Windows 10 detected)")
            return True
        ok = True
        for hive in (r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot",
                     r"HKCU\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot"):
            if stop_event and stop_event.is_set():
                return False
            ok &= SystemManager.set_registry_policy(hive, "TurnOffWindowsCopilot", 1, "DWORD", stop_event)
        return ok

    @staticmethod
    def restore_copilot(stop_event=None) -> bool:
        ok = True
        for hive in (r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot",
                     r"HKCU\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot"):
            if stop_event and stop_event.is_set():
                return False
            ok &= SystemManager.remove_registry_value(hive, "TurnOffWindowsCopilot", stop_event)
        return ok

    # ------------------ OneDrive ------------------
    @staticmethod
    def disable_onedrive(stop_event: threading.Event, logger: Logger) -> bool:
        if stop_event.is_set():
            return False
        try:
            subprocess.run(["taskkill", "/F", "/IM", "OneDrive.exe"], capture_output=True, timeout=10)
        except Exception:
            pass
        ProcessRunner.run_powershell(
            r'Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" '
            r'-Name "OneDrive" -ErrorAction SilentlyContinue',
            timeout=20, stop_event=stop_event)
        return SystemManager.set_registry_policy(
            REG_POLICIES["ONEDRIVE"], "DisableFileSyncNGSC", 1, "DWORD", stop_event)

    @staticmethod
    def restore_onedrive(stop_event=None) -> bool:
        return SystemManager.remove_registry_value(REG_POLICIES["ONEDRIVE"], "DisableFileSyncNGSC", stop_event)

    # ------------------ Telemetry ------------------
    @staticmethod
    def disable_telemetry(stop_event=None) -> bool:
        if stop_event and stop_event.is_set():
            return False
        ok = SystemManager.set_registry_policy(REG_POLICIES["TELEMETRY"], "AllowTelemetry", 0, "DWORD", stop_event)
        if not (stop_event and stop_event.is_set()):
            ProcessRunner.run_powershell(
                'Stop-Service -Name "DiagTrack" -Force -ErrorAction SilentlyContinue; '
                'Set-Service -Name "DiagTrack" -StartupType Disabled -ErrorAction SilentlyContinue',
                timeout=20, stop_event=stop_event)
        return ok

    @staticmethod
    def restore_telemetry(stop_event=None) -> bool:
        SystemManager.remove_registry_value(REG_POLICIES["TELEMETRY"], "AllowTelemetry", stop_event)
        if not (stop_event and stop_event.is_set()):
            ProcessRunner.run_powershell(
                'Set-Service -Name "DiagTrack" -StartupType Automatic -ErrorAction SilentlyContinue; '
                'Start-Service -Name "DiagTrack" -ErrorAction SilentlyContinue',
                timeout=20, stop_event=stop_event)
        return True

    # ------------------ Windows Update ------------------
    @staticmethod
    def disable_windows_update(stop_event=None, logger=None) -> bool:
        if logger:
            logger.info("Disabling Windows Update...")
        if stop_event and stop_event.is_set():
            return False
        ok = SystemManager.set_registry_policy(REG_POLICIES["WUPDATE"], "NoAutoUpdate", 1, "DWORD", stop_event)
        if not (stop_event and stop_event.is_set()):
            ProcessRunner.run_powershell(
                'Stop-Service -Name "wuauserv" -Force -ErrorAction SilentlyContinue; '
                'Set-Service -Name "wuauserv" -StartupType Disabled -ErrorAction SilentlyContinue',
                timeout=20, stop_event=stop_event)
            SystemOptimizer._schedule_update_reminder(stop_event)
        return ok

    @staticmethod
    def _schedule_update_reminder(stop_event=None) -> None:
        ps = (
            "$action = New-ScheduledTaskAction -Execute 'powershell.exe' "
            "-Argument '-WindowStyle Hidden -Command \""
            "Add-Type -AssemblyName System.Windows.Forms; "
            "[System.Windows.Forms.MessageBox]::Show("
            "'Windows Update has been disabled for 30 days by Vantax. Consider re-enabling it.', "
            "'Vantax Security Alert')\"'; "
            "$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddDays(30); "
            "Register-ScheduledTask -TaskName 'VantaxUpdateReminder' -Action $action "
            "-Trigger $trigger -Force -ErrorAction SilentlyContinue"
        )
        ProcessRunner.run_powershell(ps, timeout=30, stop_event=stop_event)

    @staticmethod
    def restore_windows_update(stop_event=None, logger=None) -> bool:
        if logger:
            logger.info("Restoring Windows Update to defaults...")
        SystemManager.remove_registry_value(REG_POLICIES["WUPDATE"], "NoAutoUpdate", stop_event)
        if not (stop_event and stop_event.is_set()):
            ProcessRunner.run_powershell(
                'Set-Service -Name "wuauserv" -StartupType Automatic -ErrorAction SilentlyContinue; '
                'Start-Service -Name "wuauserv" -ErrorAction SilentlyContinue',
                timeout=20, stop_event=stop_event)
        return True

    # ------------------ Hibernation ------------------
    @staticmethod
    def disable_hibernation(stop_event=None, logger=None) -> bool:
        if logger:
            logger.info("Disabling hibernation...")
        if stop_event and stop_event.is_set():
            return False
        code, _, _ = ProcessRunner.run_powershell('powercfg -h off', timeout=20, stop_event=stop_event)
        return code == 0

    @staticmethod
    def restore_hibernation(stop_event=None, logger=None) -> bool:
        if logger:
            logger.info("Enabling hibernation...")
        if stop_event and stop_event.is_set():
            return False
        code, _, _ = ProcessRunner.run_powershell('powercfg -h on', timeout=20, stop_event=stop_event)
        return code == 0

    # ------------------ Superfetch ------------------
    @staticmethod
    def disable_superfetch(stop_event=None, logger=None) -> bool:
        if logger:
            logger.info("Disabling SuperFetch/SysMain...")
        if stop_event and stop_event.is_set():
            return False
        code, _, _ = ProcessRunner.run_powershell(
            'Stop-Service -Name "SysMain" -Force -ErrorAction SilentlyContinue; '
            'Set-Service -Name "SysMain" -StartupType Disabled -ErrorAction SilentlyContinue',
            timeout=20, stop_event=stop_event)
        return code == 0

    @staticmethod
    def restore_superfetch(stop_event=None, logger=None) -> bool:
        if logger:
            logger.info("Restoring SuperFetch/SysMain...")
        if stop_event and stop_event.is_set():
            return False
        code, _, _ = ProcessRunner.run_powershell(
            'Set-Service -Name "SysMain" -StartupType Automatic -ErrorAction Stop; '
            'Start-Service -Name "SysMain" -ErrorAction Stop',
            timeout=20, stop_event=stop_event)
        return code == 0

    # ------------------ Prefetch ------------------
    @staticmethod
    def disable_prefetch(stop_event=None, logger=None) -> bool:
        if logger:
            logger.info("Disabling Prefetch...")
        if stop_event and stop_event.is_set():
            return False
        return SystemManager.set_registry_policy(
            r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters",
            "EnablePrefetcher", 0, "DWORD", stop_event)

    @staticmethod
    def restore_prefetch(stop_event=None, logger=None) -> bool:
        if logger:
            logger.info("Restoring Prefetch (default = 3)...")
        if stop_event and stop_event.is_set():
            return False
        return SystemManager.set_registry_policy(
            r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters",
            "EnablePrefetcher", 3, "DWORD", stop_event)

    # ------------------ Temp cleanup ------------------
    @staticmethod
    def clean_temp(stop_event=None, logger=None) -> bool:
        if logger:
            logger.info("Cleaning temporary files...")
        dirs = [
            os.environ.get("TEMP", ""),
            os.environ.get("TMP", ""),
            r"C:\Windows\Temp",
            r"C:\Windows\Prefetch",
        ]
        for d in dirs:
            if not d or not os.path.isdir(d):
                continue
            try:
                items = os.listdir(d)
            except Exception:
                continue
            for item in items:
                if stop_event and stop_event.is_set():
                    return False
                full = os.path.join(d, item)
                try:
                    if os.path.isfile(full) or os.path.islink(full):
                        os.unlink(full)
                    elif os.path.isdir(full):
                        shutil.rmtree(full, ignore_errors=True)
                except Exception:
                    pass
        if logger:
            logger.info("Temp cleanup finished.")
        return True

    # ------------------ DNS ------------------
    @staticmethod
    def set_fast_dns(stop_event=None, logger=None) -> bool:
        if logger:
            logger.info("Setting Cloudflare DNS (1.1.1.1 / 1.0.0.1)...")
        if stop_event and stop_event.is_set():
            return False
        ps = (
            '$adapters = Get-NetAdapter | Where-Object {$_.Status -eq "Up"}; '
            'foreach ($a in $adapters) { '
            '  Set-DnsClientServerAddress -InterfaceIndex $a.InterfaceIndex '
            '    -ServerAddresses ("1.1.1.1","1.0.0.1") -ErrorAction SilentlyContinue '
            '}'
        )
        code, _, _ = ProcessRunner.run_powershell(ps, timeout=30, stop_event=stop_event)
        return code == 0

    @staticmethod
    def restore_dns(stop_event=None, logger=None) -> bool:
        if logger:
            logger.info("Resetting DNS to automatic...")
        if stop_event and stop_event.is_set():
            return False
        ps = (
            '$adapters = Get-NetAdapter | Where-Object {$_.Status -eq "Up"}; '
            'foreach ($a in $adapters) { '
            '  Set-DnsClientServerAddress -InterfaceIndex $a.InterfaceIndex '
            '    -ResetServerAddresses -ErrorAction SilentlyContinue '
            '}'
        )
        code, _, _ = ProcessRunner.run_powershell(ps, timeout=30, stop_event=stop_event)
        return code == 0

    # ------------------ Gaming mode ------------------
    @staticmethod
    def enable_gaming_mode(stop_event=None, logger=None) -> bool:
        if logger:
            logger.info("Enabling Gaming Mode + disabling Game DVR...")
        if stop_event and stop_event.is_set():
            return False
        ok = True
        ok &= SystemManager.set_registry_policy(
            r"HKCU\SOFTWARE\Microsoft\GameBar", "AllowAutoGameMode", 1, "DWORD", stop_event)
        if stop_event and stop_event.is_set():
            return False
        ok &= SystemManager.set_registry_policy(
            r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR",
            "AppCaptureEnabled", 0, "DWORD", stop_event)
        if stop_event and stop_event.is_set():
            return False
        ok &= SystemManager.set_registry_policy(
            r"HKLM\SOFTWARE\Policies\Microsoft\Windows\GameDVR",
            "AllowGameDVR", 0, "DWORD", stop_event)
        return ok

    @staticmethod
    def restore_gaming_mode(stop_event=None, logger=None) -> bool:
        if logger:
            logger.info("Restoring default gaming settings...")
        SystemManager.remove_registry_value(r"HKCU\SOFTWARE\Microsoft\GameBar", "AllowAutoGameMode", stop_event)
        SystemManager.remove_registry_value(r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR",
                                            "AppCaptureEnabled", stop_event)
        SystemManager.remove_registry_value(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\GameDVR",
                                            "AllowGameDVR", stop_event)
        return True

    # ------------------ Defender ------------------
    @staticmethod
    def disable_defender(stop_event=None, logger=None) -> bool:
        if logger:
            logger.warning("Disabling Windows Defender real‑time protection (security risk!)...")
        if stop_event and stop_event.is_set():
            return False
        code, out, _ = ProcessRunner.run_powershell(
            "(Get-MpComputerStatus).IsTamperProtected", timeout=10, stop_event=stop_event)
        if "True" in out:
            if logger:
                logger.error(
                    "Tamper Protection is ON – Defender cannot be disabled via policy. "
                    "Disable it manually in Windows Security first.")
            return False
        return SystemManager.set_registry_policy(
            r"HKLM\SOFTWARE\Policies\Microsoft\Windows Defender",
            "DisableAntiSpyware", 1, "DWORD", stop_event)

    @staticmethod
    def restore_defender(stop_event=None, logger=None) -> bool:
        if logger:
            logger.info("Removing Defender policy restriction...")
        return SystemManager.remove_registry_value(
            r"HKLM\SOFTWARE\Policies\Microsoft\Windows Defender",
            "DisableAntiSpyware", stop_event)


# ====================== SPLASH SCREEN ======================

class SplashScreen(ctk.CTk):
    def __init__(self, on_finish_callback: Callable[[], None]):
        super().__init__()
        self._on_finish = on_finish_callback
        self.overrideredirect(True)
        w, h = 600, 380
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.configure(fg_color="#08080c")
        try:
            self.wm_attributes("-transparentcolor", "#000001")
        except Exception:
            pass

        self.wrapper = ctk.CTkFrame(self, fg_color="#0c0c12", border_color=ACCENT,
                                    border_width=1, corner_radius=16)
        self.wrapper.pack(fill="both", expand=True, padx=10, pady=10)

        self.content = ctk.CTkFrame(self.wrapper, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=45, pady=40)

        # ==================== HOZZÁADOTT VANTAX CÍM ====================
        self.title_label = ctk.CTkLabel(self.content, text="VANTAX",
                                        font=ctk.CTkFont(family="Impact", size=54, weight="bold"),
                                        text_color=ACCENT)
        self.title_label.pack(pady=(35, 0))
        # ==============================================================

        status_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        status_frame.pack(fill="x", side="bottom", pady=(0, 5))
        self.status_label = ctk.CTkLabel(status_frame, text="» Initializing...",
                                         font=ctk.CTkFont(family="Consolas", size=11),
                                         text_color="#8888aa")
        self.status_label.pack(side="left")
        self.pct_label = ctk.CTkLabel(status_frame, text="00%",
                                      font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                                      text_color="#ffffff")
        self.pct_label.pack(side="right")

        self.progress = ctk.CTkProgressBar(self.content, width=490, height=3,
                                           fg_color="#12121c", progress_color=ACCENT)
        self.progress.pack(anchor="w", side="bottom", pady=(0, 10))
        self.progress.set(0)

        self.sub_info = ctk.CTkLabel(self.content, text="Initializing modules...",
                                     font=ctk.CTkFont(family="Consolas", size=9),
                                     text_color="#333344")
        self.sub_info.pack(anchor="w", side="bottom", pady=(0, 2))

        self._start_time = time.monotonic()
        self._duration = 3.5
        self._after_id = self.after(30, self._update)

    def _update(self) -> None:
        if not self.winfo_exists():
            return
        elapsed = time.monotonic() - self._start_time
        t = min(elapsed / self._duration, 1.0)
        value = 1.0 - (1.0 - t) ** 3
        self.progress.set(value)
        pct = int(value * 100)
        self.pct_label.configure(text=f"{pct:02d}%")

        if value < 0.25:
            self.status_label.configure(text="» Scanning system environment...")
            self.sub_info.configure(text="Loading: os.platform.win32 // sub_process_init")
        elif value < 0.5:
            self.status_label.configure(text="» Verifying Chocolatey remote repo...")
            self.sub_info.configure(text="Fetch: https://community.chocolatey.org/install.ps1")
        elif value < 0.75:
            self.status_label.configure(text="» Baking optimization algorithms...")
            self.sub_info.configure(text="RegKey: HKLM_POLICIES_BAKED // integrity_check")
        else:
            self.status_label.configure(text="» Rendering Vantax graphical interface...")
            self.sub_info.configure(text="UI: CustomTkinter.Mainframe // active_theme_load")

        if value < 1.0:
            self._after_id = self.after(30, self._update)
        else:
            self.status_label.configure(text="» System loaded. Launching...")
            self.sub_info.configure(text="Status: SUCCESS // Booting Vantax Main UI...")
            self._after_id = self.after(400, self._finish)

    def _finish(self) -> None:
        if self._after_id:
            self.after_cancel(self._after_id)
        self.destroy()
        self._on_finish()


# ====================== MAIN APPLICATION WINDOW ======================

class VantaxApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("VANTAX  EAv4.0")
        self.geometry("1000x720")
        self.configure(fg_color=BG_MAIN)

        self._state = AppState.IDLE
        self._lock = threading.Lock()
        self._choco_path: Optional[str] = SystemManager.find_choco()
        self.stop_event = threading.Event()
        self.logger = Logger(self.safe_log)
        self.worker_thread: Optional[threading.Thread] = None

        self.app_checkboxes: Dict[str, ctk.CTkCheckBox] = {}
        self.adv_vars: Dict[AdvOption, ctk.BooleanVar] = {}

        self.installed_success: List[str] = []
        self.installed_failed: List[str] = []
        self._restore_point_ok: bool = False
        self._destroyed: bool = False
        self.installer: Optional[PackageInstaller] = None

        self.setup_ui()

    # ---------- Properties ----------
    @property
    def choco_path(self) -> Optional[str]:
        with self._lock:
            return self._choco_path

    @choco_path.setter
    def choco_path(self, value: Optional[str]) -> None:
        with self._lock:
            self._choco_path = value

    # ---------- UI Construction ----------
    def setup_ui(self) -> None:
        title = ctk.CTkLabel(self, text="VANTAX EAv4.0",
                             font=ctk.CTkFont(family="Impact", size=26, weight="bold"),
                             text_color=ACCENT)
        title.pack(pady=(12, 2))

        self.tabview = ctk.CTkTabview(self, fg_color=BG_PANEL,
                                      segmented_button_fg_color=BG_SEGBTN,
                                      segmented_button_selected_color=ACCENT,
                                      segmented_button_selected_hover_color=ACCENT_HOVER)
        self.tabview.pack(pady=6, padx=40, fill="both", expand=True)

        self.tab_basic   = self.tabview.add("📦 PROGRAMS")
        self.tab_adv     = self.tabview.add("⚙️ SYSTEM")
        self.tab_presets = self.tabview.add("⚡ PRESETS")
        self.tab_restore = self.tabview.add("🔄 RESTORE")

        self.create_app_list()
        self.create_adv_tab()
        self.create_presets_tab()
        self.create_restore_tab()

        self.progress = ctk.CTkProgressBar(self, height=10, fg_color=BG_PANEL, progress_color=ACCENT)
        self.progress.pack(fill="x", padx=40, pady=(8, 4))
        self.progress.set(0)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=40, pady=(4, 4))

        self.start_btn = ctk.CTkButton(btn_frame, text="🚀 START PROCESS",
                                       font=ctk.CTkFont(size=16, weight="bold"),
                                       fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                       height=54, corner_radius=10,
                                       command=self.start_process)
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.stop_btn = ctk.CTkButton(btn_frame, text="STOP",
                                      font=ctk.CTkFont(size=14, weight="bold"),
                                      fg_color="#4a4a5a", hover_color="#333344",
                                      height=54, corner_radius=10,
                                      state="disabled", command=self.request_stop)
        self.stop_btn.pack(side="right", expand=True, fill="x", padx=(6, 0))

        self.status_label = ctk.CTkLabel(self, text="Ready", text_color="#aaa",
                                         font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=(3, 2))

        self.log_text = ctk.CTkTextbox(self, height=82, fg_color="#0e0e18", text_color="#999",
                                       font=ctk.CTkFont(family="Courier New", size=11))
        self.log_text.pack(fill="x", padx=40, pady=(0, 10))

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_app_list(self) -> None:
        scroll = ctk.CTkScrollableFrame(self.tab_basic, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        for category, apps in APPS_TO_INSTALL.items():
            cat_frame = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=8)
            cat_frame.pack(fill="x", padx=5, pady=6, ipady=4)
            ctk.CTkLabel(cat_frame, text=category,
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color="#ffffff").pack(anchor="w", padx=12, pady=4)

            grid = ctk.CTkFrame(cat_frame, fg_color="transparent")
            grid.pack(fill="x", padx=12, pady=2)
            grid.columnconfigure((0, 1, 2), weight=1)

            for idx, (name, choco_id) in enumerate(apps.items()):
                row, col = divmod(idx, 3)
                cb = ctk.CTkCheckBox(grid, text=name,
                                     font=ctk.CTkFont(size=12),
                                     fg_color=ACCENT, hover_color=ACCENT_HOVER)
                cb.grid(row=row, column=col, sticky="w", padx=4, pady=4)
                self.app_checkboxes[choco_id] = cb

    def create_adv_tab(self) -> None:
        scroll = ctk.CTkScrollableFrame(self.tab_adv, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        def section(title: str) -> ctk.CTkFrame:
            f = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=8)
            f.pack(fill="x", padx=5, pady=6, ipady=4)
            ctk.CTkLabel(f, text=title,
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color="#ffffff").pack(anchor="w", padx=12, pady=4)
            return f

        def add_opt(parent, opt: AdvOption, text: str, default: bool, warn: str = "") -> None:
            var = ctk.BooleanVar(value=default)
            self.adv_vars[opt] = var
            cb = ctk.CTkCheckBox(parent, text=text, variable=var,
                                 font=ctk.CTkFont(size=12),
                                 fg_color=ACCENT, hover_color=ACCENT_HOVER)
            cb.pack(anchor="w", padx=16, pady=4)
            if warn:
                ctk.CTkLabel(parent, text=warn,
                             font=ctk.CTkFont(size=10, slant="italic"),
                             text_color="#bb3333").pack(anchor="w", padx=36, pady=(0, 4))
            if opt == AdvOption.DEFENDER:
                cb.configure(command=self._defender_warning)

        f1 = section("🛡️ Privacy & Telemetry")
        add_opt(f1, AdvOption.COPILOT, "Disable Copilot AI (Windows 11)", True)
        add_opt(f1, AdvOption.ONEDRIVE, "Disable OneDrive integration", False)
        add_opt(f1, AdvOption.TELEMETRY, "Disable telemetry & data collection", True)

        f2 = section("⚠️ Destructive actions")
        add_opt(f2, AdvOption.EDGE, "Completely remove Microsoft Edge", False,
                "⚠ May affect WebView & system components!")
        add_opt(f2, AdvOption.DEFENDER, "Disable Windows Defender via policy", False,
                "⚠ SEVERE SECURITY RISK")

        f3 = section("⚡ Performance")
        add_opt(f3, AdvOption.HIBERFIL, "Disable hibernation (delete hiberfil.sys)", True)
        add_opt(f3, AdvOption.SUPERFETCH, "Disable SuperFetch/SysMain", True)
        add_opt(f3, AdvOption.PREFETCH, "Disable Prefetch", False)
        add_opt(f3, AdvOption.GAMINGMODE, "Enable Gaming Mode + disable Game DVR", True)

        f4 = section("🧹 Maintenance")
        add_opt(f4, AdvOption.TMPCLEAN, "Delete temporary files (Temp, Prefetch)", True,
                "⚠ First reboot may be slower (Prefetch rebuild)")
        add_opt(f4, AdvOption.WUPDATE, "Disable Windows Update (AU policy)", False,
                "⚠ Not recommended permanently")

        f5 = section("🌐 Network")
        add_opt(f5, AdvOption.DNS, "Set fast DNS (Cloudflare 1.1.1.1)", True)

    def _defender_warning(self) -> None:
        var = self.adv_vars.get(AdvOption.DEFENDER)
        if var and var.get():
            if not messagebox.askyesno("⚠ SECURITY WARNING",
                                       "Disabling Defender leaves your system completely unprotected.\n\n"
                                       "Tamper Protection may also block the policy.\n\n"
                                       "Are you sure you want to continue?"):
                var.set(False)

    def create_presets_tab(self) -> None:
        frame = ctk.CTkFrame(self.tab_presets, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(frame, text="Quick Selections",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=ACCENT).pack(pady=(10, 16))

        presets = [
            ("✅ Select All",       self.select_all),
            ("❌ Clear All",        self.deselect_all),
            ("⚡ Minimal (base)",   self.select_minimal),
            ("🎮 Gamer Pack",       self.select_gamer),
            ("💼 Office Pack",      self.select_work),
            ("🎨 Creative Pack",    self.select_creative),
            ("🔒 Security Pack",    self.select_security),
            ("💻 Dev Pack",         self.select_dev),
        ]
        for text, cmd in presets:
            ctk.CTkButton(frame, text=text, command=cmd,
                          fg_color=BG_SEGBTN, hover_color=ACCENT,
                          font=ctk.CTkFont(size=13), height=38,
                          corner_radius=8).pack(fill="x", padx=30, pady=4)

    def create_restore_tab(self) -> None:
        frame = ctk.CTkFrame(self.tab_restore, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(frame, text="Restore Factory Settings",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="#FFFFFF").pack(pady=(10, 5))
        ctk.CTkLabel(frame,
                     text="This will remove all Vantax restrictions and reinstall Microsoft Edge.",
                     font=ctk.CTkFont(size=12), text_color="#aaa",
                     justify="center").pack(pady=(0, 20))

        self.restore_btn = ctk.CTkButton(frame, text="🔄 RESTORE TO DEFAULT",
                                         font=ctk.CTkFont(size=14, weight="bold"),
                                         fg_color="#34495e", hover_color="#2c3e50",
                                         height=50, command=self.start_restore_process)
        self.restore_btn.pack(pady=10, padx=50, fill="x")

    # ---------- Preset helpers ----------
    def select_all(self): 
        for cb in self.app_checkboxes.values(): cb.select()
        for var in self.adv_vars.values(): var.set(True)

    def deselect_all(self):
        for cb in self.app_checkboxes.values(): cb.deselect()
        for var in self.adv_vars.values(): var.set(False)

    def select_minimal(self):
        self.deselect_all()
        for opt in (AdvOption.TELEMETRY, AdvOption.TMPCLEAN, AdvOption.DNS):
            self.adv_vars.get(opt, ctk.BooleanVar()).set(True)

    def select_gamer(self):
        self.select_minimal()
        for opt in (AdvOption.COPILOT, AdvOption.HIBERFIL, AdvOption.SUPERFETCH, AdvOption.GAMINGMODE):
            self.adv_vars.get(opt, ctk.BooleanVar()).set(True)
        for app in ("steam", "epicgameslauncher", "discord"):
            self.app_checkboxes.get(app, ctk.CTkCheckBox()).select()

    def select_work(self):
        self.deselect_all()
        for opt in (AdvOption.TELEMETRY, AdvOption.DNS):
            self.adv_vars.get(opt, ctk.BooleanVar()).set(True)
        for app in ("libreoffice", "adobereader", "zoom", "whatsapp"):
            self.app_checkboxes.get(app, ctk.CTkCheckBox()).select()

    def select_creative(self):
        self.deselect_all()
        for app in ("gimp", "inkscape", "blender", "sharex"):
            self.app_checkboxes.get(app, ctk.CTkCheckBox()).select()

    def select_security(self):
        self.deselect_all()
        for app in ("malwarebytes", "bitwarden", "keepassxc", "protonvpn"):
            self.app_checkboxes.get(app, ctk.CTkCheckBox()).select()

    def select_dev(self):
        self.deselect_all()
        for app in ("vscode", "git.install", "python3", "nodejs-lts", "microsoft-windows-terminal"):
            self.app_checkboxes.get(app, ctk.CTkCheckBox()).select()

    # ---------- Thread-safe UI updates ----------
    def safe_log(self, msg: str) -> None:
        if self._destroyed: return
        self.after(0, lambda m=msg: self._append_log(m))

    def _append_log(self, msg: str) -> None:
        if self._destroyed: return
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {msg}\n")
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > MAX_LOG_LINES:
            self.log_text.delete("1.0", f"{line_count - MAX_LOG_LINES}.0")
        self.log_text.see("end")

    def safe_update_status(self, text: str, progress: Optional[float] = None) -> None:
        self.after(0, lambda t=text, p=progress: self._update_status(t, p))

    def _update_status(self, text: str, progress: Optional[float] = None) -> None:
        self.status_label.configure(text=text)
        if progress is not None:
            self.progress.set(progress)

    def safe_finish(self, is_restore: bool = False) -> None:
        self.after(0, lambda r=is_restore: self._finish_ui(r))

    def _finish_ui(self, is_restore: bool) -> None:
        restart_needed = self._operations_require_restart()
        if restart_needed:
            self.start_btn.configure(
                state="normal", text="🔄 RESTART PC",
                fg_color="#1a7a30", hover_color="#145c24",
                command=self.restart_pc)
        else:
            self.start_btn.configure(
                state="normal", text="🚀 START PROCESS",
                fg_color=ACCENT, hover_color=ACCENT_HOVER,
                command=self.start_process)
        self.restore_btn.configure(state="normal", text="🔄 RESTORE TO DEFAULT")
        self.stop_btn.configure(state="disabled")
        self._state = AppState.IDLE

        if is_restore:
            msg = "System settings have been restored to factory defaults, Edge has been reinstalled."
            if self.stop_event.is_set():
                msg += "\n\n⚠️ The process was interrupted – restore may be partial."
        else:
            succ = len(self.installed_success)
            fail = len(self.installed_failed)
            msg = f"Optimisation completed.\n\nSuccessful installations: {succ}\nFailed: {fail}"
            if not self._restore_point_ok:
                msg += "\n\n⚠️ System restore point could not be created."
            if restart_needed:
                msg += "\n\nClick 'RESTART PC' to apply all changes."
        messagebox.showinfo("Vantax Status", msg)

    def _operations_require_restart(self) -> bool:
        restart_opts = {AdvOption.EDGE, AdvOption.HIBERFIL, AdvOption.SUPERFETCH,
                        AdvOption.PREFETCH, AdvOption.WUPDATE}
        return any(self.adv_vars.get(opt, ctk.BooleanVar(value=False)).get() for opt in restart_opts)

    # ---------- Control flow ----------
    def request_stop(self) -> None:
        self.stop_event.set()
        self.logger.warning("Stop request sent to the worker thread...")
        self.stop_btn.configure(state="disabled")
        with self._lock:
            inst = self.installer
        if inst:
            inst.stop()

    def start_process(self) -> None:
        if self._state != AppState.IDLE:
            return
        if platform.system() != "Windows":
            messagebox.showerror("Error", "Only Windows is supported.")
            return
        if not SystemManager.is_admin():
            messagebox.showerror("Admin required",
                                 "This application needs administrator privileges.\n\n"
                                 "Please restart it as administrator.")
            return

        self._state = AppState.RUNNING
        self.stop_event.clear()
        self.installed_success.clear()
        self.installed_failed.clear()
        self._restore_point_ok = False

        self.start_btn.configure(state="disabled", text="⏳ WORKING...")
        self.restore_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.logger.info("=== Vantax EAv4.0 optimisation started ===")
        self.worker_thread = threading.Thread(target=self._run_logic, daemon=True)
        self.worker_thread.start()

    def start_restore_process(self) -> None:
        if self._state != AppState.IDLE:
            return
        if not SystemManager.is_admin():
            messagebox.showerror("Admin required", "Restoration requires administrator rights.")
            return
        if not messagebox.askyesno("Confirm restore",
                                   "Revert all Vantax changes and reinstall Edge?"):
            return

        self._state = AppState.RESTORING
        self.stop_event.clear()
        self.start_btn.configure(state="disabled")
        self.restore_btn.configure(state="disabled", text="⏳ RESTORING...")
        self.stop_btn.configure(state="normal")
        self.logger.info("=== Restoring factory defaults ===")
        self.worker_thread = threading.Thread(target=self._run_restore_logic, daemon=True)
        self.worker_thread.start()

    # ---------- Background logic ----------
    def _run_logic(self) -> None:
        try:
            # 1. System restore point
            self.safe_update_status("Creating system restore point...", 0.03)
            code, _, _ = ProcessRunner.run_powershell(
                'Checkpoint-Computer -Description "Vantax pre-install" -RestorePointType "MODIFY_SETTINGS"',
                timeout=90, stop_event=self.stop_event)
            self._restore_point_ok = (code == 0)
            if not self._restore_point_ok:
                self.logger.warning("System restore point creation FAILED. Edge removal will require confirmation.")

            if self.stop_event.is_set():
                self.safe_finish()
                return

            # 2. Chocolatey
            if not self.choco_path:
                self.safe_update_status("Installing Chocolatey...", 0.10)
                if not self._install_choco():
                    self.logger.error("Chocolatey installation FAILED. Aborting.")
                    self.safe_finish()
                    return
                self.choco_path = SystemManager.find_choco()

            if self.stop_event.is_set():
                self.safe_finish()
                return

            # 3. Tweaks (including Edge removal with user confirmation if no restore point)
            self._run_tweaks()

            if self.stop_event.is_set():
                self.safe_finish()
                return

            # 4. App installations
            self._run_app_installs()

            self.safe_update_status("Process completed!", 1.0)
            self.safe_finish(is_restore=False)
        except Exception:
            self.logger.error(f"Unexpected error:\n{traceback.format_exc()}")
            self.safe_finish(is_restore=False)

    def _run_tweaks(self) -> None:
        # Edge removal may need user confirmation if restore point failed
        edge_var = self.adv_vars.get(AdvOption.EDGE)
        if edge_var and edge_var.get() and not self._restore_point_ok:
            # Ask user for confirmation
            confirmed = messagebox.askyesno(
                "⚠ Restore Point Missing",
                "A system restore point could not be created.\n\n"
                "Removing Edge without a restore point is risky.\n"
                "Do you still want to proceed with Edge removal?",
                icon="warning"
            )
            if not confirmed:
                self.logger.warning("Edge removal skipped by user (no restore point).")
                edge_var.set(False)  # uncheck and skip

        tweaks = [
            (AdvOption.COPILOT,    "Disabling Copilot...",      lambda: SystemOptimizer.disable_copilot(self.stop_event, self.logger)),
            (AdvOption.ONEDRIVE,   "Removing OneDrive...",      lambda: SystemOptimizer.disable_onedrive(self.stop_event, self.logger)),
            (AdvOption.TELEMETRY,  "Disabling telemetry...",    lambda: SystemOptimizer.disable_telemetry(self.stop_event)),
            (AdvOption.WUPDATE,    "Stopping Windows Update...", lambda: SystemOptimizer.disable_windows_update(self.stop_event, self.logger)),
            (AdvOption.HIBERFIL,   "Disabling hibernation...",  lambda: SystemOptimizer.disable_hibernation(self.stop_event, self.logger)),
            (AdvOption.SUPERFETCH, "Disabling SuperFetch...",   lambda: SystemOptimizer.disable_superfetch(self.stop_event, self.logger)),
            (AdvOption.PREFETCH,   "Disabling Prefetch...",     lambda: SystemOptimizer.disable_prefetch(self.stop_event, self.logger)),
            (AdvOption.DNS,        "Setting fast DNS...",       lambda: SystemOptimizer.set_fast_dns(self.stop_event, self.logger)),
            (AdvOption.GAMINGMODE, "Enabling Gaming Mode...",   lambda: SystemOptimizer.enable_gaming_mode(self.stop_event, self.logger)),
            (AdvOption.DEFENDER,   "Disabling Defender...",     lambda: SystemOptimizer.disable_defender(self.stop_event, self.logger)),
            (AdvOption.EDGE,       "Removing Edge...",          lambda: SystemOptimizer.remove_edge(self.stop_event, self.logger)),
            (AdvOption.TMPCLEAN,   "Cleaning temp files...",    lambda: SystemOptimizer.clean_temp(self.stop_event, self.logger)),
        ]
        total = len(tweaks)
        for idx, (opt, label, action) in enumerate(tweaks):
            if self.stop_event.is_set(): break
            if self.adv_vars.get(opt, ctk.BooleanVar(value=False)).get():
                self.safe_update_status(label, 0.15 + (idx / total) * 0.30)
                try:
                    action()
                except Exception as e:
                    self.logger.error(f"Tweak '{opt.name}' failed: {e}")

    def _run_app_installs(self) -> None:
        selected = [cid for cid, cb in self.app_checkboxes.items() if cb.get()]
        if not selected:
            return
        c_path = self.choco_path
        if not c_path:
            self.logger.error("Chocolatey path invalid – cannot install packages.")
            return
        with self._lock:
            self.installer = PackageInstaller(c_path, self.stop_event, self.logger)
            inst = self.installer
        total = len(selected)
        for idx, pkg in enumerate(selected):
            if self.stop_event.is_set(): break
            self.safe_update_status(f"Installing: {pkg} ({idx+1}/{total})...", 0.50 + (idx / total) * 0.45)
            res = inst.install(pkg)
            if res.success:
                self.logger.info(f"Successfully installed: {pkg}")
                self.installed_success.append(pkg)
            else:
                self.logger.error(f"Installation failed ({pkg}): {res.error_msg}")
                self.installed_failed.append(pkg)
        with self._lock:
            self.installer = None

    def _run_restore_logic(self) -> None:
        try:
            steps = [
                ("Reinstalling Microsoft Edge...", 0.15, lambda: SystemOptimizer.restore_edge(self.stop_event, self.logger)),
                ("Restoring Copilot...",           0.35, lambda: SystemOptimizer.restore_copilot(self.stop_event)),
                ("Restoring OneDrive...",          0.45, lambda: SystemOptimizer.restore_onedrive(self.stop_event)),
                ("Restoring telemetry...",         0.65, lambda: SystemOptimizer.restore_telemetry(self.stop_event)),
                ("Restoring Windows Update...",    0.75, lambda: SystemOptimizer.restore_windows_update(self.stop_event, self.logger)),
                ("Resetting DNS...",               0.85, lambda: SystemOptimizer.restore_dns(self.stop_event, self.logger)),
                ("Restoring other services...",    0.95, lambda: self._extra_restores()),
            ]
            for label, prog, action in steps:
                if self.stop_event.is_set(): break
                self.safe_update_status(label, prog)
                try:
                    action()
                except Exception as e:
                    self.logger.error(f"Restore step error: {e}")

            self.safe_update_status("🔄 Restore completed!", 1.0)
            self.safe_finish(is_restore=True)
        except Exception:
            self.logger.error(f"Unexpected error during restore:\n{traceback.format_exc()}")
            self.safe_finish(is_restore=True)

    def _extra_restores(self) -> None:
        funcs = [
            lambda: SystemOptimizer.restore_hibernation(self.stop_event, self.logger),
            lambda: SystemOptimizer.restore_superfetch(self.stop_event, self.logger),
            lambda: SystemOptimizer.restore_prefetch(self.stop_event, self.logger),
            lambda: SystemOptimizer.restore_gaming_mode(self.stop_event, self.logger),
            lambda: SystemOptimizer.restore_defender(self.stop_event, self.logger),
        ]
        for fn in funcs:
            if self.stop_event.is_set(): break
            try:
                fn()
            except Exception as e:
                self.logger.error(f"Extra restore error: {e}")

    def _install_choco(self) -> bool:
        self.logger.info("Installing Chocolatey from community.chocolatey.org...")
        ps = f"""
        $url  = '{CHOCO_INSTALL_URL}'
        $dest = Join-Path $env:TEMP 'choco_install.ps1'
        try {{
            (New-Object System.Net.WebClient).DownloadFile($url, $dest)
            $hash = (Get-FileHash $dest -Algorithm SHA256).Hash
            if ($hash -ne '{CHOCO_INSTALL_SHA256}') {{ throw "SHA256 checksum mismatch!" }}
            Set-ExecutionPolicy Bypass -Scope Process -Force
            & $dest
            'SUCCESS'
        }} catch {{
            Write-Error $_.Exception.Message
        }} finally {{
            if (Test-Path $dest) {{ Remove-Item $dest -Force -ErrorAction SilentlyContinue }}
        }}
        """
        code, out, err = ProcessRunner.run_powershell(ps, timeout=300, stop_event=self.stop_event)
        if code != 0:
            self.logger.error(f"Chocolatey install error: {err}")
            return False
        return "SUCCESS" in out or SystemManager.find_choco() is not None

    def restart_pc(self) -> None:
        if not SystemManager.is_admin():
            return
        try:
            subprocess.run(["shutdown", "/r", "/t", "5", "/c",
                            "Vantax EAv4.0 – restarting to apply changes..."], timeout=10)
        except Exception as e:
            messagebox.showerror("Error", f"Restart failed: {e}")
            return
        self.destroy()

    def on_closing(self) -> None:
        self._destroyed = True
        self.stop_event.set()
        with self._lock:
            inst = self.installer
        if inst:
            inst.stop()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
        self.destroy()


# ====================== ENTRY POINT ======================
if __name__ == "__main__":
    if platform.system() == "Windows" and not SystemManager.is_admin():
        try:
            if getattr(sys, 'frozen', False):
                executable = sys.executable
                params = subprocess.list2cmdline(sys.argv[1:])
            else:
                executable = sys.executable
                script = os.path.abspath(sys.argv[0])
                params = subprocess.list2cmdline([script] + sys.argv[1:])
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
            if ret > 32:
                sys.exit(0)
        except Exception:
            pass

    def launch() -> None:
        app = VantaxApp()
        app.mainloop()

    splash = SplashScreen(on_finish_callback=launch)
    splash.mainloop()

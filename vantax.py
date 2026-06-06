import subprocess
import sys
import os
import threading
import time
import shutil
import platform
import ctypes
import traceback
import glob
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import customtkinter as ctk
from tkinter import messagebox

# ====================== KONSTANSOK ======================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

ACCENT       = "#9B0000"
ACCENT_HOVER = "#6e0000"
BG_MAIN      = "#1a1a24"
BG_CARD      = "#1e1e2e"
BG_PANEL     = "#252533"
BG_SEGBTN    = "#323245"

class AdvOption(Enum):
    EDGE      = "edge"
    AI        = "ai"
    ONEDRIVE  = "one"
    TELEMETRY = "tele"
    WUPDATE   = "wupdate"
    DEFENDER  = "defender"
    HIBERFIL  = "hiberfil"
    SUPERFETCH= "superfetch"
    PREFETCH  = "prefetch"
    TMPCLEAN  = "tmpclean"
    DNS       = "dns"
    GAMINGMODE= "gamingmode"

REG_POLICIES = {
    "COPILOT":   r"SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot",
    "ONEDRIVE":  r"SOFTWARE\Policies\Microsoft\Windows\OneDrive",
    "TELEMETRY": r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
    "WUPDATE":   r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU",
    "GAMING":    r"SOFTWARE\Microsoft\GameBar",
}

# ====================== APPOK (60+) ======================
APPS_TO_INSTALL: Dict[str, Dict[str, str]] = {
    "🌐 Böngészők": {
        "Google Chrome":         "googlechrome",
        "Mozilla Firefox":       "firefox",
        "Brave Browser":         "brave",
        "Opera":                 "opera",
        "Opera GX":              "opera-gx",
        "Vivaldi":               "vivaldi",
        "Tor Browser":           "tor-browser",
    },
    "🛠️ Alap Eszközök": {
        "7-Zip":                 "7zip.install",
        "WinRAR":                "winrar",
        "VLC Media Player":      "vlc",
        "Notepad++":             "notepadplusplus.install",
        "PowerToys":             "powertoys",
        "Everything":            "everything.install",
        "TreeSize Free":         "treesizefree",
        "WinDirStat":            "windirstat",
        "CrystalDiskInfo":       "crystaldiskinfo",
        "HWiNFO":                "hwinfo",
        "CPU-Z":                 "cpu-z",
        "GPU-Z":                 "gpu-z",
        "Speccy":                "speccy",
        "Rufus":                 "rufus",
        "Ventoy":                "ventoy",
        "Balena Etcher":         "etcher",
        "WizTree":               "wiztree",
    },
    "💬 Kommunikáció": {
        "Discord":               "discord",
        "WhatsApp":              "whatsapp",
        "Telegram":              "telegram.install",
        "Signal":                "signal",
        "Slack":                 "slack",
        "Zoom":                  "zoom",
        "Microsoft Teams":       "microsoft-teams",
        "Skype":                 "skype",
        "Viber":                 "viber",
    },
    "🎵 Média & Szórakozás": {
        "Spotify":               "spotify",
        "Steam":                 "steam",
        "Epic Games Launcher":   "epicgameslauncher",
        "GOG Galaxy":            "goggalaxy",
        "Ubisoft Connect":       "ubisoft-connect",
        "EA App":                "ea-app",
        "qBittorrent":           "qbittorrent",
        "OBS Studio":            "obs-studio",
        "Handbrake":             "handbrake",
        "MPC-HC":                "mpc-hc",
        "AIMP":                  "aimp",
        "foobar2000":            "foobar2000",
        "Kodi":                  "kodi",
        "Plex Media Server":     "plex",
    },
    "💻 Fejlesztés": {
        "VS Code":               "vscode",
        "Git":                   "git.install",
        "Python 3":              "python3",
        "Node.js LTS":           "nodejs-lts",
        "Java JDK 21":           "openjdk",
        "Docker Desktop":        "docker-desktop",
        "Postman":               "postman",
        "HeidiSQL":              "heidisql",
        "Windows Terminal":      "microsoft-windows-terminal",
        "WinSCP":                "winscp.install",
        "PuTTY":                 "putty.install",
        "Notepad3":              "notepad3",
        "Vim":                   "vim",
        "NASM":                  "nasm",
        "CMake":                 "cmake",
    },
    "🎨 Grafika & Design": {
        "GIMP":                  "gimp",
        "Inkscape":              "inkscape",
        "Krita":                 "krita",
        "Blender":               "blender",
        "paint.net":             "paint.net",
        "IrfanView":             "irfanview",
        "ShareX":                "sharex",
        "Greenshot":             "greenshot",
    },
    "📄 Irodai szoftverek": {
        "LibreOffice":           "libreoffice",
        "Foxit PDF Reader":      "foxitreader",
        "Adobe Acrobat Reader":  "adobereader",
        "SumatraPDF":            "sumatrapdf",
        "Obsidian":              "obsidian",
        "Notion":                "notion",
        "Joplin":                "joplin",
    },
    "🔒 Biztonság & Hálózat": {
        "Malwarebytes":          "malwarebytes",
        "Bitwarden":             "bitwarden",
        "KeePassXC":             "keepassxc",
        "ProtonVPN":             "protonvpn",
        "Wireshark":             "wireshark",
        "Nmap":                  "nmap",
        "Advanced IP Scanner":   "advanced-ip-scanner",
        "TeamViewer":            "teamviewer",
        "AnyDesk":               "anydesk.install",
    },
}

# ====================== BACKEND ======================
@dataclass
class InstallResult:
    package: str
    success: bool
    error_msg: str = ""


class Logger:
    def __init__(self, log_callback):
        self.log_callback = log_callback

    def info(self, msg):    self.log_callback(f"[INFO] {msg}")
    def warning(self, msg): self.log_callback(f"[WARN] {msg}")
    def error(self, msg):   self.log_callback(f"[ERROR] {msg}")


class SystemManager:
    @staticmethod
    def is_admin() -> bool:
        if platform.system() != "Windows":
            return False
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    @staticmethod
    def _quote_windows(arg: str) -> str:
        if not arg:
            return '""'
        if ' ' in arg or '"' in arg:
            escaped = arg.replace('"', '\\"')
            return f'"{escaped}"'
        return arg

    @staticmethod
    def run_as_admin(script_path: str, args: List[str]) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            cmd_line = ' '.join(SystemManager._quote_windows(a) for a in [script_path] + args)
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, cmd_line, None, 1)
            return ret > 32
        except Exception:
            return False

    @staticmethod
    def run_powershell(command: str, timeout: int = 60,
                       stop_event: Optional[threading.Event] = None) -> Tuple[int, str, str]:
        if platform.system() != "Windows":
            return -1, "", "Nem Windows rendszer"

        full_command = (
            "$OutputEncoding = [System.Text.Encoding]::UTF8; "
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
            + command
        )
        cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", full_command]

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding='utf-8', errors='replace')

            stdout_lines: List[str] = []
            stderr_lines: List[str] = []

            def read_stream(stream, lines):
                for line in iter(stream.readline, ''):
                    lines.append(line)
                stream.close()

            t1 = threading.Thread(target=read_stream, args=(proc.stdout, stdout_lines), daemon=True)
            t2 = threading.Thread(target=read_stream, args=(proc.stderr, stderr_lines), daemon=True)
            t1.start(); t2.start()

            start = time.time()
            while proc.poll() is None:
                if stop_event and stop_event.is_set():
                    proc.terminate(); proc.wait(timeout=5)
                    return -3, "", "Megszakítva"
                if time.time() - start > timeout:
                    proc.terminate(); proc.wait(timeout=5)
                    return -4, "", "Időtúllépés"
                time.sleep(0.1)

            t1.join(1); t2.join(1)
            return proc.returncode, ''.join(stdout_lines), ''.join(stderr_lines)
        except Exception as e:
            return -2, "", str(e)

    @staticmethod
    def _normalize_ps_path(key_path: str) -> str:
        if ":\\" in key_path:
            return key_path
        for hive in ("HKLM", "HKCU", "HKCR", "HKU", "HKCC"):
            if key_path.upper().startswith(hive + "\\"):
                return hive + ":\\" + key_path[len(hive) + 1:]
        return "HKLM:\\" + key_path

    @staticmethod
    def set_registry_policy(key_path: str, value_name: str, value_data,
                             value_type: str = "DWORD", stop_event=None) -> bool:
        if not SystemManager.is_admin():
            return False
        reg_type_map = {"DWORD": "DWord", "QWORD": "QWord", "STRING": "String"}
        prop_type = reg_type_map.get(value_type.upper(), "DWord")
        formatted_value = f'"{value_data}"' if isinstance(value_data, str) else str(value_data)
        ps_path = SystemManager._normalize_ps_path(key_path)

        ps_cmd = f'''
        $path = "{ps_path}"
        try {{
            if (-not (Test-Path $path)) {{ New-Item -Path $path -Force | Out-Null }}
            if (Get-ItemProperty -Path $path -Name "{value_name}" -ErrorAction SilentlyContinue) {{
                Set-ItemProperty -Path $path -Name "{value_name}" -Value {formatted_value} -Force
            }} else {{
                New-ItemProperty -Path $path -Name "{value_name}" -Value {formatted_value} -PropertyType {prop_type} -Force | Out-Null
            }}
            $true
        }} catch {{ $false; Write-Error $_.Exception.Message }}
        '''
        code, _, _ = SystemManager.run_powershell(ps_cmd, timeout=30, stop_event=stop_event)
        return code == 0

    @staticmethod
    def find_choco() -> Optional[str]:
        for path in [
            shutil.which("choco.exe"),
            os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "chocolatey", "bin", "choco.exe"),
            os.path.join(os.environ.get("ALLUSERSPROFILE", r"C:\ProgramData"), "chocolatey", "bin", "choco.exe"),
        ]:
            if path and os.path.isfile(path):
                return path
        return None


class PackageInstaller:
    def __init__(self, choco_path: str, stop_event: threading.Event, logger: Logger):
        self.choco_path = choco_path
        self.stop_event = stop_event
        self.logger = logger
        self.current_process: Optional[subprocess.Popen] = None

    def install(self, package: str, retry: int = 2) -> InstallResult:
        cmd = [self.choco_path, "install", package, "-y", "--limit-output",
               "--no-progress", "--ignore-checksums"]

        for attempt in range(retry + 1):
            if self.stop_event.is_set():
                return InstallResult(package, False, "Megszakítva")
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, encoding='utf-8', errors='replace')
                self.current_process = proc

                stdout_lines: List[str] = []
                stderr_lines: List[str] = []

                def read_stream(stream, lines_list):
                    for line in iter(stream.readline, ''):
                        lines_list.append(line)
                    stream.close()

                t1 = threading.Thread(target=read_stream, args=(proc.stdout, stdout_lines), daemon=True)
                t2 = threading.Thread(target=read_stream, args=(proc.stderr, stderr_lines), daemon=True)
                t1.start(); t2.start()

                start = time.time()
                while proc.poll() is None:
                    if self.stop_event.is_set():
                        proc.terminate(); proc.wait(timeout=5)
                        return InstallResult(package, False, "Megszakítva")
                    if time.time() - start > 600:
                        proc.terminate(); proc.wait(timeout=5)
                        return InstallResult(package, False, "Időtúllépés")
                    time.sleep(0.2)

                t1.join(1); t2.join(1)

                if proc.returncode == 0:
                    return InstallResult(package, True)

                error_msg = f"RC={proc.returncode}"
                stderr_str = ''.join(stderr_lines)
                if stderr_str.strip():
                    error_msg += " | " + stderr_str.strip()[:200]

                if attempt < retry:
                    self.logger.warning(f"{package} újrapróbálkozás ({attempt+1}/{retry})...")
                    time.sleep(3)
                    continue
                return InstallResult(package, False, error_msg)

            except Exception as e:
                self.logger.error(f"Telepítési hiba ({package}): {e}")
                if attempt < retry:
                    time.sleep(3); continue
                return InstallResult(package, False, str(e))
            finally:
                self.current_process = None

        return InstallResult(package, False, "Ismeretlen hiba")

    def stop(self):
        if self.current_process and self.current_process.poll() is None:
            self.current_process.terminate()
            try:
                self.current_process.wait(3)
            except Exception:
                self.current_process.kill()


class SystemOptimizer:

    # ---------- Edge ----------
    @staticmethod
    def remove_edge(stop_event: threading.Event, logger: Logger) -> bool:
        logger.info("Microsoft Edge teljes eltávolítása indul...")
        if stop_event.is_set():
            return False

        subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], capture_output=True)
        subprocess.run(["taskkill", "/F", "/IM", "MicrosoftEdgeUpdate.exe"], capture_output=True)

        setup_name = "setup.x64.exe" if platform.machine().endswith('64') else "setup.x86.exe"
        base = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(os.path.abspath(__file__))
        setup_path = os.path.join(base, setup_name)

        if os.path.exists(setup_path):
            logger.info("Hivatalos Edge uninstaller futtatása...")
            for extra in [[], ["--msedgewebview"]]:
                try:
                    subprocess.Popen(
                        [setup_path, "--uninstall", "--system-level", "--force-uninstall"] + extra,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    time.sleep(3)
                except Exception:
                    pass

        for pat in [
            r"C:\Program Files (x86)\Microsoft\Edge",
            r"C:\Program Files (x86)\Microsoft\EdgeWebView",
            r"C:\Program Files\Microsoft\Edge",
            r"C:\Program Files\Microsoft\EdgeUpdate",
            r"C:\Windows\SystemApps\Microsoft.MicrosoftEdge*",
        ]:
            for path in (glob.glob(pat) or ([pat] if os.path.exists(pat) else [])):
                logger.info(f"Törlés: {path}")
                subprocess.run(["takeown", "/F", path, "/R", "/D", "Y"], capture_output=True, shell=True)
                subprocess.run(["icacls", path, "/grant", "Administrators:F", "/T"], capture_output=True, shell=True)
                subprocess.run(["cmd", "/c", "rd", "/s", "/q", path], capture_output=True, shell=True)

        logger.info("Edge eltávolítás befejezve.")
        return True

    # ---------- Copilot ----------
    @staticmethod
    def disable_copilot(stop_event=None) -> bool:
        ok = True
        for hive in [r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot",
                     r"HKCU\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot"]:
            ok &= SystemManager.set_registry_policy(hive, "TurnOffWindowsCopilot", 1, "DWORD", stop_event)
        return ok

    # ---------- OneDrive ----------
    @staticmethod
    def disable_onedrive(stop_event: threading.Event, logger: Logger) -> bool:
        subprocess.run(["taskkill", "/F", "/IM", "OneDrive.exe"], capture_output=True, timeout=10)
        SystemManager.run_powershell(
            r'Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" '
            r'-Name "OneDrive" -ErrorAction SilentlyContinue',
            stop_event=stop_event
        )
        return SystemManager.set_registry_policy(
            REG_POLICIES["ONEDRIVE"], "DisableFileSyncNGSC", 1, "DWORD", stop_event
        )

    # ---------- Telemetry ----------
    @staticmethod
    def disable_telemetry(stop_event=None) -> bool:
        ok = SystemManager.set_registry_policy(REG_POLICIES["TELEMETRY"], "AllowTelemetry", 0, "DWORD", stop_event)
        # Extra: DiagTrack service
        SystemManager.run_powershell(
            'Stop-Service -Name "DiagTrack" -Force -ErrorAction SilentlyContinue; '
            'Set-Service -Name "DiagTrack" -StartupType Disabled -ErrorAction SilentlyContinue',
            timeout=20, stop_event=stop_event
        )
        return ok

    # ---------- Windows Update disable ----------
    @staticmethod
    def disable_windows_update(stop_event=None, logger: Optional[Logger] = None) -> bool:
        if logger: logger.info("Windows Update letiltása...")
        ok = SystemManager.set_registry_policy(REG_POLICIES["WUPDATE"], "NoAutoUpdate", 1, "DWORD", stop_event)
        SystemManager.run_powershell(
            'Stop-Service -Name "wuauserv" -Force -ErrorAction SilentlyContinue; '
            'Set-Service -Name "wuauserv" -StartupType Disabled -ErrorAction SilentlyContinue',
            timeout=20, stop_event=stop_event
        )
        return ok

    # ---------- Hibernation ----------
    @staticmethod
    def disable_hibernation(stop_event=None, logger: Optional[Logger] = None) -> bool:
        if logger: logger.info("Hibernáció letiltása (hiberfil.sys törlése)...")
        code, _, err = SystemManager.run_powershell(
            'powercfg -h off', timeout=20, stop_event=stop_event
        )
        return code == 0

    # ---------- SuperFetch / SysMain ----------
    @staticmethod
    def disable_superfetch(stop_event=None, logger: Optional[Logger] = None) -> bool:
        if logger: logger.info("SuperFetch / SysMain letiltása...")
        code, _, _ = SystemManager.run_powershell(
            'Stop-Service -Name "SysMain" -Force -ErrorAction SilentlyContinue; '
            'Set-Service -Name "SysMain" -StartupType Disabled -ErrorAction SilentlyContinue',
            timeout=20, stop_event=stop_event
        )
        return code == 0

    # ---------- Prefetch ----------
    @staticmethod
    def disable_prefetch(stop_event=None, logger: Optional[Logger] = None) -> bool:
        if logger: logger.info("Prefetch letiltása...")
        return SystemManager.set_registry_policy(
            r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters",
            "EnablePrefetcher", 0, "DWORD", stop_event
        )

    # ---------- Temp cleanup ----------
    @staticmethod
    def clean_temp(stop_event=None, logger: Optional[Logger] = None) -> bool:
        if logger: logger.info("Ideiglenes fájlok törlése...")
        dirs_to_clean = [
            os.environ.get("TEMP", ""),
            os.environ.get("TMP", ""),
            r"C:\Windows\Temp",
            r"C:\Windows\Prefetch",
        ]
        for d in dirs_to_clean:
            if not d or not os.path.isdir(d):
                continue
            for item in os.listdir(d):
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
        if logger: logger.info("Temp tisztítás kész.")
        return True

    # ---------- DNS gyorsítás (Cloudflare) ----------
    @staticmethod
    def set_fast_dns(stop_event=None, logger: Optional[Logger] = None) -> bool:
        if logger: logger.info("DNS beállítása Cloudflare-re (1.1.1.1 / 1.0.0.1)...")
        ps = (
            '$adapters = Get-NetAdapter | Where-Object {$_.Status -eq "Up"}; '
            'foreach ($a in $adapters) { '
            '  Set-DnsClientServerAddress -InterfaceIndex $a.InterfaceIndex '
            '    -ServerAddresses ("1.1.1.1","1.0.0.1") -ErrorAction SilentlyContinue '
            '}'
        )
        code, _, _ = SystemManager.run_powershell(ps, timeout=30, stop_event=stop_event)
        return code == 0

    # ---------- Gaming mode ----------
    @staticmethod
    def enable_gaming_mode(stop_event=None, logger: Optional[Logger] = None) -> bool:
        if logger: logger.info("Gaming Mode + Game DVR letiltás...")
        ok = True
        ok &= SystemManager.set_registry_policy(
            r"HKCU\SOFTWARE\Microsoft\GameBar", "AllowAutoGameMode", 1, "DWORD", stop_event
        )
        ok &= SystemManager.set_registry_policy(
            r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 0, "DWORD", stop_event
        )
        ok &= SystemManager.set_registry_policy(
            r"HKLM\SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", 0, "DWORD", stop_event
        )
        return ok

    # ---------- Defender ----------
    @staticmethod
    def disable_defender(stop_event=None, logger: Optional[Logger] = None) -> bool:
        if logger: logger.warning("Windows Defender real-time protection letiltása (FIGYELEM: biztonsági kockázat!)...")
        return SystemManager.set_registry_policy(
            r"HKLM\SOFTWARE\Policies\Microsoft\Windows Defender",
            "DisableAntiSpyware", 1, "DWORD", stop_event
        )


# ====================== UI ======================
class VantaxUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Vantax EAv3.0 - System Optimizer & App Installer")
        self.geometry("920x740")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)

        self.stop_event      = threading.Event()
        self.installer: Optional[PackageInstaller] = None
        self.worker_thread: Optional[threading.Thread] = None
        self._lock           = threading.Lock()

        self.check_vars:  Dict[str, ctk.BooleanVar]       = {}
        self.adv_vars:    Dict[AdvOption, ctk.BooleanVar]  = {}
        self.installed_success: List[str]                  = []
        self.installed_failed:  List[Tuple[str, str]]      = []
        self.choco_path: Optional[str]                     = None

        self.logger = Logger(self.safe_log)
        self.setup_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(150, self.initial_check)

    # ================================================================
    #  UI SETUP
    # ================================================================
    def setup_ui(self):
        # --- Header ---
        header = ctk.CTkFrame(self, fg_color=BG_MAIN)
        header.pack(pady=(14, 4), padx=40, fill="x")
        ctk.CTkLabel(header, text="VANTAX", font=ctk.CTkFont(size=40, weight="bold"),
                     text_color=ACCENT).pack(side="left")
        ctk.CTkLabel(header, text="EAv3.0", font=ctk.CTkFont(size=15), text_color="#555").pack(side="left", padx=10)
        ctk.CTkLabel(header, text="System Optimizer & App Installer",
                     font=ctk.CTkFont(size=13), text_color="#777").pack(side="left", padx=4)

        # --- Tabs ---
        self.tabview = ctk.CTkTabview(
            self, fg_color=BG_PANEL,
            segmented_button_fg_color=BG_SEGBTN,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT_HOVER,
        )
        self.tabview.pack(pady=6, padx=40, fill="both", expand=True)

        self.tab_basic   = self.tabview.add("📦 PROGRAMOK")
        self.tab_adv     = self.tabview.add("⚙️ RENDSZER")
        self.tab_presets = self.tabview.add("⚡ PRESET-ek")

        self.create_app_list()
        self.create_adv_tab()
        self.create_presets_tab()

        # --- Progress ---
        self.progress = ctk.CTkProgressBar(self, height=10, fg_color=BG_PANEL, progress_color=ACCENT)
        self.progress.pack(fill="x", padx=40, pady=(8, 4))
        self.progress.set(0)

        # --- Buttons ---
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=40, pady=(4, 4))

        self.start_btn = ctk.CTkButton(
            btn_frame, text="🚀 FOLYAMAT INDÍTÁSA",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            height=54, corner_radius=10, command=self.start_process
        )
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.stop_btn = ctk.CTkButton(
            btn_frame, text="STOP",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#4a4a5a", hover_color="#333344",
            height=54, corner_radius=10, state="disabled",
            command=self.request_stop
        )
        self.stop_btn.pack(side="right", expand=True, fill="x", padx=(6, 0))

        # --- Status ---
        self.status_label = ctk.CTkLabel(self, text="Inicializálás...", text_color="#aaa",
                                         font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=(3, 2))

        # --- Log ---
        self.log_text = ctk.CTkTextbox(
            self, height=82, fg_color="#0e0e18", text_color="#999",
            font=ctk.CTkFont(family="Courier New", size=11)
        )
        self.log_text.pack(fill="x", padx=40, pady=(0, 10))

    # ---- App list ----
    def create_app_list(self):
        scroll = ctk.CTkScrollableFrame(self.tab_basic, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        for category, apps in APPS_TO_INSTALL.items():
            ctk.CTkLabel(scroll, text=category,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=ACCENT).pack(anchor="w", padx=8, pady=(10, 2))

            card = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=8)
            card.pack(fill="x", padx=4, pady=(0, 4))

            # 2-column grid inside the card
            card.columnconfigure((0, 1), weight=1)
            col = 0; row = 0
            for display_name, pkg_id in apps.items():
                var = ctk.BooleanVar(value=False)
                self.check_vars[pkg_id] = var
                cb = ctk.CTkCheckBox(
                    card, text=display_name, variable=var,
                    font=ctk.CTkFont(size=12),
                    checkbox_width=16, checkbox_height=16,
                    fg_color=ACCENT, hover_color=ACCENT_HOVER
                )
                cb.grid(row=row, column=col, sticky="w", padx=14, pady=3)
                col += 1
                if col > 1:
                    col = 0; row += 1

    # ---- System tab ----
    def create_adv_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_adv, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=8, pady=8)

        # Section helper
        def section(title: str):
            ctk.CTkLabel(scroll, text=title, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=ACCENT).pack(anchor="w", padx=8, pady=(12, 2))
            f = ctk.CTkFrame(scroll, fg_color=BG_CARD, corner_radius=8)
            f.pack(fill="x", padx=4, pady=(0, 4))
            return f

        def add_opt(parent, opt: AdvOption, label: str, default: bool, warning: str = ""):
            var = ctk.BooleanVar(value=default)
            self.adv_vars[opt] = var
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=1)
            ctk.CTkCheckBox(row, text=label, variable=var,
                            font=ctk.CTkFont(size=13),
                            fg_color=ACCENT, hover_color=ACCENT_HOVER).pack(side="left", padx=12, pady=5)
            if warning:
                ctk.CTkLabel(row, text=warning, font=ctk.CTkFont(size=10),
                             text_color="#ff6b6b").pack(side="left", padx=4)

        # Software removal
        f1 = section("🗑️  Szoftver eltávolítás")
        add_opt(f1, AdvOption.EDGE, "Microsoft Edge teljes eltávolítása", False,
                "⚠ egyes Win-frissítések visszatehetik")

        # Privacy
        f2 = section("🔒  Adatvédelem & Privátság")
        add_opt(f2, AdvOption.AI,        "Windows Copilot letiltása",          True)
        add_opt(f2, AdvOption.ONEDRIVE,  "OneDrive letiltása (policy)",         True)
        add_opt(f2, AdvOption.TELEMETRY, "Telemetria letiltása + DiagTrack",    True)
        add_opt(f2, AdvOption.DEFENDER,  "Windows Defender letiltása",          False,
                "⚠ BIZTONSÁGI KOCKÁZAT")

        # Performance
        f3 = section("⚡  Teljesítmény")
        add_opt(f3, AdvOption.HIBERFIL,   "Hibernáció kikapcsolása (hiberfil.sys)", True)
        add_opt(f3, AdvOption.SUPERFETCH, "SuperFetch / SysMain letiltása",         True)
        add_opt(f3, AdvOption.PREFETCH,   "Prefetch letiltása",                     False)
        add_opt(f3, AdvOption.GAMINGMODE, "Gaming Mode + Game DVR letiltás",        True)

        # Maintenance
        f4 = section("🧹  Karbantartás")
        add_opt(f4, AdvOption.TMPCLEAN,  "Temp fájlok törlése (%TEMP%, C:\\Windows\\Temp)", True)
        add_opt(f4, AdvOption.WUPDATE,   "Windows Update letiltása (AU policy)",             False,
                "⚠ nem ajánlott tartósan")

        # Network
        f5 = section("🌐  Hálózat")
        add_opt(f5, AdvOption.DNS, "DNS gyorsítása (Cloudflare 1.1.1.1)", True)

    # ---- Presets ----
    def create_presets_tab(self):
        frame = ctk.CTkFrame(self.tab_presets, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame, text="Gyors kiválasztás",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=ACCENT).pack(pady=(10, 16))

        btn_cfg = [
            ("✅  Mindent kijelöl",    self.select_all),
            ("❌  Mindent töröl",      self.deselect_all),
            ("⚡  Minimál (alap)",     self.select_minimal),
            ("🎮  Gamer csomag",       self.select_gamer),
            ("💼  Munkás csomag",      self.select_work),
            ("🎨  Kreatív csomag",     self.select_creative),
            ("🔒  Biztonsági csomag",  self.select_security),
            ("💻  Dev csomag",         self.select_dev),
        ]
        for text, cmd in btn_cfg:
            ctk.CTkButton(
                frame, text=text, command=cmd,
                fg_color=BG_SEGBTN, hover_color=ACCENT,
                font=ctk.CTkFont(size=13), height=38, corner_radius=8
            ).pack(fill="x", padx=30, pady=4)

    # ---- Preset helpers ----
    def _set_all(self, value: bool):
        for var in self.check_vars.values():
            var.set(value)

    def select_all(self):     self._set_all(True)
    def deselect_all(self):   self._set_all(False)

    def _select(self, pkgs: List[str]):
        self.deselect_all()
        for p in pkgs:
            if p in self.check_vars:
                self.check_vars[p].set(True)

    def select_minimal(self):
        self._select(["7zip.install", "vlc", "notepadplusplus.install",
                      "googlechrome", "sumatrapdf"])

    def select_gamer(self):
        self._select(["steam", "epicgameslauncher", "goggalaxy", "discord",
                      "obs-studio", "qbittorrent", "brave", "spotify",
                      "sharex", "7zip.install", "vlc"])

    def select_work(self):
        self._select(["googlechrome", "vscode", "git.install", "7zip.install",
                      "notepadplusplus.install", "libreoffice", "everything.install",
                      "slack", "zoom", "sumatrapdf", "bitwarden"])

    def select_creative(self):
        self._select(["gimp", "inkscape", "krita", "blender", "paint.net",
                      "obs-studio", "sharex", "spotify", "vlc",
                      "googlechrome", "7zip.install"])

    def select_security(self):
        self._select(["malwarebytes", "bitwarden", "keepassxc", "protonvpn",
                      "brave", "tor-browser", "wireshark", "7zip.install"])

    def select_dev(self):
        self._select(["vscode", "git.install", "python3", "nodejs-lts",
                      "docker-desktop", "postman", "heidisql",
                      "microsoft-windows-terminal", "winscp.install",
                      "putty.install", "googlechrome", "7zip.install"])

    # ---- Logging ----
    def safe_log(self, msg: str):
        self.after(0, lambda: self._append_log(msg))

    def _append_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {msg}\n")
        self.log_text.see("end")

    def safe_update_status(self, text: str, progress: Optional[float] = None):
        self.after(0, lambda: self._update_status(text, progress))

    def _update_status(self, text: str, progress=None):
        self.status_label.configure(text=text)
        if progress is not None:
            self.progress.set(progress)

    def safe_finish(self):
        self.after(0, self._finish_ui)

    def _finish_ui(self):
        self.start_btn.configure(
            state="normal", text="🔄 GÉP ÚJRAINDÍTÁSA",
            fg_color="#1a7a30", hover_color="#145c24",
            command=self.restart_pc
        )
        self.stop_btn.configure(state="disabled")

        ok  = len(self.installed_success)
        nok = len(self.installed_failed)
        msg = f"✅ Sikeres telepítés: {ok}\n❌ Sikertelen: {nok}"
        if self.installed_failed:
            msg += "\n\nHibák:\n" + "\n".join(
                f"• {pkg}: {err[:120]}" for pkg, err in self.installed_failed
            )
        if self.stop_event.is_set():
            msg += "\n\n⚠️ A folyamat manuálisan lett leállítva."
        messagebox.showinfo("Vantax EAv3.0 – Kész", f"Folyamat befejezve!\n\n{msg}")

    # ---- Initial check ----
    def initial_check(self):
        self.choco_path = SystemManager.find_choco()
        if self.choco_path:
            self.safe_update_status("✅ Chocolatey megtalálva – kész a telepítéshez", 0.0)
            self.logger.info(f"Chocolatey: {self.choco_path}")
        else:
            self.safe_update_status("⚠️ Chocolatey nem található – telepítésre kerül", 0.0)
            self.logger.warning("Chocolatey hiányzik.")

    def request_stop(self):
        self.stop_event.set()
        if self.installer:
            self.installer.stop()
        self.logger.info("Leállítás kérve...")
        self.safe_update_status("Leállítás folyamatban...")

    # ---- Start ----
    def start_process(self):
        if platform.system() != "Windows":
            messagebox.showerror("Hiba", "Csak Windows alatt fut!")
            return
        if not SystemManager.is_admin():
            if SystemManager.run_as_admin(sys.argv[0], sys.argv[1:]):
                self.destroy(); return
            messagebox.showerror("Admin jog szükséges",
                                 "Futtasd rendszergazdaként (Run as administrator)!")
            return

        self.stop_event.clear()
        self.installed_success.clear()
        self.installed_failed.clear()

        self.start_btn.configure(state="disabled", text="⏳ DOLGOZOM...")
        self.stop_btn.configure(state="normal")
        self.logger.info("=== Vantax EAv3.0 folyamat elindult ===")

        self.worker_thread = threading.Thread(target=self.run_logic, daemon=True)
        self.worker_thread.start()

    # ---- Worker ----
    def run_logic(self):
        try:
            self.safe_update_status("Rendszer-visszaállítási pont...", 0.03)
            SystemManager.run_powershell(
                'Checkpoint-Computer -Description "Vantax pre-install" '
                '-RestorePointType "MODIFY_SETTINGS" -ErrorAction SilentlyContinue',
                timeout=90, stop_event=self.stop_event
            )

            if self.stop_event.is_set(): self.safe_finish(); return

            if not self.choco_path:
                self.safe_update_status("Chocolatey telepítése...", 0.10)
                if not self.install_chocolatey():
                    self.logger.error("Chocolatey telepítése SIKERTELEN. Leállás.")
                    self.safe_finish(); return
                self.choco_path = SystemManager.find_choco()

            if self.stop_event.is_set(): self.safe_finish(); return

            self.safe_update_status("Rendszer optimalizálás...", 0.22)
            self.run_cleanup()

            if self.stop_event.is_set(): self.safe_finish(); return

            selected = [cid for cid, var in self.check_vars.items() if var.get()]
            if selected and self.choco_path:
                self.logger.info(f"{len(selected)} csomag telepítése indul...")
                self.installer = PackageInstaller(self.choco_path, self.stop_event, self.logger)

                for i, pkg in enumerate(selected):
                    if self.stop_event.is_set(): break
                    prog = 0.30 + 0.68 * (i + 1) / len(selected)
                    self.safe_update_status(f"Telepítés: {pkg}  ({i+1}/{len(selected)})", prog)
                    res = self.installer.install(pkg)
                    with self._lock:
                        if res.success:
                            self.installed_success.append(pkg)
                            self.logger.info(f"✓ {pkg}")
                        else:
                            self.installed_failed.append((pkg, res.error_msg))
                            self.logger.error(f"✗ {pkg} – {res.error_msg}")
                self.installer = None
            elif not selected:
                self.logger.info("Nincs kiválasztott program.")
            else:
                self.logger.error("Chocolatey útvonal ismeretlen – telepítés kihagyva.")

            self.safe_update_status("✅ Minden kész!", 1.0)
            self.safe_finish()
        except Exception:
            self.logger.error(f"Váratlan hiba:\n{traceback.format_exc()}")
            self.safe_finish()

    def install_chocolatey(self) -> bool:
        self.logger.info("Chocolatey telepítése (community.chocolatey.org)...")
        ps = (
            "Set-ExecutionPolicy Bypass -Scope Process -Force; "
            "[System.Net.ServicePointManager]::SecurityProtocol = "
            "[System.Net.ServicePointManager]::SecurityProtocol -bor 3072; "
            "iex ((New-Object System.Net.WebClient).DownloadString("
            "'https://community.chocolatey.org/install.ps1'))"
        )
        code, _, err = SystemManager.run_powershell(ps, timeout=300, stop_event=self.stop_event)
        if code != 0:
            self.logger.error(f"Choco hiba: {err[:300]}")
            return False
        time.sleep(2)
        # Reload PATH so choco.exe is findable immediately
        os.environ["PATH"] = (
            os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "chocolatey", "bin")
            + os.pathsep + os.environ.get("PATH", "")
        )
        self.logger.info("Chocolatey sikeresen telepítve.")
        return True

    def run_cleanup(self):
        actions = [
            (AdvOption.EDGE,       lambda: SystemOptimizer.remove_edge(self.stop_event, self.logger)),
            (AdvOption.AI,         lambda: SystemOptimizer.disable_copilot(self.stop_event)),
            (AdvOption.ONEDRIVE,   lambda: SystemOptimizer.disable_onedrive(self.stop_event, self.logger)),
            (AdvOption.TELEMETRY,  lambda: SystemOptimizer.disable_telemetry(self.stop_event)),
            (AdvOption.DEFENDER,   lambda: SystemOptimizer.disable_defender(self.stop_event, self.logger)),
            (AdvOption.HIBERFIL,   lambda: SystemOptimizer.disable_hibernation(self.stop_event, self.logger)),
            (AdvOption.SUPERFETCH, lambda: SystemOptimizer.disable_superfetch(self.stop_event, self.logger)),
            (AdvOption.PREFETCH,   lambda: SystemOptimizer.disable_prefetch(self.stop_event, self.logger)),
            (AdvOption.GAMINGMODE, lambda: SystemOptimizer.enable_gaming_mode(self.stop_event, self.logger)),
            (AdvOption.TMPCLEAN,   lambda: SystemOptimizer.clean_temp(self.stop_event, self.logger)),
            (AdvOption.WUPDATE,    lambda: SystemOptimizer.disable_windows_update(self.stop_event, self.logger)),
            (AdvOption.DNS,        lambda: SystemOptimizer.set_fast_dns(self.stop_event, self.logger)),
        ]
        for opt, fn in actions:
            if self.stop_event.is_set():
                break
            var = self.adv_vars.get(opt)
            if var and var.get():
                try:
                    ok = fn()
                    if not ok:
                        self.logger.warning(f"{opt.value} – részben sikertelen.")
                except Exception as e:
                    self.logger.error(f"{opt.value} hiba: {e}")

    def restart_pc(self):
        if messagebox.askyesno("Újraindítás", "Biztosan újra akarod indítani a gépet most?"):
            subprocess.run(["shutdown", "/r", "/t", "5",
                            "/c", "Vantax EAv3.0 optimalizáció kész – újraindítás..."])
            self.destroy()

    def on_closing(self):
        self.stop_event.set()
        if self.installer:
            self.installer.stop()
        self.destroy()


if __name__ == "__main__":
    app = VantaxUI()
    app.mainloop()
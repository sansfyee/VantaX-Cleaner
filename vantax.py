import subprocess
import sys
import os
import threading
import time
import shutil
import platform
import ctypes
import traceback
import glob  # FIX 1: glob was used in remove_edge but never imported
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import customtkinter as ctk
from tkinter import messagebox

# ====================== KONSTANSOK ======================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AdvOption(Enum):
    EDGE = "edge"
    AI = "ai"
    ONEDRIVE = "one"
    TELEMETRY = "tele"

REG_POLICIES = {
    "COPILOT": r"SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot",
    "ONEDRIVE": r"SOFTWARE\Policies\Microsoft\Windows\OneDrive",
    "TELEMETRY": r"SOFTWARE\Policies\Microsoft\Windows\DataCollection"
}

APPS_TO_INSTALL = {
    "Böngészők": {
        "Google Chrome": "googlechrome",
        "Mozilla Firefox": "firefox",
        "Brave Browser": "brave"
    },
    "Alap Eszközök": {
        "7-Zip": "7zip.install",
        "VLC Media Player": "vlc",
        "Notepad++": "notepadplusplus.install",
        "PowerToys": "powertoys",
        "Everything": "everything.install"
    },
    "Kommunikáció": {
        "Discord": "discord",
        "WhatsApp": "whatsapp",
        "Telegram": "telegram.install"
    },
    "Média & Szórakozás": {
        "Spotify": "spotify",
        "Steam": "steam",
        "qBittorrent": "qbittorrent",
        "OBS Studio": "obs-studio"
    },
    "Egyéb Hasznos": {
        "VS Code": "vscode",
        "Git": "git.install",
        "Rufus": "rufus",
        "LibreOffice": "libreoffice"
    }
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

    def info(self, msg):
        self.log_callback(f"[INFO] {msg}")

    def warning(self, msg):
        self.log_callback(f"[WARNING] {msg}")

    def error(self, msg):
        self.log_callback(f"[ERROR] {msg}")


class SystemManager:
    @staticmethod
    def is_admin() -> bool:
        if platform.system() != "Windows":
            return False
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False

    @staticmethod
    def _quote_windows(arg: str) -> str:
        if not arg:
            return '""'
        # FIX 2: nested same-quote f-string syntax error — use a variable for the replacement
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
        except:
            return False

    @staticmethod
    def run_powershell(command: str, timeout: int = 60, stop_event: Optional[threading.Event] = None) -> Tuple[int, str, str]:
        if platform.system() != "Windows":
            return -1, "", "Nem Windows rendszer"

        full_command = f'$OutputEncoding = [System.Text.Encoding]::UTF8; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {command}'
        cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", full_command]

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')

            stdout_lines = []
            stderr_lines = []

            def read_stream(stream, lines):
                for line in iter(stream.readline, ''):
                    lines.append(line)
                stream.close()

            t1 = threading.Thread(target=read_stream, args=(proc.stdout, stdout_lines), daemon=True)
            t2 = threading.Thread(target=read_stream, args=(proc.stderr, stderr_lines), daemon=True)
            t1.start()
            t2.start()

            start = time.time()
            while proc.poll() is None:
                if stop_event and stop_event.is_set():
                    proc.terminate()
                    proc.wait(timeout=5)
                    return -3, "", "Megszakítva"
                if time.time() - start > timeout:
                    proc.terminate()
                    proc.wait(timeout=5)
                    return -4, "", "Időtúllépés"
                time.sleep(0.1)

            t1.join(1)
            t2.join(1)
            return proc.returncode, ''.join(stdout_lines), ''.join(stderr_lines)

        except Exception as e:
            return -2, "", str(e)

    @staticmethod
    def _normalize_ps_path(key_path: str) -> str:
        """FIX 6: Normalize a registry path to a valid PowerShell PSDrive path."""
        # Already has PS drive syntax (e.g. HKLM:\...)
        if ":\\" in key_path:
            return key_path
        # Replace first \ with :\  for known hives
        for hive in ("HKLM", "HKCU", "HKCR", "HKU", "HKCC"):
            if key_path.upper().startswith(hive + "\\"):
                return hive + ":\\" + key_path[len(hive) + 1:]
        # Default: assume HKLM
        return "HKLM:\\" + key_path

    @staticmethod
    def set_registry_policy(key_path: str, value_name: str, value_data, value_type: str = "DWORD", stop_event=None) -> bool:
        if not SystemManager.is_admin():
            return False

        reg_type_map = {"DWORD": "DWord", "QWORD": "QWord", "STRING": "String"}
        prop_type = reg_type_map.get(value_type.upper(), "DWord")

        formatted_value = f'"{value_data}"' if isinstance(value_data, str) else str(value_data)

        # FIX 6: use the dedicated normalizer instead of the broken inline replace
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
            os.path.join(os.environ.get("ALLUSERSPROFILE", r"C:\ProgramData"), "chocolatey", "bin", "choco.exe")
        ]:
            if path and os.path.isfile(path):
                return path
        return None


class PackageInstaller:
    def __init__(self, choco_path: str, stop_event: threading.Event, logger: Logger):
        self.choco_path = choco_path
        self.stop_event = stop_event
        self.logger = logger
        self.current_process = None

    def install(self, package: str, retry: int = 2) -> InstallResult:
        cmd = [self.choco_path, "install", package, "-y", "--limit-output", "--no-progress"]

        for attempt in range(retry + 1):
            if self.stop_event.is_set():
                return InstallResult(package, False, "Megszakítva")

            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
                self.current_process = proc

                stdout_lines = []
                stderr_lines = []

                def read_stream(stream, lines_list):
                    for line in iter(stream.readline, ''):
                        lines_list.append(line)
                    stream.close()

                t1 = threading.Thread(target=read_stream, args=(proc.stdout, stdout_lines), daemon=True)
                t2 = threading.Thread(target=read_stream, args=(proc.stderr, stderr_lines), daemon=True)
                t1.start()
                t2.start()

                start = time.time()
                while proc.poll() is None:
                    if self.stop_event.is_set():
                        proc.terminate()
                        proc.wait(timeout=5)
                        return InstallResult(package, False, "Megszakítva")
                    if time.time() - start > 600:
                        proc.terminate()
                        proc.wait(timeout=5)
                        return InstallResult(package, False, "Időtúllépés")
                    time.sleep(0.2)

                t1.join(1)
                t2.join(1)

                if proc.returncode == 0:
                    return InstallResult(package, True)

                error_msg = f"Return code: {proc.returncode}"
                if attempt < retry:
                    self.logger.warning(f"{package} újrapróbálkozás ({attempt+1}/{retry})")
                    time.sleep(3)
                    continue

                return InstallResult(package, False, error_msg)

            except Exception as e:
                self.logger.error(f"Telepítési hiba ({package}): {e}")
                if attempt < retry:
                    time.sleep(3)
                    continue
                return InstallResult(package, False, str(e))
            finally:
                self.current_process = None

        return InstallResult(package, False, "Ismeretlen hiba")

    def stop(self):
        if self.current_process and self.current_process.poll() is None:
            self.current_process.terminate()
            try:
                self.current_process.wait(3)
            except:
                self.current_process.kill()


class SystemOptimizer:
    @staticmethod
    def remove_edge(stop_event: threading.Event, logger: Logger) -> bool:
        logger.info("Microsoft Edge teljes eltávolítása indul...")
        if stop_event.is_set():
            return False

        subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], capture_output=True)
        subprocess.run(["taskkill", "/F", "/IM", "MicrosoftEdgeUpdate.exe"], capture_output=True)

        setup_name = "setup.x64.exe" if platform.machine().endswith('64') else "setup.x86.exe"
        if hasattr(sys, '_MEIPASS'):
            setup_path = os.path.join(sys._MEIPASS, setup_name)
        else:
            setup_path = os.path.join(os.path.dirname(__file__), setup_name)

        if os.path.exists(setup_path):
            logger.info("Hivatalos Edge uninstaller futtatása...")
            try:
                subprocess.Popen([setup_path, "--uninstall", "--system-level", "--force-uninstall"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(3)
            except:
                pass

            try:
                subprocess.Popen([setup_path, "--uninstall", "--msedgewebview", "--system-level", "--force-uninstall"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                pass

        paths_to_remove = [
            r"C:\Program Files (x86)\Microsoft\Edge",
            r"C:\Program Files (x86)\Microsoft\EdgeWebView",
            r"C:\Program Files\Microsoft\Edge",
            r"C:\Program Files\Microsoft\EdgeUpdate",
            r"C:\Windows\SystemApps\Microsoft.MicrosoftEdge*"
        ]

        for path_pattern in paths_to_remove:
            # FIX 1: glob is now imported — expand wildcards properly
            matches = glob.glob(path_pattern)
            targets = matches if matches else ([path_pattern] if os.path.exists(path_pattern) else [])
            for path in targets:
                logger.info(f"Mappa törlése: {path}")
                subprocess.run(["takeown", "/F", path, "/R", "/D", "Y"], capture_output=True, shell=True)
                subprocess.run(["icacls", path, "/grant", "Administrators:F", "/T"], capture_output=True, shell=True)
                subprocess.run(["cmd", "/c", "rd", "/s", "/q", path], capture_output=True, shell=True)

        logger.info("Edge eltávolítás befejezve (lehet, hogy újraindítás után teljes).")
        return True

    @staticmethod
    def disable_copilot(stop_event=None) -> bool:
        success = True
        for hive in [r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot",
                     r"HKCU\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot"]:
            success &= SystemManager.set_registry_policy(hive, "TurnOffWindowsCopilot", 1, "DWORD", stop_event)
        return success

    @staticmethod
    def disable_onedrive(stop_event: threading.Event, logger: Logger) -> bool:
        subprocess.run(["taskkill", "/F", "/IM", "OneDrive.exe"], capture_output=True, timeout=10)
        SystemManager.run_powershell(
            r'Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "OneDrive" -ErrorAction SilentlyContinue',
            stop_event=stop_event
        )
        return SystemManager.set_registry_policy(REG_POLICIES["ONEDRIVE"], "DisableFileSyncNGSC", 1, "DWORD", stop_event)

    @staticmethod
    def disable_telemetry(stop_event=None) -> bool:
        return SystemManager.set_registry_policy(REG_POLICIES["TELEMETRY"], "AllowTelemetry", 0, "DWORD", stop_event)


# ====================== UI ======================
class VantaxUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Vantax v2.3 - Ultimate Edge Killer")
        self.geometry("840x680")
        self.resizable(False, False)
        self.configure(fg_color="#1a1a24")

        self.stop_event = threading.Event()
        self.installer: Optional[PackageInstaller] = None
        self.worker_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self.check_vars: Dict[str, ctk.BooleanVar] = {}
        self.adv_vars: Dict[AdvOption, ctk.BooleanVar] = {}
        self.installed_success = []
        self.installed_failed = []
        self.choco_path: Optional[str] = None

        self.logger = Logger(self.safe_log)

        self.setup_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(150, self.initial_check)

    def setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="#1a1a24")
        header.pack(pady=15, padx=40, fill="x")
        ctk.CTkLabel(header, text="VANTAX", font=ctk.CTkFont(size=42, weight="bold"), text_color="#f5425a").pack(side="left")
        ctk.CTkLabel(header, text="v2.3", font=ctk.CTkFont(size=16), text_color="#666").pack(side="left", padx=12)

        self.tabview = ctk.CTkTabview(self, fg_color="#252533", segmented_button_fg_color="#323245",
                                      segmented_button_selected_color="#f5425a")
        self.tabview.pack(pady=10, padx=40, fill="both", expand=True)

        self.tab_basic = self.tabview.add("PROGRAMOK")
        self.tab_adv = self.tabview.add("RENDSZER")
        self.tab_presets = self.tabview.add("PRESET-ek")

        self.create_app_list()
        self.create_adv_tab()
        self.create_presets_tab()

        self.progress = ctk.CTkProgressBar(self, height=12, fg_color="#252533", progress_color="#f5425a")
        self.progress.pack(fill="x", padx=40, pady=(10, 5))
        self.progress.set(0)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=40, pady=(5, 5))

        self.start_btn = ctk.CTkButton(btn_frame, text="🚀 FOLYAMAT INDÍTÁSA", font=ctk.CTkFont(size=17, weight="bold"),
                                       fg_color="#f5425a", height=58, corner_radius=12, command=self.start_process)
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 8))

        self.stop_btn = ctk.CTkButton(btn_frame, text="⏹️ STOP", font=ctk.CTkFont(size=15, weight="bold"),
                                      fg_color="#6c757d", height=58, corner_radius=12, state="disabled", command=self.request_stop)
        self.stop_btn.pack(side="right", expand=True, fill="x", padx=(8, 0))

        self.status_label = ctk.CTkLabel(self, text="Rendszer ellenőrzése...", text_color="#bbb")
        self.status_label.pack(pady=(4, 2))

        # FIX 3: log_text was referenced in _append_log but never created
        self.log_text = ctk.CTkTextbox(self, height=80, fg_color="#12121a", text_color="#aaa",
                                       font=ctk.CTkFont(family="Courier", size=11))
        self.log_text.pack(fill="x", padx=40, pady=(0, 10))

    # ---- App list tab ----
    def create_app_list(self):
        scroll = ctk.CTkScrollableFrame(self.tab_basic, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=5, pady=5)

        for category, apps in APPS_TO_INSTALL.items():
            cat_label = ctk.CTkLabel(scroll, text=category.upper(),
                                     font=ctk.CTkFont(size=12, weight="bold"),
                                     text_color="#f5425a")
            cat_label.pack(anchor="w", padx=10, pady=(10, 2))

            cat_frame = ctk.CTkFrame(scroll, fg_color="#1e1e2e", corner_radius=8)
            cat_frame.pack(fill="x", padx=5, pady=(0, 4))

            for display_name, pkg_id in apps.items():
                var = ctk.BooleanVar(value=False)
                self.check_vars[pkg_id] = var
                cb = ctk.CTkCheckBox(cat_frame, text=display_name, variable=var,
                                     font=ctk.CTkFont(size=13),
                                     checkbox_width=18, checkbox_height=18,
                                     fg_color="#f5425a", hover_color="#c73346")
                cb.pack(anchor="w", padx=15, pady=4)

    # ---- System / advanced tab ----
    def create_adv_tab(self):
        frame = ctk.CTkFrame(self.tab_adv, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        options = [
            (AdvOption.EDGE,      "🗑️  Microsoft Edge eltávolítása",  False),
            (AdvOption.AI,        "🤖  Windows Copilot letiltása",     True),
            (AdvOption.ONEDRIVE,  "☁️  OneDrive letiltása",            True),
            (AdvOption.TELEMETRY, "📡  Telemetria letiltása",          True),
        ]

        for opt, label, default in options:
            var = ctk.BooleanVar(value=default)
            self.adv_vars[opt] = var
            cb = ctk.CTkCheckBox(frame, text=label, variable=var,
                                 font=ctk.CTkFont(size=14),
                                 fg_color="#f5425a", hover_color="#c73346")
            cb.pack(anchor="w", padx=15, pady=8)

    # ---- Presets tab ----
    def create_presets_tab(self):
        frame = ctk.CTkFrame(self.tab_presets, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame, text="Gyors kiválasztás", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#f5425a").pack(pady=(10, 20))

        btn_cfg = [
            ("✅ Mindent kijelöl",    self.select_all),
            ("❌ Mindent töröl",      self.deselect_all),
            ("⚡ Minimál (alap)",     self.select_minimal),
            ("🎮 Gamer csomag",       self.select_gamer),
            ("💼 Munkás csomag",      self.select_work),
        ]

        for text, cmd in btn_cfg:
            ctk.CTkButton(frame, text=text, command=cmd,
                          fg_color="#323245", hover_color="#f5425a",
                          font=ctk.CTkFont(size=14), height=40, corner_radius=8).pack(
                fill="x", padx=30, pady=5)

    # ---- Preset helpers ----
    def _set_all(self, value: bool):
        for var in self.check_vars.values():
            var.set(value)

    def select_all(self):
        self._set_all(True)

    def deselect_all(self):
        self._set_all(False)

    def select_minimal(self):
        self.deselect_all()
        for pkg in ["7zip.install", "vlc", "notepadplusplus.install"]:
            if pkg in self.check_vars:
                self.check_vars[pkg].set(True)

    def select_gamer(self):
        self.deselect_all()
        for pkg in ["steam", "discord", "obs-studio", "qbittorrent", "brave", "spotify"]:
            if pkg in self.check_vars:
                self.check_vars[pkg].set(True)

    def select_work(self):
        self.deselect_all()
        for pkg in ["googlechrome", "vscode", "git.install", "7zip.install",
                    "notepadplusplus.install", "libreoffice", "everything.install"]:
            if pkg in self.check_vars:
                self.check_vars[pkg].set(True)

    # ---- Logging / status ----
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
        self.start_btn.configure(state="normal", text="🔄 GÉP ÚJRAINDÍTÁSA", fg_color="#28a745", command=self.restart_pc)
        self.stop_btn.configure(state="disabled")

        msg = f"Sikeres: {len(self.installed_success)}\nSikertelen: {len(self.installed_failed)}"
        if self.installed_failed:
            msg += "\n\nHibák:\n" + "\n".join(f"• {pkg}: {err[:120]}" for pkg, err in self.installed_failed)

        if self.stop_event.is_set():
            msg += "\n\nA folyamat le lett állítva a felhasználó által."

        messagebox.showinfo("Vantax v2.3", f"Folyamat befejezve!\n\n{msg}")

    # ---- System check ----
    def initial_check(self):
        self.choco_path = SystemManager.find_choco()
        if self.choco_path:
            self.safe_update_status("✅ Chocolatey megtalálva – kész a telepítéshez", 0.0)
            self.logger.info(f"Chocolatey: {self.choco_path}")
        else:
            self.safe_update_status("⚠️ Chocolatey nem található (telepíteni fogja)", 0.0)
            self.logger.warning("Chocolatey hiányzik – a folyamat telepíteni fogja.")

    def request_stop(self):
        self.stop_event.set()
        if self.installer:
            self.installer.stop()
        self.logger.info("Leállítás kérve a felhasználótól.")
        self.safe_update_status("Leállítás folyamatban...")

    def start_process(self):
        if platform.system() != "Windows":
            messagebox.showerror("Hiba", "Csak Windows alatt fut!")
            return

        if not SystemManager.is_admin():
            if SystemManager.run_as_admin(sys.argv[0], sys.argv[1:]):
                self.destroy()
                return
            messagebox.showerror("Admin jog szükséges", "Futtasd rendszergazdaként (Run as administrator)!")
            return

        self.stop_event.clear()
        self.installed_success.clear()
        self.installed_failed.clear()

        self.start_btn.configure(state="disabled", text="⏳ DOLGOZOM...")
        self.stop_btn.configure(state="normal")
        self.logger.info("=== Vantax folyamat elindult ===")

        self.worker_thread = threading.Thread(target=self.run_logic, daemon=True)
        self.worker_thread.start()

    def run_logic(self):
        try:
            self.safe_update_status("Rendszer-visszaállítási pont létrehozása...", 0.05)
            SystemManager.run_powershell(
                'Checkpoint-Computer -Description "Vantax pre-install" -RestorePointType "MODIFY_SETTINGS" -ErrorAction SilentlyContinue',
                stop_event=self.stop_event
            )

            if self.stop_event.is_set():
                self.safe_finish()
                return

            if not self.choco_path:
                self.safe_update_status("Chocolatey telepítése...", 0.12)
                if not self.install_chocolatey():
                    self.logger.error("Chocolatey telepítése sikertelen.")
                    self.safe_finish()
                    return
                self.choco_path = SystemManager.find_choco()

            if self.stop_event.is_set():
                self.safe_finish()
                return

            self.safe_update_status("Rendszer tisztítás és optimalizálás...", 0.28)
            self.run_cleanup()

            if self.stop_event.is_set():
                self.safe_finish()
                return

            selected = [cid for cid, var in self.check_vars.items() if var.get()]
            if selected:
                self.logger.info(f"{len(selected)} csomag telepítése...")
                self.installer = PackageInstaller(self.choco_path, self.stop_event, self.logger)

                for i, pkg in enumerate(selected):
                    if self.stop_event.is_set():
                        break
                    prog = 0.35 + 0.6 * (i + 1) / len(selected)
                    self.safe_update_status(f"Telepítés: {pkg} ({i+1}/{len(selected)})", prog)

                    res = self.installer.install(pkg)
                    with self._lock:
                        if res.success:
                            self.installed_success.append(pkg)
                            self.logger.info(f"✓ {pkg} telepítve")
                        else:
                            self.installed_failed.append((pkg, res.error_msg))
                            self.logger.error(f"✗ {pkg} sikertelen: {res.error_msg}")

                self.installer = None
            else:
                self.logger.info("Nincs kiválasztott program.")

            self.safe_update_status("Minden kész!", 1.0)
            self.safe_finish()

        except Exception as e:
            self.logger.error(f"Váratlan hiba: {traceback.format_exc()}")
            self.safe_finish()

    def install_chocolatey(self) -> bool:
        self.logger.info("Chocolatey telepítése hivatalos scripttel...")
        ps_cmd = (
            "Set-ExecutionPolicy Bypass -Scope Process -Force; "
            "[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; "
            "iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"
        )

        code, out, err = SystemManager.run_powershell(ps_cmd, timeout=300, stop_event=self.stop_event)
        if code != 0:
            self.logger.error(f"Choco telepítési hiba: {err}")
            return False

        time.sleep(2)
        self.logger.info("Chocolatey sikeresen telepítve.")
        return True

    def run_cleanup(self):
        # FIX 4: adv_vars.get(key, default_BooleanVar()) always returned a fresh var
        # (never the stored one). Use direct dict lookup with None check instead.
        edge_var = self.adv_vars.get(AdvOption.EDGE)
        if edge_var and edge_var.get():
            SystemOptimizer.remove_edge(self.stop_event, self.logger)

        ai_var = self.adv_vars.get(AdvOption.AI)
        if ai_var and ai_var.get():
            self.logger.info("Copilot letiltása...")
            if SystemOptimizer.disable_copilot(self.stop_event):
                self.logger.info("Copilot tiltva.")
            else:
                self.logger.warning("Copilot tiltása nem teljes.")

        od_var = self.adv_vars.get(AdvOption.ONEDRIVE)
        if od_var and od_var.get():
            self.logger.info("OneDrive letiltása...")
            if SystemOptimizer.disable_onedrive(self.stop_event, self.logger):
                self.logger.info("OneDrive tiltva.")
            else:
                self.logger.warning("OneDrive tiltása nem teljes.")

        tele_var = self.adv_vars.get(AdvOption.TELEMETRY)
        if tele_var and tele_var.get():
            self.logger.info("Telemetria letiltása...")
            if SystemOptimizer.disable_telemetry(self.stop_event):
                self.logger.info("Telemetria tiltva.")
            else:
                self.logger.warning("Telemetria tiltása sikertelen.")

    def restart_pc(self):
        if messagebox.askyesno("Újraindítás", "Biztosan újra akarod indítani most?"):
            subprocess.run(["shutdown", "/r", "/t", "5", "/c", "Vantax optimalizáció kész – újraindítás..."])
            self.destroy()

    def on_closing(self):
        self.stop_event.set()
        if self.installer:
            self.installer.stop()
        self.destroy()


if __name__ == "__main__":
    app = VantaxUI()
    app.mainloop()
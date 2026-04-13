import subprocess
import ctypes
import sys
import os
import threading
import time
from datetime import datetime
import customtkinter as ctk
from tkinter import messagebox

# ====================== KONFIGURÁCIÓ ======================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Az összes elérhető szoftver listája
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

# Chocolatey alapértelmezett elérési útja
CHOCO_EXE = r"C:\ProgramData\chocolatey\bin\choco.exe"

class Vantax(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Vantax v1.1 - Ultimate Installer")
        self.geometry("820x650")
        self.resizable(False, False)
        self.configure(fg_color="#1a1a24")

        self.check_vars = {}
        self.adv_vars = {}
        self.installed_success = []
        self.installed_failed = []

        self.setup_ui()
        # Kezdeti ellenőrzés külön szálon, hogy ne akadjon meg az UI
        threading.Thread(target=self.initial_check, daemon=True).start()

    def setup_ui(self):
        # HEADER SZAKASZ
        header = ctk.CTkFrame(self, fg_color="#1a1a24")
        header.pack(pady=15, padx=35, fill="x")

        ctk.CTkLabel(header, text="VANTAX", font=ctk.CTkFont(size=38, weight="bold"),
                     text_color="#f5425a").pack(side="left")
        ctk.CTkLabel(header, text="v1.1", font=ctk.CTkFont(size=15), text_color="#666").pack(side="left", padx=10)

        # FÜLEK (TABS)
        self.tabview = ctk.CTkTabview(self, fg_color="#252533", segmented_button_fg_color="#323245",
                                      segmented_button_selected_color="#f5425a", corner_radius=12)
        self.tabview.pack(pady=8, padx=35, fill="both", expand=True)

        self.tab_basic = self.tabview.add("PROGRAMOK")
        self.tab_adv = self.tabview.add("RENDSZER")
        self.tab_presets = self.tabview.add("PRESET-ek")

        self.create_app_list()
        self.create_adv_tab()
        self.create_presets_tab()

        # FOLYAMATJELZŐ ÉS GOMBOK
        self.progress = ctk.CTkProgressBar(self, height=10, fg_color="#252533", progress_color="#f5425a")
        self.progress.pack(fill="x", padx=40, pady=(8, 10))
        self.progress.set(0)

        self.start_btn = ctk.CTkButton(self, text="🚀 FOLYAMAT INDÍTÁSA",
                                       font=ctk.CTkFont(size=16, weight="bold"),
                                       fg_color="#f5425a", height=55, corner_radius=12,
                                       command=self.start_process)
        self.start_btn.pack(fill="x", padx=40, pady=12)

        self.status_label = ctk.CTkLabel(self, text="Rendszer ellenőrzése...", text_color="#aaa")
        self.status_label.pack(pady=6)

    def create_app_list(self):
        scroll = ctk.CTkScrollableFrame(self.tab_basic, fg_color="#252533")
        scroll.pack(fill="both", expand=True, padx=15, pady=10)

        # Mindent / Semmit gombok
        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10, padx=10)

        ctk.CTkButton(btn_frame, text="✅ Mindet", width=120, fg_color="#323245",
                      command=self.select_all).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="❌ Semmit", width=120, fg_color="#323245",
                      command=self.deselect_all).pack(side="left", padx=6)

        for cat, apps in APPS_TO_INSTALL.items():
            ctk.CTkLabel(scroll, text=cat.upper(), font=ctk.CTkFont(size=13, weight="bold"),
                         text_color="#f5425a").pack(anchor="w", pady=(18, 6), padx=25)

            for name, cid in apps.items():
                var = ctk.BooleanVar()
                cb = ctk.CTkCheckBox(scroll, text=name, variable=var,
                                   fg_color="#323245", hover_color="#f5425a",
                                   checkbox_width=24, checkbox_height=24)
                cb.pack(anchor="w", pady=5, padx=35)
                self.check_vars[cid] = var

    def create_adv_tab(self):
        self.adv_vars = {
            "edge": ctk.BooleanVar(value=False),
            "ai": ctk.BooleanVar(value=True),
            "one": ctk.BooleanVar(value=True),
            "tele": ctk.BooleanVar(value=True)
        }

        options = [
            ("🗑️ Microsoft Edge eltávolítása", "edge"),
            ("🤖 Windows AI / Copilot letiltása", "ai"),
            ("☁️ OneDrive letiltása", "one"),
            ("📊 Telemetria letiltása", "tele")
        ]

        for text, key in options:
            cb = ctk.CTkCheckBox(self.tab_adv, text=text, variable=self.adv_vars[key],
                               fg_color="#323245", hover_color="#f5425a",
                               checkbox_width=24, checkbox_height=24)
            cb.pack(anchor="w", pady=14, padx=35)

        # Napló (Log) ablak
        log_frame = ctk.CTkFrame(self.tab_adv, fg_color="#1a1a24")
        log_frame.pack(fill="both", expand=True, pady=20, padx=25)
        
        ctk.CTkLabel(log_frame, text="📋 Napló", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=15, pady=8)

        self.log_text = ctk.CTkTextbox(log_frame, height=160, fg_color="#0f0f17",
                                     text_color="#ccc", font=ctk.CTkFont(size=11))
        self.log_text.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def create_presets_tab(self):
        frame = ctk.CTkFrame(self.tab_presets, fg_color="#252533")
        frame.pack(pady=35, padx=50, fill="both", expand=True)

        presets = [
            ("💻 Minimal", "#1f8a70", self.select_minimal),
            ("🎮 Gamer", "#f5425a", self.select_gamer),
            ("🏢 Office", "#3b8ed0", self.select_office),
            ("🎯 Teljes", "#9d4edd", self.select_full)
        ]

        for name, color, cmd in presets:
            btn = ctk.CTkButton(frame, text=name, width=260, height=72,
                              fg_color=color, hover_color=color,
                              font=ctk.CTkFont(size=15, weight="bold"),
                              corner_radius=12, command=cmd)
            btn.pack(pady=11)

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.after(0, lambda: self.log_text.insert("end", f"[{ts}] {msg}\n") or self.log_text.see("end"))

    def update_status(self, text, progress=None):
        self.after(0, lambda: self.status_label.configure(text=text))
        if progress is not None:
            self.after(0, lambda: self.progress.set(progress))

    def select_all(self):
        for v in self.check_vars.values(): v.set(True)

    def deselect_all(self):
        for v in self.check_vars.values(): v.set(False)

    def select_minimal(self):
        self.deselect_all()
        minimal = ["googlechrome", "7zip.install", "vlc", "notepadplusplus.install"]
        for pkg in minimal:
            if pkg in self.check_vars: self.check_vars[pkg].set(True)

    def select_gamer(self):
        self.deselect_all()
        gamer = ["steam", "discord", "spotify", "obs-studio", "qbittorrent"]
        for pkg in gamer:
            if pkg in self.check_vars: self.check_vars[pkg].set(True)

    def select_office(self):
        self.deselect_all()
        office = ["googlechrome", "libreoffice", "notepadplusplus.install", "discord"]
        for pkg in office:
            if pkg in self.check_vars: self.check_vars[pkg].set(True)

    def select_full(self):
        self.select_all()

    def is_choco_installed(self):
        return os.path.exists(CHOCO_EXE)

    def install_chocolatey(self):
        self.log("📦 Chocolatey telepítése folyamatban...")
        ps_cmd = "Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"
        
        try:
            proc = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd], 
                                  capture_output=True, text=True, timeout=300)
            
            # Környezeti változók frissítése az aktuális folyamathoz
            os.environ["PATH"] += os.pathsep + r"C:\ProgramData\chocolatey\bin"
            
            if self.is_choco_installed():
                self.log("✅ Chocolatey sikeresen telepítve!")
                return True
            return False
        except Exception as e:
            self.log(f"❌ Choco hiba: {e}")
            return False

    def initial_check(self):
        if self.is_choco_installed():
            self.update_status("✅ Rendszer kész", 0.0)
            self.log("Chocolatey észlelve.")
        else:
            self.update_status("⚠️ Chocolatey hiányzik", 0.0)
            self.log("Chocolatey nem található a rendszerben.")

    def start_process(self):
        if not ctypes.windll.shell32.IsUserAnAdmin():
            messagebox.showerror("Hiba", "Kérlek, futtasd a programot Rendszergazdaként!")
            return

        self.start_btn.configure(state="disabled", text="⏳ DOLGOZOM...")
        self.log_text.delete("1.0", "end")
        self.installed_success.clear()
        self.installed_failed.clear()

        threading.Thread(target=self.run_logic, daemon=True).start()

    def run_logic(self):
        self.log("🚀 Vantax folyamat elindult")
        
        # 1. Choco ellenőrzés/telepítés
        if not self.is_choco_installed():
            self.update_status("Chocolatey telepítése...", 0.1)
            if not self.install_chocolatey():
                messagebox.showerror("Hiba", "Nem sikerült telepíteni a Chocolatey-t!")
                self.finish_ui(False)
                return
        
        # 2. Rendszer optimalizálások (Registry / Cleanup)
        self.update_status("Rendszer beállítása...", 0.25)
        self.run_cleanup()

        # 3. Szoftverek telepítése
        selected = [cid for cid, var in self.check_vars.items() if var.get()]
        total = len(selected)

        if selected:
            self.log(f"📦 {total} szoftver telepítése/frissítése következik...")
            for i, pkg in enumerate(selected):
                progress = 0.3 + (0.65 * (i + 1) / total)
                self.update_status(f"Telepítés: {pkg} ({i+1}/{total})", progress)
                
                if self.install_package(pkg):
                    self.installed_success.append(pkg)
                    self.log(f"✅ {pkg} sikeresen lefutott.")
                else:
                    self.installed_failed.append(pkg)
                    self.log(f"❌ {pkg} telepítése nem sikerült.")
        else:
            self.log("ℹ️ Nincs kiválasztott szoftver.")

        self.update_status("Kész!", 1.0)
        self.finish_ui(True)

    def install_package(self, pkg):
        """Kényszerített újratelepítés/frissítés végrehajtása."""
        try:
            # 'upgrade' parancs a '--force' kapcsolóval kényszeríti az újraletöltést
            cmd = [CHOCO_EXE, "upgrade", pkg, "-y", "--force", "--limit-output", "--no-progress"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
            return result.returncode == 0
        except Exception as e:
            self.log(f"Hiba {pkg} közben: {e}")
            return False

    def run_cleanup(self):
        # Edge eltávolítás
        if self.adv_vars["edge"].get():
            self.log("🗑️ Edge eltávolítása...")
            ps_cmd = 'Get-AppxPackage *Edge* | Remove-AppxPackage -ErrorAction SilentlyContinue'
            subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
            self.log("✅ Edge eltávolítva.")

        # AI / Copilot tiltás
        if self.adv_vars["ai"].get():
            self.log("🤖 Copilot letiltása...")
            subprocess.run(['reg', 'add', r'HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot', '/v', 'TurnOffWindowsCopilot', '/t', 'REG_DWORD', '/d', '1', '/f'], capture_output=True)
            self.log("✅ Copilot tiltva.")

        # OneDrive tiltás
        if self.adv_vars["one"].get():
            self.log("☁️ OneDrive leállítása...")
            subprocess.run(['taskkill', '/f', '/im', 'OneDrive.exe'], capture_output=True)
            subprocess.run(['reg', 'add', r'HKLM\SOFTWARE\Policies\Microsoft\Windows\OneDrive', '/v', 'DisableFileSyncNGSC', '/t', 'REG_DWORD', '/d', '1', '/f'], capture_output=True)
            self.log("✅ OneDrive tiltva.")

        # Telemetria tiltás
        if self.adv_vars["tele"].get():
            self.log("📊 Telemetria kikapcsolva...")
            subprocess.run(['reg', 'add', r'HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection', '/v', 'AllowTelemetry', '/t', 'REG_DWORD', '/d', '0', '/f'], capture_output=True)
            self.log("✅ Telemetria tiltva.")

    def finish_ui(self, success):
        # Gomb átalakítása újraindítássá
        self.after(0, lambda: self.start_btn.configure(
            state="normal", 
            text="🔄 GÉP ÚJRAINDÍTÁSA", 
            fg_color="#28a745", 
            command=self.restart_pc
        ))
        
        res_msg = f"Sikeres: {len(self.installed_success)}\nSikertelen: {len(self.installed_failed)}"
        if self.installed_failed:
            res_msg += "\n\nHibás csomagok:\n" + "\n".join(self.installed_failed)
            
        messagebox.showinfo("Vantax", f"A folyamat befejeződött!\n\n{res_msg}")

    def restart_pc(self):
        if messagebox.askyesno("Újraindítás", "Biztosan újra szeretnéd indítani a számítógépet most?"):
            subprocess.run('shutdown /r /t 5 /c "Vantax optimalizáció befejezése..."', shell=True)
            self.destroy()

if __name__ == "__main__":
    if not ctypes.windll.shell32.IsUserAnAdmin():
        # Újraindítás admin módban, ha szükséges
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"', None, 1)
    else:
        app = Vantax()
        app.mainloop()
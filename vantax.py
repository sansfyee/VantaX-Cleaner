import subprocess
import ctypes
import sys
import os
import threading
from datetime import datetime
import customtkinter as ctk
from tkinter import messagebox

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ====================== APP LISTA ======================
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

class Vantax(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Vantax v1.2")
        self.geometry("560x780")
        self.resizable(False, False)
        self.configure(fg_color="#1a1a24")

        self.check_vars = {}
        self.adv_vars = {}
        self.installed_success = []
        self.installed_failed = []
        self.choco_path = r"C:\ProgramData\chocolatey\bin\choco.exe"

        self.setup_ui()
        threading.Thread(target=self.initial_check, daemon=True).start()

    def setup_ui(self):
        # HEADER
        header = ctk.CTkFrame(self, fg_color="#1a1a24")
        header.pack(pady=15, padx=25, fill="x")
        ctk.CTkLabel(header, text="VANTAX", font=ctk.CTkFont(size=38, weight="bold"),
                     text_color="#f5425a").pack(side="left")
        ctk.CTkLabel(header, text="v1.2", font=ctk.CTkFont(size=15), text_color="#666").pack(side="left", padx=8)

        # TABS
        self.tabview = ctk.CTkTabview(self, fg_color="#252533", segmented_button_fg_color="#323245",
                                      segmented_button_selected_color="#f5425a", corner_radius=12)
        self.tabview.pack(pady=8, padx=25, fill="both", expand=True)

        self.tab_basic = self.tabview.add("PROGRAMOK")
        self.tab_adv = self.tabview.add("RENDSZER")
        self.tab_presets = self.tabview.add("PRESET-ek")

        self.create_app_list()
        self.create_adv_tab()
        self.create_presets_tab()

        # PROGRESS + BUTTONS
        self.progress = ctk.CTkProgressBar(self, height=10, fg_color="#252533", progress_color="#f5425a")
        self.progress.pack(fill="x", padx=30, pady=(5, 8))
        self.progress.set(0)

        self.start_btn = ctk.CTkButton(self, text="🚀 TELEPÍTÉS INDÍTÁSA",
                                       font=ctk.CTkFont(size=16, weight="bold"),
                                       fg_color="#f5425a", height=52, corner_radius=12,
                                       command=self.start_process)
        self.start_btn.pack(fill="x", padx=30, pady=12)

        self.status_label = ctk.CTkLabel(self, text="Ellenőrzés folyamatban...", text_color="#aaa")
        self.status_label.pack(pady=5)

    def create_app_list(self):
        scroll = ctk.CTkScrollableFrame(self.tab_basic, fg_color="#252533")
        scroll.pack(fill="both", expand=True, padx=15, pady=10)

        # BUTTONS
        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.pack(fill="x", pady=8)
        ctk.CTkButton(btn_frame, text="✅ Mindet", width=100, fg_color="#323245", 
                     command=self.select_all).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="❌ Semmit", width=100, fg_color="#323245", 
                     command=self.deselect_all).pack(side="left", padx=5)

        # APPS
        for cat, apps in APPS_TO_INSTALL.items():
            ctk.CTkLabel(scroll, text=cat.upper(), font=ctk.CTkFont(size=13, weight="bold"),
                         text_color="#f5425a").pack(anchor="w", pady=(15, 5), padx=20)
            for name, cid in apps.items():
                var = ctk.BooleanVar()
                cb = ctk.CTkCheckBox(scroll, text=name, variable=var,
                                   fg_color="#323245", hover_color="#f5425a",
                                   checkbox_width=22, checkbox_height=22)
                cb.pack(anchor="w", pady=4, padx=28)
                self.check_vars[cid] = var

    def create_adv_tab(self):
        # ADVANCED OPTIONS
        self.adv_vars = {
            "edge": ctk.BooleanVar(value=True),
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
                               fg_color="#323245", hover_color="#f5425a")
            cb.pack(anchor="w", pady=11, padx=25)

        # LOG
        log_frame = ctk.CTkFrame(self.tab_adv, fg_color="#1a1a24")
        log_frame.pack(fill="both", expand=True, pady=15, padx=20)
        ctk.CTkLabel(log_frame, text="📋 Napló", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=15, pady=6)
        
        self.log_text = ctk.CTkTextbox(log_frame, height=160, fg_color="#0f0f17", 
                                     text_color="#ccc", font=ctk.CTkFont(size=11))
        self.log_text.pack(fill="both", expand=True, padx=15, pady=(0,10))
        self.log("Vantax v1.2 elindult - Készen áll!")

    def create_presets_tab(self):
        frame = ctk.CTkFrame(self.tab_presets, fg_color="#252533")
        frame.pack(pady=30, padx=30, fill="both", expand=True)
        
        presets = [
            ("💻 Minimal", "#1f8a70", self.select_minimal),
            ("🎮 Gamer", "#f5425a", self.select_gamer),
            ("🏢 Office", "#3b8ed0", self.select_office),
            ("🎯 Teljes", "#9d4edd", self.select_full)
        ]
        for name, color, cmd in presets:
            btn = ctk.CTkButton(frame, text=name, width=220, height=65, fg_color=color, 
                              font=ctk.CTkFont(size=14, weight="bold"), hover_color=color, 
                              command=cmd, corner_radius=12)
            btn.pack(pady=12)

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
        return os.path.exists(self.choco_path)

    def install_chocolatey(self):
        self.log("📦 Chocolatey telepítése...")
        self.update_status("Chocolatey telepítés...", 0.2)

        ps_script = r'''
Set-ExecutionPolicy Bypass -Scope Process -Force;
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072;
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
'''
        try:
            result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                                  capture_output=True, text=True, timeout=180)
            
            # Újraindítjuk a choco keresést
            if os.path.exists(self.choco_path):
                self.log("✅ Chocolatey sikeresen telepítve!")
                os.environ["PATH"] += f";{os.path.dirname(self.choco_path)}"
                return True
            else:
                self.log("❌ Chocolatey telepítés sikertelen")
                return False
        except subprocess.TimeoutExpired:
            self.log("❌ Chocolatey telepítés TIMEOUT")
            return False
        except Exception as e:
            self.log(f"❌ Chocolatey hiba: {str(e)[:100]}")
            return False

    def initial_check(self):
        if self.is_choco_installed():
            self.update_status("✅ Készen áll - Chocolatey OK!", 0.0)
            self.log("Chocolatey elérhető.")
        else:
            self.update_status("Chocolatey szükséges...", 0.0)
            self.log("Chocolatey telepítés szükséges.")

    def start_process(self):
        if not ctypes.windll.shell32.IsUserAnAdmin():
            messagebox.showerror("Hiba", "Futtasd ADMINISZTRÁTORKÉNT!")
            return
            
        self.start_btn.configure(state="disabled", text="⏳ FOLYAMATBAN...")
        self.log_text.delete("1.0", "end")
        self.installed_success.clear()
        self.installed_failed.clear()
        threading.Thread(target=self.run_logic, daemon=True).start()

    def run_logic(self):
        self.log("🚀 Vantax v1.2 - FŐ FOLYAMAT INDUL")
        self.update_status("Kezdés...", 0.05)

        # 1. CHOCOLATEY
        if not self.is_choco_installed():
            if not self.install_chocolatey():
                self.after(0, lambda: messagebox.showerror("Hiba", "Chocolatey telepítés sikertelen!"))
                self.finish_ui(False)
                return

        self.update_status("Rendszer optimalizálás...", 0.3)
        
        # 2. CLEANUP
        self.run_cleanup()

        # 3. PROGRAM TELEPÍTÉS - EGYBEN!
        self.update_status("Program telepítések...", 0.6)
        selected = [cid for cid, var in self.check_vars.items() if var.get()]
        
        if selected:
            self.log(f"📦 {len(selected)} program kiválasztva")
            pkgs = " ".join(selected)
            cmd = f'"{self.choco_path}" install {pkgs} -y --force --no-progress --timeout=1200'
            
            try:
                self.log(f"Choco parancs: {cmd[:80]}...")
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2400)
                
                if result.returncode == 0:
                    self.installed_success = selected[:]
                    self.log("✅ ÖSSZES program telepítve!")
                else:
                    self.installed_failed = selected[:]
                    self.log(f"❌ Telepítési hibák (kód: {result.returncode})")
                    if result.stderr:
                        self.log(f"Hibák: {result.stderr[-300:]}")
                        
            except Exception as e:
                self.installed_failed = selected[:]
                self.log(f"❌ Kritikus hiba: {str(e)}")
        else:
            self.log("ℹ️ Nincs kiválasztott program")

        self.update_status("Kész!", 1.0)
        self.log("🎉 VANTAX v1.2 BEFEJEZVE!")
        self.finish_ui(True)

    def run_cleanup(self):
        if self.adv_vars["edge"].get():
            self.log("🗑️ Edge eltávolítás...")
            ps_cmd = 'Get-AppxPackage *Edge* | Remove-AppxPackage -ErrorAction SilentlyContinue; Get-AppxProvisionedPackage -Online | ? {$_.DisplayName -like "*Edge*"} | Remove-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue'
            subprocess.run(f'powershell -Command "{ps_cmd}"', shell=True, capture_output=True, timeout=60)
            self.log("✅ Edge törölve")

        if self.adv_vars["ai"].get():
            self.log("🤖 AI tiltás...")
            subprocess.run(['reg', 'add', r'HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot', '/v', 'TurnOffWindowsCopilot', '/t', 'REG_DWORD', '/d', '1', '/f'], 
                          capture_output=True)
            self.log("✅ AI tiltva")

        if self.adv_vars["one"].get():
            self.log("☁️ OneDrive...")
            subprocess.run(['taskkill', '/f', '/im', 'OneDrive.exe'], capture_output=True, timeout=10)
            subprocess.run(['reg', 'add', r'HKLM\SOFTWARE\Policies\Microsoft\Windows\OneDrive', '/v', 'DisableFileSyncNGSC', '/t', 'REG_DWORD', '/d', '1', '/f'], 
                          capture_output=True)
            self.log("✅ OneDrive tiltva")

        if self.adv_vars["tele"].get():
            self.log("📊 Telemetria...")
            subprocess.run(['reg', 'add', r'HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection', '/v', 'AllowTelemetry', '/t', 'REG_DWORD', '/d', '0', '/f'], 
                          capture_output=True)
            self.log("✅ Telemetria kikapcsolva")

    def finish_ui(self, success):
        self.after(0, lambda: self.start_btn.configure(
            state="normal",
            text="🔄 ÚJRAINDÍTÁS",
            fg_color="#28a745",
            command=self.restart_pc
        ))
        summary = f"Sikeres: {len(self.installed_success)}\\nSikertelen: {len(self.installed_failed)}"
        self.after(0, lambda: messagebox.showinfo("✅ Vantax v1.2", 
            f"Folyamat kész!\n\n{summary}\n\n🔄 ÚJRAINDÍTÁS AJÁNLOTT!"))

    def restart_pc(self):
        if messagebox.askyesno("Újraindítás", "Biztosan újraindítod a PC-t?"):
            subprocess.run('shutdown /r /t 10 /c "Vantax: Újraindítás 10 mp múlva..."', shell=True)
            self.destroy()

if __name__ == "__main__":
    if not ctypes.windll.shell32.IsUserAnAdmin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"', None, 1)
    else:
        app = Vantax()
        app.mainloop()
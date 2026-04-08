import subprocess
import ctypes
import sys
import os
import threading
import tkinter as tk
from tkinter import ttk


# Hol van a saját .exe vagy .py (ahol az installers is lesz)
def get_base_dir():
    if getattr(sys, 'frozen', False):
        # Ha .exe-ből fut (pyinstaller)
        return os.path.dirname(sys.executable)
    else:
        # Ha python tisztito.py-ként
        return os.path.dirname(os.path.abspath(__file__))


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_ps(cmd):
    print(f"  -> {cmd}")
    process = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
        capture_output=True,
        text=True,
        encoding='cp1250'
    )
    if process.returncode == 0:
        if process.stdout.strip():
            print(process.stdout.strip())
        print("  [OK] Sikeres művelet\n")
    else:
        print(f"  [!] Hiba: {process.stderr.strip()}\n")


def run_installers():
    base_dir = get_base_dir()
    installer_dir = os.path.join(base_dir, "installers")

    if not os.path.exists(installer_dir):
        print(f"⚠️  Nincs installers mappa: {installer_dir}")
        return

    installers = []
    for file in os.listdir(installer_dir):
        if file.lower().endswith((".exe", ".msi")):
            installers.append(os.path.join(installer_dir, file))

    if not installers:
        print("⚠️  Nincs telepítő .exe vagy .msi az installers mappában.")
        return

    print(f"\n✅ Telepítők futtatása ({len(installers)} fájl):")
    for exe_path in installers:
        print(f"  → Futtatás: {exe_path}")
        try:
            if exe_path.lower().endswith(".msi"):
                subprocess.run(["msiexec", "/i", exe_path], shell=True, check=True)
            else:
                subprocess.run([exe_path], shell=True, check=True)
        except Exception as e:
            print(f"  [!] Hiba a telepítőnél: {exe_path}\n      {e}")

    print("  [OK] Az installers mappában lévő telepítők lefutottak.\n")


# --- Elegáns, "nagy cég" stílusú GUI ablak (VANTAX Cleaning)
def create_gui(root):
    # Modern, elegáns szín - nem csak piros
    bg_color = "#2c2f33"  # Dark gray (Discord / modern app)
    fg_color = "#ffffff"  # Fehér szöveg
    accent_color = "#f5425a"  # Halvány piros accent
    font_color = fg_color

    # Ablak beállítások
    root.title("VANTAX Cleaning")
    root.geometry("750x400")
    root.resizable(False, False)
    root.configure(bg=bg_color)
    root.attributes("-topmost", True)

    # Fő cím
    title = tk.Label(
        root,
        text="VANTAX Cleaning",
        font=("Segoe UI Semibold", 22),
        fg=accent_color,
        bg=bg_color
    )
    title.pack(pady=15)

    # Részletes leírás
    subtitle = tk.Label(
        root,
        text="Optimalizálja a Windows 11 rendszerét és eltávolítja a szemét alkalmazásokat.\n" \
             "A folyamat végén a telepítők automatikusan indulnak.",
        font=("Segoe UI", 11),
        fg=font_color,
        bg=bg_color,
        justify="center"
    )
    subtitle.pack(pady=10)

    # Indikátor (ProgressBar)
    progress = ttk.Style()
    progress.theme_use("default")
    progress.configure("Horizontal.TProgressbar", thickness=8)
    progress = ttk.Progressbar(
        root,
        mode="indeterminate",
        length=350,
        style="Horizontal.TProgressbar"
    )
    progress.pack(pady=25)
    progress.start()

    # Alul jobb sarokban kis cég stílusú logo szöveg (opcionális)
    footer = tk.Label(
        root,
        text="© 2026 VANTAX Technologies",
        font=("Segoe UI", 9),
        fg="#a9a9a9",
        bg=bg_color
    )
    footer.pack(side="bottom", pady=10)


# --- Windows tuning + Firefox (csak Firefox) + installers
def run_optimization():
    if not is_admin():
        print("❌ HIBA: Ezt a scriptet Rendszergazdaként kell futtatni!")
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

    print("\n[0/8] Winget források frissítése...")
    run_ps("winget source update")

    print("\n[1/8] Rendszer-visszaállítási pont...")
    run_ps("Checkpoint-Computer -Description 'Vantax_PONT' -RestorePointType 'MODIFY_SETTINGS' -ErrorAction SilentlyContinue")

    print("\n[2/8] Felesleges alkalmazások eltávolítása (Bing, Store, stb.)...")
    apps_to_remove = [
        "Microsoft.BingNews",
        "Microsoft.BingWeather",
        "Microsoft.ZuneVideo",
        "Microsoft.GamingApp",
        "Microsoft.GetHelp",
        "Microsoft.Getstarted",
        "Microsoft.People",
        "Microsoft.WindowsFeedbackHub",
        "Microsoft.WindowsStore",          # Microsoft Store eltávolítása
    ]
    for app in apps_to_remove:
        print(f" Törlés: {app}")
        run_ps(f"Get-AppxPackage -AllUsers *{app}* | Remove-AppxPackage -ErrorAction SilentlyContinue")

    # ----- Microsoft Edge eltávolítása -----
    print("\n[2/9] Microsoft Edge eltávolítása...")
    run_ps("Get-AppxPackage -AllUsers *MicrosoftEdge* | Remove-AppxPackage -ErrorAction SilentlyContinue")

    print("\n[3/8] OneDrive eltávolítása...")
    run_ps("winget uninstall --id Microsoft.OneDrive --accept-source-agreements")

    print("\n[4/8] Cortana és Telemetria tiltása...")
    run_ps("Get-AppxPackage -allusers *Microsoft.549981C32F157* | Remove-AppxPackage -ErrorAction SilentlyContinue")
    run_ps("if (!(Test-Path 'HKLM:\\\\SOFTWARE\\\\Policies\\\\Microsoft\\\\Windows\\\\DataCollection')) { New-Item -Path 'HKLM:\\\\SOFTWARE\\\\Policies\\\\Microsoft\\\\Windows\\\\DataCollection' -Force }")
    run_ps("Set-ItemProperty -Path 'HKLM:\\\\SOFTWARE\\\\Policies\\\\Microsoft\\\\Windows\\\\DataCollection' -Name 'AllowTelemetry' -Value 0")
    run_ps("Stop-Service -Name 'DiagTrack' -Force; Set-Service -Name 'DiagTrack' -StartupType Disabled")

    print("\n[5/8] Verbose logon (részletes bejelentkezés) engedélyezése...")
    run_ps("Set-ItemProperty -Path 'HKLM:\\\\SOFTWARE\\\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' -Name 'VerboseStatus' -Value 1")

    print("\n[6/8] Classic context menu (Windows 11) engedélyezése...")
    run_ps("New-Item -Path 'HKCU:\\\\Software\\\\Microsoft\\\\Windows\\CurrentVersion\\Applets\\Regedit\\Favorites' -Force -ErrorAction SilentlyContinue")
    run_ps("New-Item -Path 'HKCU:\\\\Software\\\\Classes\\\\CLSID\\\\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}' -Force -ErrorAction SilentlyContinue")
    run_ps("New-Item -Path 'HKCU:\\\\Software\\\\Classes\\\\CLSID\\\\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\\InprocServer32' -Force -ErrorAction SilentlyContinue")
    run_ps("Set-ItemProperty -Path 'HKCU:\\\\Software\\\\Classes\\\\CLSID\\\\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\\InprocServer32' -Name '(Default)' -Value ''")
    run_ps("Set-ItemProperty -Path 'HKCU:\\\\Software\\\\Classes\\\\CLSID\\\\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\\InprocServer32' -Name 'ThreadingModel' -Value 'Apartment'")
    run_ps("Set-ItemProperty -Path 'HKCU:\\\\Software\\\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced' -Name 'LaunchTo' -Value 1")
    run_ps("Stop-Process -Name explorer -Force")

    print("\n[7/8] Firefox telepítése (csak Firefox a telepítők közül)...")
    run_ps("winget install --id Mozilla.Firefox -e --source winget --accept-source-agreements --accept-package-agreements")

    print("\n[8/8] Disable Sticky hotkeys...")
    run_ps("Set-ItemProperty -Path 'HKCU:\\\\Control Panel\\Accessibility\\StickyKeys' -Name 'Flags' -Value '506'")
    run_ps("Set-ItemProperty -Path 'HKCU:\\\\Control Panel\\Accessibility\\FilterKeys' -Name 'Flags' -Value '122'")
    run_ps("Set-ItemProperty -Path 'HKCU:\\\\Control Panel\\Accessibility\\ToggleKeys' -Name 'Flags' -Value '58'")

    print("\n[9/9] Telepítők futtatása az installers mappából (csak Firefox, a többi a felhasználó által telepítendő)...")
    run_installers()

    print("\n" + "="*40)
    print("A folyamat befejeződött!")
    print("Javasolt egy újraindítás a változtatások érvényesítéséhez.")
    print("Most már bezárhatod ezt az ablakot.")


# --- Fő entry point (VANTAX Cleaning + installer launcher)
def main():
    root = tk.Tk()
    root.protocol("WM_DELETE_WINDOW", lambda: None)  # X-re ne lehessen bezárni
    create_gui(root)

    opt_thread = threading.Thread(target=run_optimization, daemon=True)
    opt_thread.start()

    def check_if_done():
        if not opt_thread.is_alive():
            # Letesztjük, hogy a szál már megállt-e
            close_btn = tk.Button(
                root,
                text="Bezárás",
                font=("Segoe UI", 11),
                bg="#f5425a",  # Red accent
                fg="#ffffff",
                relief="flat",
                command=root.destroy
            )
            close_btn.pack(pady=10)
        else:
            root.after(500, check_if_done)  # 0.5 másodpercenként újra ellenőriz

    root.after(500, check_if_done)
    root.mainloop()


if __name__ == "__main__":
    main()
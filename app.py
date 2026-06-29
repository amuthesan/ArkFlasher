#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.scrolledtext as scrolledtext
import os
import re
import threading
import subprocess
import queue
import time
import sys
import urllib.request
import json
import zipfile
import io

# Attempt dynamic load of serial and esptool, offering auto-installation with Pep668 override fallbacks
required_packages = []

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    required_packages.append("pyserial")

esptool_found = False
try:
    import esptool
    esptool_found = True
except ImportError:
    # Try looking if it is on the PATH
    try:
        subprocess.run(['esptool', '-h'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        esptool_found = True
    except FileNotFoundError:
        try:
            subprocess.run(['esptool.py', '-h'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            esptool_found = True
        except FileNotFoundError:
            pass

if not esptool_found:
    required_packages.append("esptool")

if required_packages:
    install_commands = [
        [sys.executable, "-m", "pip", "install"] + required_packages,
        [sys.executable, "-m", "pip", "install"] + required_packages + ["--break-system-packages"],
        [sys.executable, "-m", "pip", "install"] + required_packages + ["--user"],
        [sys.executable, "-m", "pip", "install"] + required_packages + ["--user", "--break-system-packages"]
    ]
    for cmd in install_commands:
        try:
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            break
        except Exception:
            continue

    # Attempt re-import
    try:
        import serial
        import serial.tools.list_ports
    except ImportError:
        serial = None
else:
    try:
        import serial
        import serial.tools.list_ports
    except ImportError:
        serial = None

# Color Palette (Catppuccin Mocha-inspired premium dark theme)
BG_MAIN = "#181825"        # Base background
BG_CARD = "#1e1e2e"        # Surface
BG_INPUT = "#313244"       # Input field
FG_MAIN = "#cdd6f4"        # Text
FG_MUTED = "#a6adc8"       # Labels / Subtext
ACCENT = "#89b4fa"         # Sky/Lavender blue
ACCENT_HOVER = "#b4befe"   # Lighter sky blue
ACCENT_GREEN = "#a6e3a1"   # Success green
ACCENT_YELLOW = "#f9e2af"  # Warning yellow
ACCENT_RED = "#f38ba8"     # Error red
BG_BUTTON = "#89b4fa"
FG_BUTTON = "#11111b"
BG_BUTTON_DISABLED = "#313244"
FG_BUTTON_DISABLED = "#7f849c"

class ArkFlasherGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Ark Flasher (esptool wrapper)")
        self.root.geometry("1180x820")
        self.root.configure(bg=BG_MAIN)
        self.root.resizable(True, True)

        # Thread queue for logging and operations
        self.log_queue = queue.Queue()

        # Parsed flashing binaries payload: list of (hex_address, absolute_path_to_bin)
        self.parsed_binaries = []
        
        # GitHub releases cache
        self.github_releases = []
        self.github_owner = None
        self.github_repo = None
        self.cached_repo_dir = None
        self.github_token_var = tk.StringVar(value=os.environ.get("GITHUB_TOKEN", ""))

        # Configure fonts
        self.font_sans = ("Helvetica Neue", 11)
        self.font_sans_bold = ("Helvetica Neue", 11, "bold")
        self.font_title = ("Helvetica Neue", 12, "bold")
        self.font_mono = ("Menlo", 10)

        # Configure styles
        self.setup_styles()

        # Create Layout
        self.build_ui()

        # Init COM port dropdown
        self.refresh_ports()

        # Start checking incoming logs from back-end threads
        self.root.after(100, self.process_log_queue)

        self.log("Application started successfully.", "cyan")
        self.log("Configure a local folder or paste a GitHub URL to start.", "muted")

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        # Customize Combobox
        style.configure("TCombobox", 
                        fieldbackground=BG_INPUT, 
                        background=BG_CARD, 
                        foreground=FG_MAIN, 
                        arrowcolor=ACCENT, 
                        bordercolor=BG_INPUT,
                        lightcolor=BG_INPUT,
                        darkcolor=BG_INPUT)
        style.map("TCombobox", 
                  fieldbackground=[("readonly", BG_INPUT)],
                  foreground=[("readonly", FG_MAIN)],
                  arrowcolor=[("readonly", ACCENT)],
                  selectbackground=[("readonly", BG_INPUT)],
                  selectforeground=[("readonly", FG_MAIN)])

        # Customize Checkbutton
        style.configure("TCheckbutton", 
                        background=BG_CARD, 
                        foreground=FG_MAIN,
                        focuscolor=BG_CARD)
        style.map("TCheckbutton", 
                  background=[("active", BG_CARD)], 
                  foreground=[("active", FG_MAIN)])

    def build_ui(self):
        # Main outer frame with padding
        main_frame = tk.Frame(self.root, bg=BG_MAIN)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # --- LEFT SIDEBAR (Controls Column - width 380px) ---
        left_frame = tk.Frame(main_frame, bg=BG_MAIN, width=390)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        left_frame.pack_propagate(False)

        # Left Pane Title Header Banner
        banner_lbl = tk.Label(left_frame, text="ARK FLASHER", font=("Helvetica Neue", 14, "bold"), bg=BG_MAIN, fg=ACCENT)
        banner_lbl.pack(anchor=tk.W, pady=(0, 15))

        # Card 1: Project Source Input
        source_card = self.create_card(left_frame, "1. PROJECT WORKSPACE")
        
        lbl_dir = tk.Label(source_card, text="Path or GitHub Repo URL:", font=self.font_sans_bold, bg=BG_CARD, fg=FG_MAIN)
        lbl_dir.pack(anchor=tk.W, pady=(0, 5))

        self.project_path_var = tk.StringVar()
        self.entry_dir = tk.Entry(source_card, textvariable=self.project_path_var, bg=BG_INPUT, fg=FG_MAIN, 
                                  insertbackground=FG_MAIN, relief="flat", bd=1, highlightbackground=BG_INPUT, 
                                  highlightcolor=ACCENT, highlightthickness=1, font=self.font_sans)
        self.entry_dir.pack(fill=tk.X, pady=(0, 10))

        lbl_token = tk.Label(source_card, text="GitHub Token (Optional):", font=self.font_sans_bold, bg=BG_CARD, fg=FG_MAIN)
        lbl_token.pack(anchor=tk.W, pady=(0, 5))

        self.entry_token = tk.Entry(source_card, textvariable=self.github_token_var, bg=BG_INPUT, fg=FG_MAIN, 
                                    insertbackground=FG_MAIN, relief="flat", bd=1, highlightbackground=BG_INPUT, 
                                    highlightcolor=ACCENT, highlightthickness=1, font=self.font_sans, show="*")
        self.entry_token.pack(fill=tk.X, pady=(0, 10))

        # Horizontal layout for browse / load button
        src_btn_frame = tk.Frame(source_card, bg=BG_CARD)
        src_btn_frame.pack(fill=tk.X)

        self.btn_browse = tk.Button(src_btn_frame, text="Browse Folder...", font=self.font_sans_bold, bg=BG_BUTTON, fg=FG_BUTTON,
                                    activebackground=ACCENT_HOVER, activeforeground=FG_BUTTON, relief="flat", bd=0, 
                                    padx=10, pady=4, cursor="hand2", command=self.browse_project_folder)
        self.btn_browse.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        self.btn_load_src = tk.Button(src_btn_frame, text="Load / Sync", font=self.font_sans_bold, bg=ACCENT_GREEN, fg=FG_BUTTON,
                                     activebackground="#c2f0c2", activeforeground=FG_BUTTON, relief="flat", bd=0, 
                                     padx=10, pady=4, cursor="hand2", command=self.load_source)
        self.btn_load_src.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

        # Card 2: GitHub Release Control (collapsible/reactive)
        self.git_card = self.create_card(left_frame, "2. GITHUB VERSION DESIGN")
        
        self.lbl_git_versions = tk.Label(self.git_card, text="Release Version Tag:", font=self.font_sans_bold, bg=BG_CARD, fg=FG_MUTED)
        self.lbl_git_versions.pack(anchor=tk.W, pady=(0, 5))

        self.selected_git_version_var = tk.StringVar()
        self.combo_git_version = ttk.Combobox(self.git_card, textvariable=self.selected_git_version_var, state="disabled", font=self.font_sans)
        self.combo_git_version.pack(fill=tk.X, pady=(0, 10))

        self.btn_git_download = tk.Button(self.git_card, text="Download & Import Version", font=self.font_sans_bold, 
                                          bg=BG_BUTTON_DISABLED, fg=FG_BUTTON_DISABLED, state=tk.DISABLED, relief="flat", bd=0, 
                                          pady=5, command=self.start_github_download)
        self.btn_git_download.pack(fill=tk.X)

        # Card 3: Target Board & System COM
        setup_card = self.create_card(left_frame, "3. HARDWARE CONFIGS")

        lbl_board = tk.Label(setup_card, text="Target Board Config:", font=self.font_sans_bold, bg=BG_CARD, fg=FG_MAIN)
        lbl_board.pack(anchor=tk.W, pady=(0, 5))

        self.selected_board_var = tk.StringVar()
        self.combo_board = ttk.Combobox(setup_card, textvariable=self.selected_board_var, state="disabled", font=self.font_sans)
        self.combo_board.pack(fill=tk.X, pady=(0, 10))
        self.combo_board.bind("<<ComboboxSelected>>", self.on_board_selected)

        lbl_port = tk.Label(setup_card, text="Serial COM Port:", font=self.font_sans_bold, bg=BG_CARD, fg=FG_MAIN)
        lbl_port.pack(anchor=tk.W, pady=(0, 5))

        port_subframe = tk.Frame(setup_card, bg=BG_CARD)
        port_subframe.pack(fill=tk.X)

        self.selected_port_var = tk.StringVar()
        self.combo_port = ttk.Combobox(port_subframe, textvariable=self.selected_port_var, state="readonly", font=self.font_sans, width=15)
        self.combo_port.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.combo_port.bind("<<ComboboxSelected>>", lambda e: self.update_flash_button_state())

        self.btn_refresh_ports = tk.Button(port_subframe, text="⟳", font=("Helvetica Neue", 12, "bold"), bg=BG_BUTTON, 
                                           fg=FG_BUTTON, activebackground=ACCENT_HOVER, activeforeground=FG_BUTTON, 
                                           relief="flat", bd=0, padx=6, pady=2, cursor="hand2", command=self.refresh_ports)
        self.btn_refresh_ports.pack(side=tk.LEFT, padx=(5, 0))

        # Card 4: Action Flasher
        action_card = self.create_card(left_frame, "4. PROGRAMMER FLASHER")

        self.is_dry_run_var = tk.BooleanVar(value=True)
        self.sim_check = ttk.Checkbutton(action_card, text="Simulate Flash (Dry Run / Test)", variable=self.is_dry_run_var, style="TCheckbutton")
        self.sim_check.pack(anchor=tk.W, pady=(0, 10))

        self.btn_flash = tk.Button(action_card, text="Flash Target Board", font=("Helvetica Neue", 12, "bold"), 
                                   bg=BG_BUTTON_DISABLED, fg=FG_BUTTON_DISABLED, relief="flat", bd=0, 
                                   pady=8, state=tk.DISABLED, command=self.start_flash)
        self.btn_flash.pack(fill=tk.X)

        # --- RIGHT COLUMN (Details & Live Logs Console) ---
        right_frame = tk.Frame(main_frame, bg=BG_MAIN)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Panel 1: Documentation Panel
        lbl_desc_title = tk.Label(right_frame, text="PROJECT RE.ME DOCUMENTATION", font=self.font_title, bg=BG_MAIN, fg=FG_MUTED)
        lbl_desc_title.pack(anchor=tk.W, pady=(0, 5))

        desc_card = tk.Frame(right_frame, bg=BG_CARD, bd=1, relief="solid", highlightbackground=BG_INPUT)
        desc_card.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        self.desc_text = scrolledtext.ScrolledText(desc_card, wrap=tk.WORD, font=self.font_sans, bg=BG_CARD, fg=FG_MAIN,
                                                   insertbackground=FG_MAIN, relief="flat", bd=0, state=tk.DISABLED, height=12)
        self.desc_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Panel 2: Live Log Console
        lbl_logs_title = tk.Label(right_frame, text="LIVE CONSOLE OUTPUT", font=self.font_title, bg=BG_MAIN, fg=FG_MUTED)
        lbl_logs_title.pack(anchor=tk.W, pady=(0, 5))

        logs_card = tk.Frame(right_frame, bg=BG_CARD, bd=1, relief="solid", highlightbackground=BG_INPUT)
        logs_card.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(logs_card, wrap=tk.CHAR, font=self.font_mono, bg="#0d0e15", fg="#d9e0ee",
                                                  insertbackground="#d9e0ee", relief="flat", bd=0, state=tk.DISABLED, height=18)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Colors configuration for terminal styling tags
        self.log_text.tag_config("tag_info", foreground="#cdd6f4")
        self.log_text.tag_config("tag_cyan", foreground="#89b4fa")
        self.log_text.tag_config("tag_success", foreground="#a6e3a1")
        self.log_text.tag_config("tag_warning", foreground="#f9e2af")
        self.log_text.tag_config("tag_error", foreground="#f38ba8")
        self.log_text.tag_config("tag_muted", foreground="#6c7086")
        self.log_text.tag_config("tag_cmd", foreground="#cba6f7")

    def create_card(self, parent, title):
        card = tk.Frame(parent, bg=BG_CARD, bd=1, relief="solid", highlightbackground=BG_INPUT, highlightthickness=0)
        card.pack(fill=tk.X, pady=(0, 12))
        
        # Border pad container
        pcard = tk.Frame(card, bg=BG_CARD, padx=12, pady=12)
        pcard.pack(fill=tk.X)
        
        tlbl = tk.Label(pcard, text=title, font=self.font_title, bg=BG_CARD, fg=ACCENT)
        tlbl.pack(anchor=tk.W, pady=(0, 8))
        
        return pcard

    def log(self, message, category="info"):
        self.log_queue.put((message, category))

    def process_log_queue(self):
        try:
            while True:
                msg, category = self.log_queue.get_nowait()
                if category == "control":
                    if msg == "enable_ui":
                        self.set_ui_state(tk.NORMAL)
                    self.log_queue.task_done()
                    continue

                tag = f"tag_{category}"
                self.log_text.configure(state=tk.NORMAL)
                self.log_text.insert(tk.END, msg + "\n", tag)
                self.log_text.see(tk.END)
                self.log_text.configure(state=tk.DISABLED)
                self.log_queue.task_done()
        except queue.Empty:
            pass
        self.root.after(100, self.process_log_queue)

    def set_flash_btn_active(self, active=True):
        if active:
            self.btn_flash.configure(bg=ACCENT_GREEN if not self.is_dry_run_var.get() else ACCENT_YELLOW, 
                                     fg=FG_BUTTON, state=tk.NORMAL, cursor="hand2")
        else:
            self.btn_flash.configure(bg=BG_BUTTON_DISABLED, fg=FG_BUTTON_DISABLED, state=tk.DISABLED, cursor="")

    def refresh_ports(self):
        if serial is None:
            self.combo_port.configure(state="disabled")
            self.selected_port_var.set("No COM ports detected")
            self.log("Warning: 'pyserial' module is missing and could not be auto-installed. Automatic serial port detection is disabled. Please run 'pip install pyserial' in your terminal.", "warning")
            self.update_flash_button_state()
            return

        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        
        if not port_list:
            port_list = ["No COM ports detected"]
            self.combo_port.configure(state="disabled")
            self.selected_port_var.set("No COM ports detected")
            self.log("No serial COM ports detected on the system.", "warning")
        else:
            self.combo_port.configure(state="readonly")
            self.combo_port['values'] = port_list
            if self.selected_port_var.get() not in port_list:
                self.selected_port_var.set(port_list[0])
            self.log(f"COM Ports Refreshed. Found {len(port_list)} ports.", "info")

        self.update_flash_button_state()

    def parse_github_url(self, value):
        match = re.search(r'github\.com/([^/]+)/([^/.]+)', value)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def load_source(self):
        path_or_url = self.project_path_var.get().strip()
        if not path_or_url:
            self.log("Error: Project workspace path is empty.", "error")
            return

        owner, repo = self.parse_github_url(path_or_url)
        if owner and repo:
            self.github_owner = owner
            self.github_repo = repo
            self.log(f"Detected GitHub URL: Repository name '{repo}' under user '{owner}'", "cyan")
            self.log("Querying release options from GitHub API...", "info")
            
            # Start background thread to query releases
            threading.Thread(target=self.fetch_github_releases_thread, args=(owner, repo), daemon=True).start()
        else:
            # Load it as local folder
            self.github_owner = None
            self.github_repo = None
            self.combo_git_version.configure(state="disabled")
            self.combo_git_version['values'] = []
            self.selected_git_version_var.set("")
            self.btn_git_download.configure(bg=BG_BUTTON_DISABLED, fg=FG_BUTTON_DISABLED, state=tk.DISABLED, cursor="")
            self.lbl_git_versions.configure(fg=FG_MUTED)

            self.load_local_directory(path_or_url)

    def get_github_token(self):
        token = self.github_token_var.get().strip()
        if not token:
            token = os.environ.get("GITHUB_TOKEN", "").strip()
        return token

    def fetch_github_releases_thread(self, owner, repo):
        url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        headers = {'User-Agent': 'Mozilla/5.0'}
        token = self.get_github_token()
        if token:
            headers['Authorization'] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        versions = ["Latest (default branch)"]
        self.github_releases = []
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                for rel in data:
                    tag = rel.get("tag_name")
                    if tag:
                        versions.append(tag)
                        self.github_releases.append(rel)
            self.log(f"GitHub releases parsed: found {len(versions)-1} tags.", "success")
        except Exception as e:
            self.log(f"Warning: Failed to fetch releases from GitHub API ({str(e)}). Falling back to default branch.", "warning")

        # Update controls safety on main thread
        def gui_update():
            self.combo_git_version.configure(state="readonly")
            self.combo_git_version['values'] = versions
            self.combo_git_version.set(versions[0])
            self.btn_git_download.configure(bg=ACCENT, fg=FG_BUTTON, state=tk.NORMAL, cursor="hand2")
            self.lbl_git_versions.configure(fg=FG_MAIN)
        self.root.after(0, gui_update)

    def start_github_download(self):
        self.set_ui_state(tk.DISABLED)
        version_tag = self.selected_git_version_var.get()
        self.log(f"Downloading repository version: {version_tag}...", "info")
        threading.Thread(target=self.github_downloader_thread, args=(version_tag,), daemon=True).start()

    def github_downloader_thread(self, version):
        # Setup cache folder
        cache_dir = os.path.expanduser(f"~/.gemini/antigravity/scratch/esp_gui_wrapper/github_downloads/{self.github_owner}_{self.github_repo}")
        
        # Format tags to safely compose path
        safe_ver_name = version.replace(" ", "_").replace("/", "_")
        target_extract_path = os.path.join(cache_dir, safe_ver_name)

        if os.path.exists(target_extract_path):
            self.log(f"Cached build files found at: {target_extract_path}", "success")
            self.cached_repo_dir = target_extract_path
            self.root.after(0, lambda: self.finish_github_download(target_extract_path))
            return

        os.makedirs(target_extract_path, exist_ok=True)

        # ZIP URL construction
        if "Latest" in version:
            zip_url = f"https://api.github.com/repos/{self.github_owner}/{self.github_repo}/zipball/"
        else:
            zip_url = f"https://api.github.com/repos/{self.github_owner}/{self.github_repo}/zipball/{version}"

        headers = {'User-Agent': 'Mozilla/5.0'}
        token = self.get_github_token()
        if token:
            headers['Authorization'] = f"Bearer {token}"
        req = urllib.request.Request(zip_url, headers=headers)
        self.log(f"Fetching code ZIP archive: {zip_url}", "info")
        
        try:
            with urllib.request.urlopen(req) as url_resp:
                zip_bytes = url_resp.read()
            
            self.log("ZIP downloaded. Extracting bytes to local project cache directory...", "info")
            z = zipfile.ZipFile(io.BytesIO(zip_bytes))
            z.extractall(target_extract_path)

            self.log("Extraction complete.", "success")
            self.cached_repo_dir = target_extract_path

            self.root.after(0, lambda: self.finish_github_download(target_extract_path))
        except Exception as e:
            self.log(f"Error: Failed to download/extract zip file ({str(e)}).", "error")
            self.log_queue.put(("enable_ui", "control"))

    def finish_github_download(self, extract_path):
        # Zipball extracts everything to a single subroot named {owner}-{repo}-{hash}/
        # Look for this inner folder to point the loader to the true project root path
        extracted_subfolders = os.listdir(extract_path)
        actual_path = extract_path
        if len(extracted_subfolders) == 1:
            child = os.path.join(extract_path, extracted_subfolders[0])
            if os.path.isdir(child):
                actual_path = child

        self.log(f"Pointing workspace loader to extracted root path: {actual_path}", "cyan")
        self.load_local_directory(actual_path)
        self.set_ui_state(tk.NORMAL)

    def load_local_directory(self, directory):
        if not os.path.exists(directory) or not os.path.isdir(directory):
            self.log(f"Error: Workspace path '{directory}' is not a valid directory.", "error")
            return

        self.log(f"Loading files from directory: {directory}", "info")
        
        # Load desc readme
        self.load_project_readme(directory)

        # Check for Build/ folder
        build_path = os.path.join(directory, "Build")
        if os.path.exists(build_path) and os.path.isdir(build_path):
            subdirs = [d for d in os.listdir(build_path) if os.path.isdir(os.path.join(build_path, d))]
            if subdirs:
                self.combo_board.configure(state="readonly")
                self.combo_board['values'] = sorted(subdirs)
                self.combo_board.set(subdirs[0])
                self.log(f"Loaded {len(subdirs)} target boards from Build/ folder.", "success")
                self.on_board_selected()
            else:
                self.combo_board.configure(state="disabled")
                self.combo_board['values'] = []
                self.selected_board_var.set("")
                self.log("Warning: Build/ folder contains no subdirectories.", "warning")
                self.parsed_binaries = []
                self.set_flash_btn_active(False)
        else:
            self.combo_board.configure(state="disabled")
            self.combo_board['values'] = []
            self.selected_board_var.set("")
            self.log("Error: 'Build' folder (case-sensitive) not found in project root folder.", "error")
            self.parsed_binaries = []
            self.set_flash_btn_active(False)

        self.update_flash_button_state()

    def browse_project_folder(self):
        directory = filedialog.askdirectory(title="Select Project Root Folder")
        if not directory:
            return

        self.project_path_var.set(directory)
        # Clear Git widgets since this is a local folder
        self.github_owner = None
        self.github_repo = None
        self.combo_git_version.configure(state="disabled")
        self.combo_git_version['values'] = []
        self.selected_git_version_var.set("")
        self.btn_git_download.configure(bg=BG_BUTTON_DISABLED, fg=FG_BUTTON_DISABLED, state=tk.DISABLED, cursor="")
        self.lbl_git_versions.configure(fg=FG_MUTED)

        self.load_local_directory(directory)

    def load_project_readme(self, root_dir):
        readme_file = None
        for filename in os.listdir(root_dir):
            if filename.lower() in ["read.me", "readme", "readme.txt", "readme.md"]:
                readme_file = os.path.join(root_dir, filename)
                break

        self.desc_text.configure(state=tk.NORMAL)
        self.desc_text.delete("1.0", tk.END)

        if readme_file:
            try:
                with open(readme_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                self.desc_text.insert(tk.END, content)
                self.log(f"Loaded project readme description: {os.path.basename(readme_file)}", "info")
            except Exception as e:
                self.desc_text.insert(tk.END, f"Error reading read.me file:\n{str(e)}")
                self.log(f"Failed to read project documentation file {os.path.basename(readme_file)}", "error")
        else:
            self.desc_text.insert(tk.END, "No read.me file found in the project folder.")
            self.log("Project documentation (read.me) not found in root.", "warning")

        self.desc_text.configure(state=tk.DISABLED)

    def on_board_selected(self, event=None):
        # We need to determine the active workspace root folder being parsed.
        # If GitHub repository is cloned, point board resolution path to self.cached_repo_dir
        path_or_url = self.project_path_var.get().strip()
        owner, repo = self.parse_github_url(path_or_url)
        
        if owner and repo:
            if not self.cached_repo_dir:
                self.parsed_binaries = []
                self.set_flash_btn_active(False)
                return
            project_dir = self.cached_repo_dir
            # Deal with extracted folders inner structures
            subfolders = os.listdir(project_dir)
            if len(subfolders) == 1 and os.path.isdir(os.path.join(project_dir, subfolders[0])):
                project_dir = os.path.join(project_dir, subfolders[0])
        else:
            project_dir = path_or_url

        board_name = self.selected_board_var.get()
        if not project_dir or not board_name:
            self.parsed_binaries = []
            self.set_flash_btn_active(False)
            return

        board_dir = os.path.join(project_dir, "Build", board_name)
        self.log(f"Parsing board profile: {board_name}", "cyan")

        readme_file = None
        for filename in os.listdir(board_dir):
            if filename.lower() in ["read.me", "readme", "readme.txt", "readme.md"]:
                readme_file = os.path.join(board_dir, filename)
                break

        self.parsed_binaries = []

        if not readme_file:
            self.log(f"Error: No partition readme config found in board directory: {board_dir}", "error")
            self.set_flash_btn_active(False)
            return

        try:
            with open(readme_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            pattern = re.compile(r'(0x[0-9a-fA-F]+)\s+([a-zA-Z0-9_\-\.]+\.bin)')
            matches = pattern.findall(content)

            if not matches:
                self.log(f"No partition entries matching '0xHEX partition.bin' found in {os.path.basename(readme_file)}", "error")
                self.set_flash_btn_active(False)
                return

            self.log(f"Parsing {os.path.basename(readme_file)} partition entries:", "info")
            valid_entries = []
            has_missing = False

            for offset, bin_filename in matches:
                abs_bin_path = os.path.join(board_dir, bin_filename)
                exists = os.path.exists(abs_bin_path)
                
                status_str = "FOUND" if exists else "NOT FOUND"
                color = "success" if exists else "error"
                self.log(f"  └─ Address {offset} -> {bin_filename} [{status_str}]", color)

                if exists:
                    valid_entries.append((offset, abs_bin_path))
                else:
                    has_missing = True

            if has_missing:
                self.log("Warning: Some partition binary files listed in read.me are missing from the build directory.", "warning")

            if valid_entries:
                self.parsed_binaries = valid_entries
                self.log(f"Loaded {len(valid_entries)} targets to flash.", "success")
            else:
                self.log("Failure: No valid (existing) binary files parsed to flash.", "error")
                
        except Exception as e:
            self.log(f"Exception parsing partition map: {str(e)}", "error")

        self.update_flash_button_state()

    def update_flash_button_state(self):
        has_dir = bool(self.project_path_var.get())
        has_board = bool(self.selected_board_var.get())
        
        selected_port = self.selected_port_var.get()
        has_port = bool(selected_port) and selected_port != "No COM ports detected"
        
        has_binaries = len(self.parsed_binaries) > 0

        can_flash = has_dir and has_board and has_port and has_binaries
        self.set_flash_btn_active(can_flash)

    def start_flash(self):
        self.set_ui_state(tk.DISABLED)
        
        # Clear log area
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

        # Run flashing on a background thread so UI doesn't lock up
        flash_thread = threading.Thread(target=self.flash_thread_worker, args=(self.selected_port_var.get(), self.is_dry_run_var.get()), daemon=True)
        flash_thread.start()

    def set_ui_state(self, state):
        self.btn_browse.configure(state=state)
        self.btn_load_src.configure(state=state)
        self.entry_dir.configure(state=state)
        self.entry_token.configure(state=state)
        
        if state == tk.DISABLED:
            self.combo_board.configure(state="disabled")
            self.combo_port.configure(state="disabled")
            self.combo_git_version.configure(state="disabled")
            self.sim_check.configure(state="disabled")
            self.btn_refresh_ports.configure(state=state)
            self.btn_git_download.configure(state="disabled")
            self.btn_flash.configure(bg=BG_BUTTON_DISABLED, fg=FG_BUTTON_DISABLED, state=tk.DISABLED, cursor="")
        else:
            self.combo_board.configure(state="readonly" if self.combo_board["values"] else "disabled")
            self.combo_port.configure(state="readonly" if self.combo_port["values"] and self.combo_port["values"][0] != "No COM ports detected" else "disabled")
            self.combo_git_version.configure(state="readonly" if self.combo_git_version["values"] else "disabled")
            self.sim_check.configure(state="normal")
            self.btn_refresh_ports.configure(state=state)
            if self.combo_git_version["values"]:
                self.btn_git_download.configure(bg=ACCENT, fg=FG_BUTTON, state=tk.NORMAL, cursor="hand2")
            self.update_flash_button_state()

    def flash_thread_worker(self, port, is_dry_run):
        self.log("================= Starting Flashing Operation =================", "cyan")
        if is_dry_run:
            self.log("[SIMULATION MODE ACTIVE]", "warning")

        cmd_args = ["--baud", "460800", "write_flash", "-z", "--flash_mode", "dio", "--flash_freq", "40m", "--flash_size", "detect"]
        
        flash_target_list = []
        for offset, bin_path in self.parsed_binaries:
            flash_target_list.append(offset)
            flash_target_list.append(bin_path)

        if is_dry_run:
            full_command_str = f"esptool.py --port {port} " + " ".join(cmd_args) + " " + " ".join(
                [f"{offset} {os.path.basename(path)}" for offset, path in self.parsed_binaries]
            )
            self.log(f"Flash Command constructed (simulation):\n{full_command_str}", "cmd")
            self.log("Working path containing firmware: " + os.path.dirname(self.parsed_binaries[0][1]), "muted")

            time.sleep(0.5)
            self.log("esptool.py v4.6.2", "info")
            self.log(f"Serial port {port}", "info")
            self.log("Connecting....", "info")
            time.sleep(0.6)
            self.log("Detecting chip type... ESP32", "info")
            time.sleep(0.4)
            self.log("Chip is ESP32-D0WDQ6 (revision v1.0)", "info")
            self.log("Mac verification complete. Auto-detected Flash size: 4MB", "success")

            for offset, path in self.parsed_binaries:
                basename = os.path.basename(path)
                self.log(f"\nFlashing {basename} at {offset}...", "cyan")
                time.sleep(0.3)
                
                for percentage in range(0, 101, 20):
                    self.log(f"Writing at {offset}... ({percentage}%)", "info")
                    time.sleep(0.15)
                
                self.log(f"Wrote file {basename} at {offset} - Hash of data verified.", "success")
                time.sleep(0.2)

            self.log("\nLeaving...", "info")
            self.log("Hard resetting via RTS pin...", "info")
            self.log("================= Flash Successful! =================", "success")
            
        else:
            esptool_command = ['esptool']
            try:
                subprocess.run(['esptool', '-h'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except FileNotFoundError:
                try:
                    subprocess.run(['esptool.py', '-h'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    esptool_command = ['esptool.py']
                except FileNotFoundError:
                    esptool_command = [sys.executable, '-m', 'esptool']

            full_cmd = esptool_command + ["--port", port] + cmd_args + flash_target_list
            
            cmd_log_list = esptool_command + ["--port", port] + cmd_args
            for offset, bin_path in self.parsed_binaries:
                cmd_log_list.append(offset)
                cmd_log_list.append(os.path.basename(bin_path))
            
            self.log(f"Executing Flash Command:\n{' '.join(cmd_log_list)}", "cmd")
            self.log(f"Targeting absolute paths:\n" + "\n".join([f"{o} -> {p}" for o, p in self.parsed_binaries]), "muted")

            try:
                process = subprocess.Popen(
                    full_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )

                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        clean_line = line.rstrip('\n')
                        if "error" in clean_line.lower() or "failed" in clean_line.lower():
                            self.log(clean_line, "error")
                        elif "success" in clean_line.lower() or "hash of data verified" in clean_line.lower():
                            self.log(clean_line, "success")
                        elif "warning" in clean_line.lower():
                            self.log(clean_line, "warning")
                        else:
                            self.log(clean_line, "info")

                exit_code = process.wait()
                if exit_code == 0:
                    self.log("\n================= Flash Successful! =================", "success")
                else:
                    self.log(f"\n================= Flash Failed! Exit code {exit_code} =================", "error")

            except Exception as e:
                self.log(f"System Error: Failed to execute command. {str(e)}", "error")
                self.log("Please verify python dependencies / esptool package installation.", "warning")

        # Finished - restore GUI state on main thread via queue
        self.log_queue.put(("enable_ui", "control"))

if __name__ == "__main__":
    root = tk.Tk()
    app = ArkFlasherGUI(root)
    root.mainloop()

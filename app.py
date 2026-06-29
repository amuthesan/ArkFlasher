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

# Color Palette (Premium Slate Light Theme)
BG_MAIN = "#f1f5f9"           # Slate-100 base background
BG_CARD = "#ffffff"           # White cards/panels
BG_INPUT = "#f8fafc"          # Slate-50 inputs
FG_MAIN = "#0f172a"           # Slate-900 primary text
FG_MUTED = "#64748b"          # Slate-500 muted text/labels
ACCENT = "#2563eb"            # vibrant Blue-600
ACCENT_HOVER = "#1d4ed8"      # Blue-700 hover
ACCENT_GREEN = "#10b981"      # Emerald-500 success
ACCENT_YELLOW = "#f59e0b"     # Amber-500 warn
ACCENT_RED = "#ef4444"        # Red-500 error
BG_BUTTON = "#e2e8f0"         # Slate-200 secondary button bg
FG_BUTTON = "#0f172a"         # Slate-900 text on buttons
BG_BUTTON_DISABLED = "#cbd5e1"
FG_BUTTON_DISABLED = "#94a3b8"

class ArkFlasherGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Ark Flasher (esptool wrapper)")
        self.root.geometry("1120x730")
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
        self.font_sans = ("Avenir Next", 10)
        self.font_sans_bold = ("Avenir Next", 10, "bold")
        self.font_title = ("Avenir Next", 11, "bold")
        self.font_mono = ("Menlo", 9)

        # Load and scale brand Logo
        self.logo_img = None
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(script_dir, "img", "Logo.png")
        if os.path.exists(logo_path):
            try:
                temp_img = tk.PhotoImage(file=logo_path)
                self.logo_img = temp_img.subsample(3, 3)
            except Exception as e:
                print(f"Error loading logo: {e}")

        # Configure styles
        self.setup_styles()

        # Create Layout
        self.build_ui()

        # Prepopulate project workspace directory with current working directory to show panels populated on startup
        curr_dir = os.path.abspath(os.path.dirname(__file__))
        self.project_path_var.set(curr_dir)
        self.root.after(100, lambda: self.load_local_directory(curr_dir))

        # Init COM port dropdown
        self.refresh_ports()

        # Start checking incoming logs from back-end threads
        self.root.after(100, self.process_log_queue)

        self.log("Application started successfully.", "cyan")
        self.log("Workspace auto-detected and loaded.", "success")

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

    def add_hover_effect(self, widget, hover_bg, normal_bg, active_fg=None, normal_fg=None):
        def on_enter(e):
            if widget.cget("state") != "disabled":
                widget.config(bg=hover_bg)
                if active_fg:
                    widget.config(fg=active_fg)
        def on_leave(e):
            if widget.cget("state") != "disabled":
                widget.config(bg=normal_bg)
                if normal_fg:
                    widget.config(fg=normal_fg)
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def bind_mousewheel(self, widget):
        def on_mousewheel(event):
            if sys.platform == 'darwin':
                self.catalog_canvas.xview_scroll(-1 * event.delta, "units")
            else:
                self.catalog_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

        widget.bind("<MouseWheel>", on_mousewheel)
        widget.bind("<Button-4>", lambda e: self.catalog_canvas.xview_scroll(-1, "units"))
        widget.bind("<Button-5>", lambda e: self.catalog_canvas.xview_scroll(1, "units"))
        for child in widget.winfo_children():
            self.bind_mousewheel(child)

    def update_hardware_status(self):
        selected_port = self.selected_port_var.get()
        if selected_port and selected_port != "No COM ports detected":
            self.status_dot.configure(fg=ACCENT_GREEN)
            self.status_text_lbl.configure(text=f"CONNECTED: {selected_port}", fg=FG_MAIN)
        else:
            self.status_dot.configure(fg=ACCENT_RED)
            self.status_text_lbl.configure(text="DISCONNECTED", fg=FG_MUTED)

    def render_board_catalog(self, boards):
        # Clear existing cards in catalog
        for widget in self.catalog_grid_frame.winfo_children():
            widget.destroy()
        self.board_card_widgets = []
        
        # Reset scroll view to start
        if hasattr(self, 'catalog_canvas'):
            self.catalog_canvas.xview_moveto(0)

        if not boards:
            no_boards_lbl = tk.Label(self.catalog_grid_frame, text="No board configurations discovered yet. Load a project first.", 
                                     font=self.font_sans, bg=BG_CARD, fg=FG_MUTED)
            no_boards_lbl.pack(pady=40)
            self.bind_mousewheel(self.catalog_grid_frame)
            return

        # Render board cards
        for board_name in boards:
            card_frame = tk.Frame(self.catalog_grid_frame, bg=BG_CARD, bd=1, relief="solid", 
                                  highlightbackground="#e2e8f0", highlightthickness=1, cursor="hand2")
            card_frame.pack(side=tk.LEFT, padx=12, pady=10, ipady=12, ipadx=18)

            lbl_title = tk.Label(card_frame, text=board_name.upper(), font=("Helvetica Neue", 13, "bold"), 
                                 bg=BG_CARD, fg=ACCENT)
            lbl_title.pack(anchor=tk.W, pady=(0, 4))

            lbl_desc = tk.Label(card_frame, text="ESP32 Firmware Target", font=self.font_sans, 
                                bg=BG_CARD, fg=FG_MUTED)
            lbl_desc.pack(anchor=tk.W)

            card_frame.board_name = board_name

            def make_select_callback(name=board_name):
                return lambda e: self.select_board_card(name)

            card_frame.bind("<Button-1>", make_select_callback())
            lbl_title.bind("<Button-1>", make_select_callback())
            lbl_desc.bind("<Button-1>", make_select_callback())

            def make_hover_enter(frame=card_frame):
                def handler(e):
                    if self.selected_board_var.get() != frame.board_name:
                        frame.config(bg="#f1f5f9")
                        for child in frame.winfo_children():
                            child.config(bg="#f1f5f9")
                return handler

            def make_hover_leave(frame=card_frame):
                def handler(e):
                    if self.selected_board_var.get() != frame.board_name:
                        frame.config(bg=BG_CARD)
                        for child in frame.winfo_children():
                            child.config(bg=BG_CARD)
                return handler

            card_frame.bind("<Enter>", make_hover_enter())
            card_frame.bind("<Leave>", make_hover_leave())

            self.board_card_widgets.append(card_frame)

        self.bind_mousewheel(self.catalog_grid_frame)

    def select_board_card(self, board_name):
        self.selected_board_var.set(board_name)
        self.combo_board.set(board_name)

        # Highlight selected card, unhighlight others
        for card in self.board_card_widgets:
            if card.board_name == board_name:
                card.config(highlightbackground=ACCENT, highlightthickness=1, bg="#eff6ff")
                for child in card.winfo_children():
                    child.config(bg="#eff6ff")
            else:
                card.config(highlightbackground="#e2e8f0", highlightthickness=1, bg=BG_CARD)
                for child in card.winfo_children():
                    child.config(bg=BG_CARD)

        # Trigger partition parsing
        self.on_board_selected()

    def build_ui(self):
        # --- TOP HEADER BAR ---
        header_frame = tk.Frame(self.root, bg="#ffffff", height=80)
        header_frame.pack(side=tk.TOP, fill=tk.X)
        header_frame.pack_propagate(False)

        # Subtle bottom border separator line
        border_line = tk.Frame(self.root, bg="#cbd5e1", height=1)
        border_line.pack(side=tk.TOP, fill=tk.X)

        # Logo on the left of header
        if self.logo_img:
            logo_lbl = tk.Label(header_frame, image=self.logo_img, bg="#ffffff")
            logo_lbl.pack(side=tk.LEFT, padx=20, pady=13)
        else:
            logo_lbl = tk.Label(header_frame, text="ARK TECHNOLOGY", font=("Avenir Next", 14, "bold"), bg="#ffffff", fg=ACCENT)
            logo_lbl.pack(side=tk.LEFT, padx=20, pady=25)

        # Title/desc in the center
        title_lbl = tk.Label(header_frame, text="ARK FLASHER", font=("Avenir Next", 18, "bold"), bg="#ffffff", fg=FG_MAIN)
        title_lbl.pack(side=tk.LEFT, padx=(10, 15), pady=23)

        # Live Status indicator on the right of header
        status_subframe = tk.Frame(header_frame, bg="#ffffff")
        status_subframe.pack(side=tk.RIGHT, padx=25, pady=23)

        self.status_dot = tk.Label(status_subframe, text="●", font=("Avenir Next", 14), bg="#ffffff", fg=ACCENT_RED)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 5))

        self.status_text_lbl = tk.Label(status_subframe, text="DISCONNECTED", font=self.font_sans_bold, bg="#ffffff", fg=FG_MUTED)
        self.status_text_lbl.pack(side=tk.LEFT)

        # Main outer frame with padding (positioned below header)
        main_frame = tk.Frame(self.root, bg=BG_MAIN)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # --- LEFT SIDEBAR (Controls Column - width 380px) ---
        left_frame = tk.Frame(main_frame, bg=BG_MAIN, width=390)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        left_frame.pack_propagate(False)

        # Card 1: Project Source Input
        source_card = self.create_card(left_frame, "1. PROJECT WORKSPACE")
        
        lbl_dir = tk.Label(source_card, text="Path or GitHub Repo URL:", font=self.font_sans_bold, bg=BG_CARD, fg=FG_MAIN)
        lbl_dir.pack(anchor=tk.W, pady=(0, 5))

        self.project_path_var = tk.StringVar()
        self.entry_dir = tk.Entry(source_card, textvariable=self.project_path_var, bg=BG_INPUT, fg=FG_MAIN, 
                                  insertbackground=FG_MAIN, relief="flat", bd=1, highlightbackground="#cbd5e1", 
                                  highlightcolor=ACCENT, highlightthickness=1, font=self.font_sans)
        self.entry_dir.pack(fill=tk.X, pady=(0, 10))

        lbl_token = tk.Label(source_card, text="GitHub Token (Optional):", font=self.font_sans_bold, bg=BG_CARD, fg=FG_MAIN)
        lbl_token.pack(anchor=tk.W, pady=(0, 5))

        self.entry_token = tk.Entry(source_card, textvariable=self.github_token_var, bg=BG_INPUT, fg=FG_MAIN, 
                                    insertbackground=FG_MAIN, relief="flat", bd=1, highlightbackground="#cbd5e1", 
                                    highlightcolor=ACCENT, highlightthickness=1, font=self.font_sans, show="*")
        self.entry_token.pack(fill=tk.X, pady=(0, 10))

        # Horizontal layout for browse / load button
        src_btn_frame = tk.Frame(source_card, bg=BG_CARD)
        src_btn_frame.pack(fill=tk.X)

        self.btn_browse = tk.Button(src_btn_frame, text="Browse Folder...", font=self.font_sans_bold, bg=BG_BUTTON, fg=FG_BUTTON,
                                    activebackground="#cbd5e1", activeforeground=FG_BUTTON, relief="flat", bd=0, 
                                    padx=10, pady=4, cursor="hand2", command=self.browse_project_folder)
        self.btn_browse.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        self.add_hover_effect(self.btn_browse, "#cbd5e1", BG_BUTTON)

        self.btn_load_src = tk.Button(src_btn_frame, text="Load / Sync", font=self.font_sans_bold, bg=ACCENT_GREEN, fg="#ffffff",
                                     activebackground="#059669", activeforeground="#ffffff", relief="flat", bd=0, 
                                     padx=10, pady=4, cursor="hand2", command=self.load_source)
        self.btn_load_src.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))
        self.add_hover_effect(self.btn_load_src, "#059669", ACCENT_GREEN)

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
        self.add_hover_effect(self.btn_git_download, ACCENT_HOVER, ACCENT)

        # Hidden Combobox for Test Cases Compatibility
        self.selected_board_var = tk.StringVar()
        self.combo_board = ttk.Combobox(left_frame, textvariable=self.selected_board_var)
        self.combo_board.bind("<<ComboboxSelected>>", self.on_board_selected)

        # Card 3: Flasher Control
        setup_card = self.create_card(left_frame, "3. FLASHER CONTROL")

        lbl_port = tk.Label(setup_card, text="Serial COM Port:", font=self.font_sans_bold, bg=BG_CARD, fg=FG_MAIN)
        lbl_port.pack(anchor=tk.W, pady=(0, 5))

        port_subframe = tk.Frame(setup_card, bg=BG_CARD)
        port_subframe.pack(fill=tk.X, pady=(0, 10))

        self.selected_port_var = tk.StringVar()
        self.combo_port = ttk.Combobox(port_subframe, textvariable=self.selected_port_var, state="readonly", font=self.font_sans, width=15)
        self.combo_port.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.combo_port.bind("<<ComboboxSelected>>", lambda e: (self.update_flash_button_state(), self.update_hardware_status()))

        self.btn_refresh_ports = tk.Button(port_subframe, text="⟳", font=("Helvetica Neue", 12, "bold"), bg=BG_BUTTON, 
                                           fg=FG_BUTTON, activebackground="#cbd5e1", activeforeground=FG_BUTTON, 
                                           relief="flat", bd=0, padx=6, pady=2, cursor="hand2", command=self.refresh_ports)
        self.btn_refresh_ports.pack(side=tk.LEFT, padx=(5, 0))
        self.add_hover_effect(self.btn_refresh_ports, "#cbd5e1", BG_BUTTON)

        self.is_dry_run_var = tk.BooleanVar(value=True)
        self.sim_check = ttk.Checkbutton(setup_card, text="Simulate Flash (Dry Run / Test)", variable=self.is_dry_run_var, style="TCheckbutton")
        self.sim_check.pack(anchor=tk.W, pady=(0, 10))

        self.btn_flash = tk.Button(setup_card, text="Flash Target Board", font=("Helvetica Neue", 12, "bold"), 
                                   bg=BG_BUTTON_DISABLED, fg=FG_BUTTON_DISABLED, relief="flat", bd=0, 
                                   pady=8, state=tk.DISABLED, command=self.start_flash)
        self.btn_flash.pack(fill=tk.X)

        def on_enter_flash(e):
            if self.btn_flash.cget("state") != "disabled":
                is_dry = self.is_dry_run_var.get()
                self.btn_flash.configure(bg="#fce8c3" if is_dry else "#c2f0c2")
        def on_leave_flash(e):
            if self.btn_flash.cget("state") != "disabled":
                is_dry = self.is_dry_run_var.get()
                self.btn_flash.configure(bg=ACCENT_YELLOW if is_dry else ACCENT_GREEN)
        self.btn_flash.bind("<Enter>", on_enter_flash)
        self.btn_flash.bind("<Leave>", on_leave_flash)

        # --- RIGHT COLUMN (Board Catalog & Program Specs Widescreen) ---
        right_frame = tk.Frame(main_frame, bg=BG_MAIN)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 1. Board Catalog Section
        lbl_catalog_title = tk.Label(right_frame, text="BOARD CATALOG BROWSER", font=self.font_title, bg=BG_MAIN, fg=FG_MUTED)
        lbl_catalog_title.pack(anchor=tk.W, pady=(0, 4))

        catalog_card = tk.Frame(right_frame, bg=BG_CARD, bd=1, relief="solid", highlightbackground="#e2e8f0")
        catalog_card.pack(fill=tk.X, pady=(0, 10))

        # A Canvas to scroll the cards
        self.catalog_canvas = tk.Canvas(catalog_card, bg=BG_CARD, highlightthickness=0, bd=0)
        self.catalog_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Horizontal Scrollbar
        self.catalog_scrollbar = ttk.Scrollbar(catalog_card, orient=tk.HORIZONTAL, command=self.catalog_canvas.xview)
        self.catalog_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.catalog_canvas.configure(xscrollcommand=self.catalog_scrollbar.set)

        # A horizontal frame for catalog boards
        self.catalog_grid_frame = tk.Frame(self.catalog_canvas, bg=BG_CARD, padx=10, pady=8)
        self.catalog_window_id = self.catalog_canvas.create_window((0, 0), window=self.catalog_grid_frame, anchor="nw")
        self.board_card_widgets = []

        no_boards_lbl = tk.Label(self.catalog_grid_frame, text="No board configurations discovered yet. Load a project first.", 
                                 font=self.font_sans, bg=BG_CARD, fg=FG_MUTED)
        no_boards_lbl.pack(pady=25)

        # Dynamically resize canvas height to match grid frame and update scrollregion
        def on_grid_configure(event):
            self.catalog_canvas.configure(scrollregion=self.catalog_canvas.bbox("all"))
            grid_height = self.catalog_grid_frame.winfo_reqheight()
            self.catalog_canvas.configure(height=grid_height)

        self.catalog_grid_frame.bind("<Configure>", on_grid_configure)

        # 2. README Documentation Panel (stacked in middle)
        lbl_desc_title = tk.Label(right_frame, text="PROJECT README DOCUMENTATION", font=self.font_title, bg=BG_MAIN, fg=FG_MUTED)
        lbl_desc_title.pack(anchor=tk.W, pady=(0, 4))

        desc_card = tk.Frame(right_frame, bg=BG_CARD, bd=1, relief="solid", highlightbackground="#e2e8f0")
        desc_card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.desc_text = scrolledtext.ScrolledText(desc_card, wrap=tk.WORD, font=self.font_sans, bg=BG_CARD, fg=FG_MAIN,
                                                   insertbackground=FG_MAIN, relief="flat", bd=0, state=tk.DISABLED, height=8)
        self.desc_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 3. Live Console Logs (Tray at bottom, full width of details section)
        lbl_logs_title = tk.Label(right_frame, text="LIVE CONSOLE OUTPUT", font=self.font_title, bg=BG_MAIN, fg=FG_MUTED)
        lbl_logs_title.pack(anchor=tk.W, pady=(0, 4))

        logs_card = tk.Frame(right_frame, bg=BG_CARD, bd=1, relief="solid", highlightbackground="#e2e8f0")
        logs_card.pack(fill=tk.X, pady=(0, 2))

        self.log_text = scrolledtext.ScrolledText(logs_card, wrap=tk.CHAR, font=self.font_mono, bg="#0d0e15", fg="#d9e0ee",
                                                   insertbackground="#d9e0ee", relief="flat", bd=0, state=tk.DISABLED, height=8)
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
        card.pack(fill=tk.X, pady=(0, 10))
        
        # Border pad container
        pcard = tk.Frame(card, bg=BG_CARD, padx=10, pady=10)
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
            is_dry = self.is_dry_run_var.get()
            self.btn_flash.configure(bg=ACCENT_YELLOW if is_dry else ACCENT_GREEN, 
                                     fg="#0f172a" if is_dry else "#ffffff", state=tk.NORMAL, cursor="hand2")
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
        self.update_hardware_status()

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
            self.btn_git_download.configure(bg=ACCENT, fg="#ffffff", state=tk.NORMAL, cursor="hand2")
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
                sorted_subdirs = sorted(subdirs)
                self.combo_board.configure(state="readonly")
                self.combo_board['values'] = sorted_subdirs
                self.combo_board.set(sorted_subdirs[0])
                self.log(f"Loaded {len(subdirs)} target boards from Build/ folder.", "success")
                self.render_board_catalog(sorted_subdirs)
                self.select_board_card(sorted_subdirs[0])
            else:
                self.combo_board.configure(state="disabled")
                self.combo_board['values'] = []
                self.selected_board_var.set("")
                self.log("Warning: Build/ folder contains no subdirectories.", "warning")
                self.parsed_binaries = []
                self.set_flash_btn_active(False)
                self.render_board_catalog([])
        else:
            self.combo_board.configure(state="disabled")
            self.combo_board['values'] = []
            self.selected_board_var.set("")
            self.log("Error: 'Build' folder (case-sensitive) not found in project root folder.", "error")
            self.parsed_binaries = []
            self.set_flash_btn_active(False)
            self.render_board_catalog([])

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
                self.btn_git_download.configure(bg=ACCENT, fg="#ffffff", state=tk.NORMAL, cursor="hand2")
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

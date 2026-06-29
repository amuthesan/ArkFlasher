#!/usr/bin/env python3
import os
import re
import sys
import time
import unittest
import io
import zipfile
import tkinter as tk
from unittest.mock import MagicMock, patch

# 1. Mock serial and serial.tools.list_ports before importing app
mock_serial = MagicMock()
mock_serial.tools = MagicMock()
mock_serial.tools.list_ports = MagicMock()

# Mock list_ports.comports
mock_port = MagicMock()
mock_port.device = "COM3"
mock_serial.tools.list_ports.comports.return_value = [mock_port]

sys.modules['serial'] = mock_serial
sys.modules['serial.tools'] = mock_serial.tools
sys.modules['serial.tools.list_ports'] = mock_serial.tools.list_ports

import app

class TestArkFlasherGUI(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        # Withdraw the root window so it doesn't display physically during tests
        self.root.withdraw()
        self.gui = app.ArkFlasherGUI(self.root)
        self.mock_project_dir = "/Users/amuthesan/.gemini/antigravity/scratch/esp_gui_wrapper/mock_project"

    def tearDown(self):
        self.root.destroy()

    def test_regex_regex_pattern(self):
        # Validate that the regex pattern specified in requirements matches correctly
        pattern = re.compile(r'(0x[0-9a-fA-F]+)\s+([a-zA-Z0-9_\-\.]+\.bin)')
        
        test_text = "0x1000 bootloader.bin\n0x8000 partition-table.bin\n0x10000 firmware.bin\n"
        matches = pattern.findall(test_text)
        
        self.assertEqual(len(matches), 3)
        self.assertEqual(matches[0], ("0x1000", "bootloader.bin"))
        self.assertEqual(matches[1], ("0x8000", "partition-table.bin"))
        self.assertEqual(matches[2], ("0x10000", "firmware.bin"))

    def test_parse_github_url(self):
        # Valid URLs
        owner, repo = self.gui.parse_github_url("https://github.com/espressif/esptool")
        self.assertEqual(owner, "espressif")
        self.assertEqual(repo, "esptool")

        owner, repo = self.gui.parse_github_url("github.com/espressif/esptool.git")
        self.assertEqual(owner, "espressif")
        self.assertEqual(repo, "esptool")

        # Invalid URLs
        owner, repo = self.gui.parse_github_url("/Users/amuthesan/project")
        self.assertIsNone(owner)
        self.assertIsNone(repo)

    def test_project_load(self):
        # Directly call directory loading on mock project
        self.gui.project_path_var.set(self.mock_project_dir)
        self.gui.load_project_readme(self.mock_project_dir)
        
        # Verify content was loaded in text box
        desc_content = self.gui.desc_text.get("1.0", tk.END)
        self.assertIn("Tx_tester Project", desc_content)

    def test_board_selection_populates_targets(self):
        self.gui.project_path_var.set(self.mock_project_dir)
        
        # Simulate browsing the project
        build_path = os.path.join(self.mock_project_dir, "Build")
        self.assertTrue(os.path.exists(build_path))
        
        # Populate board combo manually and select
        subdirs = sorted([d for d in os.listdir(build_path) if os.path.isdir(os.path.join(build_path, d))])
        self.assertIn("esp32", subdirs)
        self.assertIn("Esp32s3", subdirs)
        
        # Select esp32 and trigger load
        self.gui.combo_board['values'] = subdirs
        self.gui.selected_board_var.set("esp32")
        self.gui.on_board_selected()
        
        # Verification that partition files were parsed successfully
        self.assertEqual(len(self.gui.parsed_binaries), 3)
        self.assertEqual(self.gui.parsed_binaries[0][0], "0x1000")
        self.assertTrue(self.gui.parsed_binaries[0][1].endswith("bootloader.bin"))

    def test_dry_run_command_construction(self):
        # Mock time.sleep to run instantly
        original_sleep = time.sleep
        time.sleep = lambda x: None
        
        try:
            self.gui.project_path_var.set(self.mock_project_dir)
            self.gui.combo_board['values'] = ["esp32"]
            self.gui.selected_board_var.set("esp32")
            self.gui.on_board_selected()
            
            # Set COM port and mock dry run checkbox
            self.gui.selected_port_var.set("COM3")
            self.gui.is_dry_run_var.set(True)
            
            # Enable flash button checks
            self.gui.update_flash_button_state()
            
            # Re-verify simulated background runner
            self.gui.start_flash()
            
            # Wait for background thread to post control message to queue and terminate
            timeout = 3.0
            start = time.perf_counter()
            while time.perf_counter() - start < timeout:
                self.gui.process_log_queue()
                if self.gui.btn_flash.cget("state") == "normal":
                    break
                self.root.update()
                
            # Process one final queue flush
            self.gui.process_log_queue()

            # Check logs scrolled area contains flash target outputs
            logs_content = self.gui.log_text.get("1.0", tk.END)
            self.assertIn("SIMULATION MODE ACTIVE", logs_content)
            self.assertIn("esptool.py --port COM3", logs_content)
            self.assertIn("Wrote file firmware.bin", logs_content)
            self.assertIn("Flash Successful!", logs_content)
            
        finally:
            # Restore original sleep
            time.sleep = original_sleep

    def test_fetch_github_releases_mock(self):
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = b'[{"tag_name": "v5.0.0"}, {"tag_name": "v4.9.0"}]'
        
        with patch('urllib.request.urlopen', return_value=mock_response):
            self.gui.fetch_github_releases_thread("espressif", "esptool")
            
            self.root.update()
            
            # Check version values in combobox
            self.assertEqual(self.gui.combo_git_version['values'], ("Latest (default branch)", "v5.0.0", "v4.9.0"))
            self.assertEqual(self.gui.combo_git_version.get(), "Latest (default branch)")

    def test_github_downloader_mock(self):
        # Clean up any stale directory from previous test runs
        import shutil
        cache_dir = os.path.expanduser("~/.gemini/antigravity/scratch/esp_gui_wrapper/github_downloads/mock_owner_mock_repo")
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)

        # We will mock urlopen to return a fake ZIP file
        mock_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(mock_zip_buffer, 'w') as z:
            z.writestr("mock-repo-1234/read.me", "mock project readme content")
            z.writestr("mock-repo-1234/Build/esp32/read.me", "0x1000 bootloader.bin\n")
            z.writestr("mock-repo-1234/Build/esp32/bootloader.bin", "")
            
        mock_zip_bytes = mock_zip_buffer.getvalue()
        
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = mock_zip_bytes
        
        # Point the path to a mock GitHub URL
        self.gui.project_path_var.set("https://github.com/mock_owner/mock_repo")
        self.gui.github_owner = "mock_owner"
        self.gui.github_repo = "mock_repo"
        
        with patch('urllib.request.urlopen', return_value=mock_response):
            # Run download thread
            self.gui.github_downloader_thread("Latest (default branch)")
            
            # Retrieve project root path and trigger final loaders
            extracted_root = self.gui.cached_repo_dir
            self.gui.finish_github_download(extracted_root)
            
            # Check readme loaded
            desc_content = self.gui.desc_text.get("1.0", tk.END)
            self.assertIn("mock project readme content", desc_content)
            
            # Verify board read.me parsed and populated board combo values
            self.assertEqual(self.gui.combo_board['values'], ("esp32",))

    def test_fetch_github_releases_with_token(self):
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = b'[]'
        
        self.gui.github_token_var.set("ghp_my_mock_secret_token")
        
        with patch('urllib.request.urlopen', return_value=mock_response) as mock_urlopen:
            self.gui.fetch_github_releases_thread("espressif", "esptool")
            
            # Extract request object
            args, kwargs = mock_urlopen.call_args
            req = args[0]
            
            self.assertEqual(req.get_header("Authorization"), "Bearer ghp_my_mock_secret_token")

    def test_github_downloader_with_token(self):
        import shutil
        cache_dir = os.path.expanduser("~/.gemini/antigravity/scratch/esp_gui_wrapper/github_downloads/mock_owner_token_mock_repo_token")
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)

        mock_zip_buffer = io.BytesIO()
        with zipfile.ZipFile(mock_zip_buffer, 'w') as z:
            z.writestr("mock-repo-1234/read.me", "mock project readme content")
            z.writestr("mock-repo-1234/Build/esp32/read.me", "0x1000 bootloader.bin\n")
            z.writestr("mock-repo-1234/Build/esp32/bootloader.bin", "")
            
        mock_zip_bytes = mock_zip_buffer.getvalue()
        
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.read.return_value = mock_zip_bytes
        
        self.gui.project_path_var.set("https://github.com/mock_owner_token/mock_repo_token")
        self.gui.github_owner = "mock_owner_token"
        self.gui.github_repo = "mock_repo_token"
        self.gui.github_token_var.set("ghp_download_secret_token")
        
        with patch('urllib.request.urlopen', return_value=mock_response) as mock_urlopen:
            self.gui.github_downloader_thread("Latest (default branch)")
            
            # Extract request object
            args, kwargs = mock_urlopen.call_args
            req = args[0]
            
            self.assertEqual(req.get_header("Authorization"), "Bearer ghp_download_secret_token")

if __name__ == "__main__":
    unittest.main()

# Ark Flasher - Standardized ESP32 Project Structure

**Ark Flasher** is a modern, cross-platform graphical wrapper for `esptool.py`. To ensure Ark Flasher can seamlessly parse and upload builds from your ESP32 projects (either loaded locally or fetched directly from a GitHub repository), projects must adhere to a standardized directory layout.

---

## 📂 Standard Directory Layout

Every compatible ESP32 project must follow this exact workspace layout in its root directory:

```
my-esp32-project/
├── README.md               <-- Project-level documentation (rendered in the right panel)
└── Build/                  <-- [REQUIRED] Contains all build-compiled target binary profiles (case-sensitive)
    ├── esp32/              <-- Target Board Profile Name (e.g. esp32, heltec_wifi_lora_v3)
    │   ├── README.md       <-- [REQUIRED] Target Board partition-map specification
    │   ├── bootloader.bin  <-- Firmware binary at specified offset (e.g., 0x1000)
    │   ├── partitions.bin  <-- Partition table binary (e.g., 0x8000)
    │   └── firmware.bin    <-- Main application binary (e.g., 0x10000)
    │
    └── esp32s3/            <-- Another target board profile
        ├── README.md
        └── ...
```

---

## ⚙️ Target Board Profile Requirements

Ark Flasher parses target profiles dynamically. To be recognized, each subfolder under `Build/` must satisfy:

1. **Target Board Name**: The name of the subfolder acts as the target board identify/profile name displayed in the board configuration dropdown (e.g., `esp32s3` or `heltec_wifi_lora_v3`).
2. **Metadata file (`README.md` or `read.me`)**: A markdown or text file located directly inside the board profile folder, defining the custom partition table mapping.
3. **Firmware Binary Files**: The actual `.bin` executable files mapped in your partition definitions.

### 📝 Partition Map Format

The partition map metadata file (`README.md` or `read.me`) inside a target board folder specifies the exact hardware write addresses (offsets) for your binaries. 

Ark Flasher matches rows in this metadata file via a strict pattern: `<0xHEX_ADDRESS>   <BINARY_NAME.bin>`. For example:

```markdown
# Heltec WiFi LoRa v3 Partition Map
0x1000   bootloader.bin
0x8000   partition-table.bin
0x10000  firmware.bin
```

> [!IMPORTANT]
> - **Syntax**: Addresses must be in hexadecimal format (e.g., `0x1000`, `0x8000`, `0x10000`).
> - **Filename Matching**: The referenced binary file name must precisely match the file names present in that target board subdirectory (case-sensitive).
> - **Whitespace**: A space or tab must separate the hex address and the binary filename.

---

## ⚡ Loading into Ark Flasher

Ark Flasher supports loading your project files in two ways:

1. **Local Mode**: Click **Browse Folder...** to point to the repository root directory on your computer.
2. **GitHub Mode**: Paste the repository URL (e.g., `https://github.com/your-username/your-project`) in the **Path or GitHub Repo URL** field and click **Load / Sync**. If the project is private, provide a GitHub Personal Access Token in the **GitHub Token (Optional)** field.

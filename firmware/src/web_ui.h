#ifndef WEB_UI_H
#define WEB_UI_H

const char* WEB_UI_HTML = R"rawhtml(
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ArkFlasher S3 Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-main: #0f172a;
            --bg-panel: #1e293b;
            --bg-card: #334155;
            --fg-text: #f8fafc;
            --fg-text-muted: #94a3b8;
            --accent: #2563eb;
            --accent-hover: #1d4ed8;
            --accent-green: #10b981;
            --accent-yellow: #f59e0b;
            --accent-red: #ef4444;
            --border: #475569;
        }
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-main);
            color: var(--fg-text);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        header {
            background-color: var(--bg-panel);
            border-bottom: 1px solid var(--border);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo-container {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        .logo-icon {
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, var(--accent), var(--accent-green));
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 1.2rem;
            color: white;
            box-shadow: 0 4px 10px rgba(37, 99, 235, 0.3);
        }
        .logo-text {
            font-size: 1.25rem;
            font-weight: 700;
            letter-spacing: -0.025em;
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }
        .logo-text span {
            color: var(--accent-green);
        }
        .system-status {
            display: flex;
            align-items: center;
            gap: 1.5rem;
        }
        .status-badge {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            background-color: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 500;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--accent-red);
            box-shadow: 0 0 8px var(--accent-red);
            animation: pulse 2s infinite;
        }
        .status-dot.connected {
            background-color: var(--accent-green);
            box-shadow: 0 0 8px var(--accent-green);
        }
        .status-dot.syncing {
            background-color: var(--accent-yellow);
            box-shadow: 0 0 8px var(--accent-yellow);
        }
        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.5; }
            50% { transform: scale(1.05); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.5; }
        }
        main {
            flex: 1;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            padding: 2rem;
            max-width: 1400px;
            margin: 0 auto;
            width: 100%;
        }
        @media (max-width: 1024px) {
            main {
                grid-template-columns: 1fr;
            }
        }
        .panel {
            background-color: var(--bg-panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
            height: 100%;
        }
        h2 {
            font-size: 1.1rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--fg-text-muted);
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 0.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .control-group {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        .card {
            background-color: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            transition: all 0.2s ease;
        }
        .card:hover {
            border-color: rgba(255, 255, 255, 0.3);
        }
        .card-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }
        label {
            font-weight: 500;
            font-size: 0.95rem;
        }
        input[type="text"] {
            background-color: var(--bg-main);
            border: 1px solid var(--border);
            color: var(--fg-text);
            padding: 0.5rem 0.75rem;
            border-radius: 6px;
            font-family: 'JetBrains Mono', monospace;
            width: 100px;
            text-align: right;
        }
        input[type="text"]:focus {
            border-color: var(--accent);
            outline: none;
        }
        .file-dropzone {
            border: 2px dashed var(--border);
            background-color: rgba(255, 255, 255, 0.01);
            border-radius: 6px;
            padding: 1rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s ease;
            position: relative;
        }
        .file-dropzone:hover, .file-dropzone.dragover {
            border-color: var(--accent);
            background-color: rgba(37, 99, 235, 0.05);
        }
        .file-dropzone input[type="file"] {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            opacity: 0;
            cursor: pointer;
        }
        .dropzone-text {
            font-size: 0.85rem;
            color: var(--fg-text-muted);
        }
        .dropzone-text span {
            color: var(--accent);
            font-weight: 500;
        }
        .file-info {
            display: none;
            align-items: center;
            justify-content: space-between;
            background-color: rgba(255, 255, 255, 0.05);
            padding: 0.5rem;
            border-radius: 4px;
            font-size: 0.8rem;
            margin-top: 0.25rem;
        }
        .file-name {
            font-family: 'JetBrains Mono', monospace;
            text-overflow: ellipsis;
            white-space: nowrap;
            overflow: hidden;
            max-width: 250px;
        }
        .file-remove {
            color: var(--accent-red);
            cursor: pointer;
            font-weight: bold;
        }
        .action-buttons {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin-top: 1rem;
        }
        .btn {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.95rem;
            cursor: pointer;
            transition: all 0.15s ease;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 0.5rem;
            color: white;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .btn-primary {
            background-color: var(--accent);
        }
        .btn-primary:hover:not(:disabled) {
            background-color: var(--accent-hover);
        }
        .btn-secondary {
            background-color: var(--border);
        }
        .btn-secondary:hover:not(:disabled) {
            background-color: #576579;
        }
        .btn-green {
            background-color: var(--accent-green);
        }
        .btn-green:hover:not(:disabled) {
            background-color: #059669;
        }
        .btn-red {
            background-color: var(--accent-red);
        }
        .btn-red:hover:not(:disabled) {
            background-color: #dc2626;
        }
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            box-shadow: none;
        }
        .progress-container {
            margin-top: 0.5rem;
            background-color: var(--bg-main);
            border: 1px solid var(--border);
            height: 10px;
            border-radius: 9999px;
            overflow: hidden;
            display: none;
        }
        .progress-bar {
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, var(--accent), var(--accent-green));
            border-radius: 9999px;
            transition: width 0.3s ease;
        }
        .console-container {
            display: flex;
            flex-direction: column;
            flex: 1;
            background-color: var(--bg-main);
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
            height: 400px;
        }
        .console-header {
            background-color: rgba(255, 255, 255, 0.02);
            border-bottom: 1px solid var(--border);
            padding: 0.5rem 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .console-title {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--fg-text-muted);
            font-family: 'JetBrains Mono', monospace;
        }
        .console-clear {
            font-size: 0.75rem;
            color: var(--accent);
            cursor: pointer;
            font-family: 'JetBrains Mono', monospace;
            background: none;
            border: none;
        }
        .console-output {
            flex: 1;
            padding: 1rem;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            line-height: 1.5;
            color: #d1d5db;
            background-color: #0b0f19;
        }
        .log-entry {
            margin-bottom: 0.25rem;
        }
        .log-info { color: #d1d5db; }
        .log-success { color: var(--accent-green); }
        .log-warn { color: var(--accent-yellow); }
        .log-err { color: var(--accent-red); }
        
        .board-preset {
            background-color: var(--bg-main);
            border: 1px solid var(--border);
            color: var(--fg-text);
            padding: 0.5rem;
            border-radius: 6px;
            font-size: 0.9rem;
            width: 100%;
        }
    </style>
</head>
<body>
    <header>
        <div class="logo-container">
            <div class="logo-icon">&#x26A1;</div>
            <div class="logo-text">ArkFlasher <span>S3</span></div>
        </div>
        <div class="system-status">
            <div class="status-badge">
                Target USB OTG: <span class="status-dot" id="usb-dot"></span> <span id="usb-status">Disconnect</span>
            </div>
        </div>
    </header>

    <main>
        <!-- Control Panel -->
        <div class="panel">
            <h2>Board Configuration</h2>
            
            <div class="control-group">
                <label for="board-preset">Target Board Template</label>
                <select id="board-preset" class="board-preset" onchange="onPresetChange()">
                    <option value="custom">Custom Presets / Manual Offsets</option>
                    <option value="esp32" selected>ESP32 DevKit (0x1000, 0x8000, 0x10000)</option>
                    <option value="esp32s3">ESP32-S3 JTAG/Serial JTAG (0x0, 0x8000, 0x10000)</option>
                    <option value="esp32c3">ESP32-C3 JTAG/Serial JTAG (0x0, 0x8000, 0x10000)</option>
                </select>
            </div>

            <h2>Upload Firmware Binaries</h2>

            <div class="control-group">
                <!-- Bootloader -->
                <div class="card">
                    <div class="card-row">
                        <label>Bootloader</label>
                        <input type="text" id="offset-bootloader" value="0x1000">
                    </div>
                    <div class="file-dropzone" id="dz-bootloader">
                        <input type="file" id="file-bootloader" onchange="handleFileSelected(this, 'bootloader')">
                        <div class="dropzone-text">Drag bin file here or <span>browse</span></div>
                    </div>
                    <div class="file-info" id="info-bootloader">
                        <span class="file-name" id="name-bootloader"></span>
                        <span class="file-remove" onclick="removeFile('bootloader')">&times;</span>
                    </div>
                </div>

                <!-- Partitions -->
                <div class="card">
                    <div class="card-row">
                        <label>Partition Table</label>
                        <input type="text" id="offset-partition" value="0x8000">
                    </div>
                    <div class="file-dropzone" id="dz-partition">
                        <input type="file" id="file-partition" onchange="handleFileSelected(this, 'partition')">
                        <div class="dropzone-text">Drag bin file here or <span>browse</span></div>
                    </div>
                    <div class="file-info" id="info-partition">
                        <span class="file-name" id="name-partition"></span>
                        <span class="file-remove" onclick="removeFile('partition')">&times;</span>
                    </div>
                </div>

                <!-- Application Firmware -->
                <div class="card">
                    <div class="card-row">
                        <label>Application (.bin)</label>
                        <input type="text" id="offset-app" value="0x10000">
                    </div>
                    <div class="file-dropzone" id="dz-app">
                        <input type="file" id="file-app" onchange="handleFileSelected(this, 'app')">
                        <div class="dropzone-text">Drag bin file here or <span>browse</span></div>
                    </div>
                    <div class="file-info" id="info-app">
                        <span class="file-name" id="name-app"></span>
                        <span class="file-remove" onclick="removeFile('app')">&times;</span>
                    </div>
                </div>
            </div>

            <div class="action-buttons">
                <button class="btn btn-secondary" id="btn-sync" onclick="syncTarget()">Sync Board</button>
                <button class="btn btn-primary" id="btn-flash" onclick="startStreamFlash()" disabled>Flash</button>
            </div>
            
            <div class="progress-container" id="prog-container">
                <div class="progress-bar" id="prog-bar"></div>
            </div>
        </div>

        <!-- Terminal Panel -->
        <div class="panel">
            <h2>Console Logs & Output</h2>
            <div class="console-container">
                <div class="console-header">
                    <span class="console-title">Flasher Terminal</span>
                    <button class="console-clear" onclick="clearConsole()">Clear</button>
                </div>
                <div class="console-output" id="console-out">
                    <div class="log-entry log-info">[INFO] ArkFlasher S3 system initialized.</div>
                    <div class="log-entry log-info">[INFO] Connect target to OTG USB port and click 'Sync Board'.</div>
                </div>
            </div>
            <div class="action-buttons">
                <button class="btn btn-secondary" onclick="resetTarget()">Reset Target</button>
                <button class="btn btn-red" onclick="abortFlash()" id="btn-abort" disabled>Abort</button>
            </div>
        </div>
    </main>

    <script>
        const files = {
            bootloader: null,
            partition: null,
            app: null
        };
        
        let isFlashing = false;
        let ws = null;
        let eventSource = null;

        // Auto connect system logs SSE / WebSocket
        function setupStatusUpdates() {
            // Check status every 2 seconds
            setInterval(async () => {
                try {
                    let res = await fetch('/api/status');
                    let data = await res.json();
                    
                    const dot = document.getElementById('usb-dot');
                    const text = document.getElementById('usb-status');
                    
                    if (data.connected) {
                        dot.className = "status-dot connected";
                        text.innerText = "Connected (" + data.device_name + ")";
                    } else if (data.syncing) {
                        dot.className = "status-dot syncing";
                        text.innerText = "Syncing...";
                    } else {
                        dot.className = "status-dot";
                        text.innerText = "Disconnected";
                    }
                    
                    // Update flash button state
                    document.getElementById('btn-flash').disabled = isFlashing || !data.connected || (!files.bootloader && !files.partition && !files.app);
                } catch (e) {
                    console.error("Failed to fetch target status", e);
                }
            }, 2000);

            // Fetch live console logs via Server-Sent Events
            eventSource = new EventSource('/api/logs');
            eventSource.onmessage = function(event) {
                const log = JSON.parse(event.data);
                logText(log.message, log.level || 'info');
            };
            eventSource.onerror = function() {
                // Ignore disconnect warnings
            };
        }

        window.onload = function() {
            setupStatusUpdates();
            setupDragAndDrop();
        };

        function logText(text, level = 'info') {
            const out = document.getElementById('console-out');
            const entry = document.createElement('div');
            entry.className = `log-entry log-${level}`;
            entry.innerText = `[${level.toUpperCase()}] ${text}`;
            out.appendChild(entry);
            out.scrollTop = out.scrollHeight;
        }

        function clearConsole() {
            document.getElementById('console-out').innerHTML = '';
        }

        function onPresetChange() {
            const preset = document.getElementById('board-preset').value;
            const bootOffset = document.getElementById('offset-bootloader');
            const partOffset = document.getElementById('offset-partition');
            const appOffset = document.getElementById('offset-app');
            
            if (preset === 'esp32') {
                bootOffset.value = '0x1000';
                partOffset.value = '0x8000';
                appOffset.value = '0x10000';
            } else if (preset === 'esp32s3' || preset === 'esp32c3') {
                bootOffset.value = '0x0';
                partOffset.value = '0x8000';
                appOffset.value = '0x10000';
            }
        }

        function setupDragAndDrop() {
            ['bootloader', 'partition', 'app'].forEach(type => {
                const zone = document.getElementById(`dz-${type}`);
                
                ['dragenter', 'dragover'].forEach(eventName => {
                    zone.addEventListener(eventName, (e) => {
                        e.preventDefault();
                        zone.classList.add('dragover');
                    }, false);
                });

                ['dragleave', 'drop'].forEach(eventName => {
                    zone.addEventListener(eventName, (e) => {
                        e.preventDefault();
                        zone.classList.remove('dragover');
                    }, false);
                });

                zone.addEventListener('drop', (e) => {
                    const dt = e.dataTransfer;
                    const rFiles = dt.files;
                    if (rFiles.length) {
                        const input = document.getElementById(`file-${type}`);
                        input.files = rFiles;
                        handleFileSelected(input, type);
                    }
                });
            });
        }

        function handleFileSelected(input, type) {
            if (input.files.length) {
                const file = input.files[0];
                files[type] = file;
                
                document.getElementById(`dz-${type}`).style.display = 'none';
                document.getElementById(`info-${type}`).style.display = 'flex';
                document.getElementById(`name-${type}`).innerText = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
                
                logText(`Stage file for ${type}: ${file.name}`, 'info');
            }
        }

        function removeFile(type) {
            files[type] = null;
            document.getElementById(`file-${type}`).value = '';
            document.getElementById(`dz-${type}`).style.display = 'block';
            document.getElementById(`info-${type}`).style.display = 'none';
            logText(`Removed file for ${type}`, 'info');
        }

        async function syncTarget() {
            logText("Requesting connection/synchronization with target...", "info");
            try {
                let res = await fetch('/api/connect', { method: 'POST' });
                let resp = await res.json();
                if (resp.success) {
                    logText("Target Synced successfully! ID: " + resp.chip_desc, "success");
                } else {
                    logText("Sync failed: " + resp.error, "err");
                }
            } catch (e) {
                logText("Failed to query target sync: " + e.message, "err");
            }
        }

        async function resetTarget() {
            logText("Requesting target reset...", "info");
            try {
                let res = await fetch('/api/reset', { method: 'POST' });
                let resp = await res.json();
                if (resp.success) {
                    logText("Target reset triggered successfully.", "success");
                } else {
                    logText("Reset failed: " + resp.error, "err");
                }
            } catch (e) {
                logText("Failed to request reset: " + e.message, "err");
            }
        }

        function updateProgress(pct) {
            const container = document.getElementById('prog-container');
            const bar = document.getElementById('prog-bar');
            container.style.display = 'block';
            bar.style.width = pct + '%';
        }

        async function startStreamFlash() {
            if (isFlashing) return;
            
            // Collect selected files
            const jobs = [];
            if (files.bootloader) jobs.push({ type: 'bootloader', offset: document.getElementById('offset-bootloader').value, file: files.bootloader });
            if (files.partition) jobs.push({ type: 'partition', offset: document.getElementById('offset-partition').value, file: files.partition });
            if (files.app) jobs.push({ type: 'app', offset: document.getElementById('offset-app').value, file: files.app });
            
            if (jobs.length === 0) {
                logText("No files selected to flash!", "warn");
                return;
            }
            
            isFlashing = true;
            document.getElementById('btn-flash').disabled = true;
            document.getElementById('btn-abort').disabled = false;
            updateProgress(0);
            
            logText("Init flash sequence...", "info");
            
            for (let i = 0; i < jobs.length; i++) {
                const job = jobs[i];
                logText(`Flashing ${job.type} upload started to offset ${job.offset}...`, "info");
                
                try {
                    // Send binary in stream chunks via POST request
                    const targetAddr = job.offset;
                    const res = await fetch(`/api/flash?address=${targetAddr}&size=${job.file.size}`, {
                        method: 'POST',
                        body: job.file,
                        headers: {
                            'Content-Type': 'application/octet-stream'
                        }
                    });
                    
                    const result = await res.json();
                    if (result.success) {
                        logText(`Successfully flashed ${job.type}`, "success");
                        updateProgress(((i + 1) / jobs.length) * 100);
                    } else {
                        logText(`Failed to flash ${job.type}: ${result.error}`, "err");
                        alert(`Flashing error on ${job.type}: ${result.error}`);
                        break;
                    }
                } catch (e) {
                    logText(`Streaming error during ${job.type}: ${e.message}`, "err");
                    break;
                }
            }
            
            isFlashing = false;
            document.getElementById('btn-flash').disabled = false;
            document.getElementById('btn-abort').disabled = true;
            logText("Flashing sequence finished.", "info");
        }

        async function abortFlash() {
            logText("Aborting current flash...", "warn");
            try {
                let res = await fetch('/api/abort', { method: 'POST' });
                let resp = await res.json();
                if (resp.success) {
                    isFlashing = false;
                    document.getElementById('btn-flash').disabled = false;
                    document.getElementById('btn-abort').disabled = true;
                    logText("Current operations cancelled.", "warn");
                }
            } catch (e) {
                logText("Abort error: " + e.message, "err");
            }
        }
    </script>
</body>
</html>
)rawhtml";

#endif

Offline IFC -> USDZ Converter

Internet access policy:
- Bundle start scripts enforce offline mode.
- Outbound network connections are blocked by the runtime launcher.
- Only local access (localhost/127.0.0.1) is expected for browser UI.

Runtime packaging:
- macOS bundle includes portable Python runtime in config/.offline_python
- start.command/start.py do one-time runtime preparation (not on every launch)

Working folders:
- Source IFC files are stored in flash drive root folder: ifc
- Converted USDZ files are stored in flash drive root folder: usdz
- By default root is parent directory of the app bundle (example: /Volumes/gip_vision)
- Environment update/cleanup does not delete ifc/usdz folders and does not remove files inside them

macOS (recommended start):
1. Open Terminal.
2. Go to bundle folder:
   cd /Volumes/gip_vision/gip-vision-offline-usb-macos-arm64
3. Run one of commands:
   python start.py
   python3 start.py
4. Open in browser:
   http://127.0.0.1:8765

Windows:
1. Open Command Prompt (cmd).
2. Go to bundle folder.
3. Run:
   run.bat
4. Open in browser:
   http://127.0.0.1:8765

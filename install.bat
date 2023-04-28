@Echo off
pyinstaller --console --clean --add-data "vmManagerConfig.json;." vm_manager.py
rmdir /s /q "build"
Pause
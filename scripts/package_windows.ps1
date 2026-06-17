$ErrorActionPreference = "Stop"

python -m pip install pyinstaller
python -m PyInstaller `
  --name SmartVoice `
  --onedir `
  --console `
  --add-data "resources;resources" `
  smartvoice\__main__.py

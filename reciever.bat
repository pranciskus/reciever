@echo off

set "dir=%~dp0"

cd "%dir%"

echo %cd%

python.exe --version

if not exist "server.json" (
  REM add demo mod
  copy mod.json.tpl mod.json
  REM install pip
  python.exe ..\get-pip.py
  REM insta install dependencies
  python.exe -m pip install -r requirements.txt
  
  python.exe reciever.py --admin
) else (
  python.exe reciever.py --admin
)

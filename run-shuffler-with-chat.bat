@ECHO OFF
REM Run YouTube chat logger in background in the same console
start /B python chat_logger.py

REM Run EmuHawk with your shuffler Lua script
..\EmuHawk.exe --lua=shuffler.lua

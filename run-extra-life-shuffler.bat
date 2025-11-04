@ECHO OFF
REM Run YT chat logger / EL donation tracker in background in the same console
start /B python3 extra_life.py

REM Run EmuHawk with your shuffler Lua script
..\EmuHawk.exe --lua=shuffler.lua

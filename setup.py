import sys
from cx_Freeze import setup, Executable


#python C:\Users\Users\AppData\Local\Programs\Python\Python36-32\Scripts\cxfreeze main.py --target-dir=dist


# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {"packages": ["os","idna"], "excludes": ["tkinter"],
'include_msvcr': True}

# GUI applications require a different base on Windows (the default is for a
# console application).
base = None

setup(  name = "Cryptopia Pump and Dump Bot",
        version = "0.1",
        description = "Pump and Dump Semi-Auto Assistant",
        options = {"build_exe": build_exe_options},
        executables = [Executable("main.py", base=base, shortcutName="Cryptopia Bot",
            shortcutDir="DesktopFolder", icon="icon.ico")])

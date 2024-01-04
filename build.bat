pyinstaller --onefile --noconsole --icon=dark.ico --name=tortle-stomp --add-data="dark.ico:." src/main.py
pyinstaller --onefile --icon=light.ico --name=tortle-stomp_debug --add-data="dark.ico:." src/main.py

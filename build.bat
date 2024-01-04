pyinstaller --onefile --noconsole --icon=dark.ico --name=tortle-stomp --add-data="dark.ico:." main.py
pyinstaller --onefile --icon=dark.ico --name=tortle-stomp_debug --add-data="dark.ico:." main.py

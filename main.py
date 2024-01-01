import re
import shutil
import tkinter as tk
from tkinter import ttk
import asyncio
import os
import subprocess
import json
from tkinter import filedialog
import psutil

# SETTINGS
COMPRESSION_TAG = 'ffmpeg'
OUTPUTROOT = os.path.join(os.path.abspath(os.getcwd()), 'bin')

with open('config.json') as f:
    config = json.load(f)

VCODEC = config['video_codec']
ACODEC = config['audio_codec']
CRF = config['constant_rate_factor']
PRESET = config['speed']
ABITRATE = config['bitrate']

INPUTROOT = config['inputRoot']

# MISC
COMPRESSION_COMMENT = f'{COMPRESSION_TAG} (-c:v {VCODEC} -crf {CRF} -preset {PRESET} -c:a {ACODEC} -b:a {ABITRATE})'
TURTLE_ASCII = '      ________    ____\n      /  \__/  \  |  {} |\n     |\__/  \__/|/ ___\|\n    < ___\__/___ _/     '
TURTLE_EYES = {
    'normal': 'o',
    'dead': 'x',
    'sleep': '–',
    'blink': '_'
}
TURTLE_FACE = '({0}\_/{0})'
POSES_ASCII = ['|_|_|  |_|_|', '|_|-/  |_|-/', '/-/_|  /-/_|']
SLEEP_EFFECT = '  ₂ z Z'


class App:
    async def exec(self):
        self.window = Window(asyncio.get_event_loop())
        await self.window.show()


class Window(tk.Tk):

    process = None
    isAlive = False
    isRunning = False

    directoryStack = [INPUTROOT]
    fileStack = []

    # tkinter
    def __init__(self, loop):
        self.loop = loop
        self.root = tk.Tk()

        self.root.title(TURTLE_FACE.format(TURTLE_EYES['sleep']) + SLEEP_EFFECT)

        self.animation = 0
        
        self.turtleBody = tk.Label(text=f'\n{TURTLE_ASCII.format(TURTLE_EYES["blink"])}', font=('Consolas', 8))
        self.turtleBody.grid(row=0, columnspan=2, padx=(8, 8), pady=(8, 0))

        self.turtleLegs = tk.Label(text='', font=('Consolas', 8))
        self.turtleLegs.grid(row=1, columnspan=2, padx=(8, 8), pady=(0, 4))

        self.statusLabel = tk.Label(text='')
        self.statusLabel.grid(row=2, columnspan=2, padx=(8, 8), pady=(0, 0))
        
        self.progressbar = ttk.Progressbar(length=280)
        self.progressbar.grid(row=3, columnspan=2, padx=(8, 8), pady=(4, 0))
        
        self.startButton = tk.Button(text="Start", width=10, command=lambda: self.loop.create_task(self.handleStartAbortButtonClick()))
        self.startButton.grid(row=4, column=0, sticky=tk.W, padx=8, pady=8)

        self.pauseButton = tk.Button(text="Pause", width=10, command=lambda: self.loop.create_task(self.handlePlayPauseButtonClick()), state='disabled')
        self.pauseButton.grid(row=4, column=1, sticky=tk.W, padx=8, pady=8)

        self.stream = asyncio.StreamReader()

    async def show(self):
        # ANIMATION
        try:
            while True:
                self.root.update()
                await asyncio.sleep(0.1)
        except:
            pass

    async def playAnimation(self): 
        while (self.isRunning):
            self.turtleLegs['text'] = POSES_ASCII[self.animation]
            self.animation = (self.animation + 1) if (self.animation + 1 < len(POSES_ASCII)) else 0
            await asyncio.sleep(0.5)

    async def handleStartAbortButtonClick(self):
        if (self.isAlive):
            # abort
            self.process.terminate()
            self.process = None
            self.isAlive = False

            #TODO store all tasks and cancel them here
        else:
            # start
            filepath = filedialog.askdirectory()

            if (filepath):
                self.directoryStack = [filepath]
                self.fileStack = []

                self.loop.create_task(self.getNextFile())
                self.isAlive = True

                self.startButton['text'] = 'Abort'
                self.statusLabel['fg'] = 'black'
                self.turtleBody['text'] = TURTLE_ASCII.format(TURTLE_EYES['normal'])
                self.root.title(TURTLE_FACE.format(TURTLE_EYES['normal']))
                self.turtleBody['fg'] = 'black'
                self.turtleLegs['fg'] = 'black'
                self.pauseButton['state'] = 'normal'
            else:
                self.handleError()


    async def handlePlayPauseButtonClick(self):
        
        if (self.process):
            if (self.isRunning):
                # pause
                psutil.Process(self.process.pid).suspend()

                self.pauseButton['text'] = 'Resume'

            else:
                # resume
                psutil.Process(self.process.pid).resume()

                self.pauseButton['text'] = 'Pause'
                self.loop.create_task(self.playAnimation())

            self.isRunning = not self.isRunning


    # ffmpeg
    async def getNextFile(self):

        self.startButton['text'] = 'Abort'
        
        if (len(self.fileStack) > 0):
            # process files
            
            file = self.fileStack.pop()

            task = self.loop.create_task(self.compressFile(file))

        else:
            # fetch more files
            if (len(self.directoryStack) > 0):
                currentDirectory = self.directoryStack.pop()
                for dir in os.listdir(currentDirectory):

                    fullPath = os.path.join(currentDirectory, dir)
                    
                    # get future directories
                    if (os.path.isdir(fullPath)):
                        self.directoryStack.append(fullPath)

                    # get files
                    else:
                        # only process mp4 files
                        if (fullPath.endswith('.mp4')):
                            self.fileStack.append(fullPath)
            
            else:
                print('DONE')
                self.statusLabel['text'] = 'DONE :D'
                self.statusLabel['fg'] = 'green'
                self.startButton['text'] = 'Start'
                self.turtleLegs['text'] = ''
                self.turtleBody['text'] = f'\n{TURTLE_ASCII.format(TURTLE_EYES["blink"])}'
                self.root.title(TURTLE_FACE.format(TURTLE_EYES['sleep']) + SLEEP_EFFECT)
                self.isAlive = False
                return # done

            await self.getNextFile()

    async def compressFile(self, file):
        
        print(file)
        self.statusLabel['text'] = file

        # trigger GUI handler
        self.isRunning = True
        self.loop.create_task(self.playAnimation())

        inputFile = file
        outputFile = os.path.join(OUTPUTROOT, "temp.mp4")

        try:
            # READ METADATA
            cmd = [
                'ffprobe',
                '-v', 'quiet', '-loglevel', 'error',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                inputFile
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if (result.returncode != 0):
                raise Exception(f'ffprobe failed with code {result.returncode}')
            
            metadata = json.loads(result.stdout)

            if ((comment := metadata['format']['tags'].get('comment')) != None) and (COMPRESSION_TAG in comment):
                # already compressed
                print(f'\t\tINFO: file has already been compressed (skipping)')

            else:
                # COMPRESS FILE
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', inputFile,
                    '-c:v', VCODEC,
                    '-crf', CRF,
                    '-preset', PRESET,
                    '-c:a', ACODEC,       # audio codec
                    '-b:a', ABITRATE,
                    '-metadata', f'comment={COMPRESSION_COMMENT}',
                    '-x265-params', 'log-level=quiet'
                ]

                for key, value in metadata['format']['tags'].items():
                    # metadata
                    cmd.append('-metadata')
                    cmd.append(f'{key}={value}')

                # output file
                cmd.append(outputFile)

                self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)

                # trigger progress handler
                self.loop.create_task(self.handleOutput(int(metadata['streams'][0]['nb_frames'])))

                while (self.process.poll() is None):
                    await asyncio.sleep(0)

                # HANDLE RESULT
                inputFileSize = os.path.getsize(file)
                outputFileSize = os.path.getsize(outputFile)

                if (outputFileSize >= inputFileSize):
                    print(f'\t\tERROR: result is not smaller than source')
                    os.remove(outputFile)
                
                else:
                    # copy new file to input directory
                    shutil.move(outputFile, inputFile)# TODO this is not working correctly with metadata

            self.isRunning = False
            self.loop.create_task(self.getNextFile())

        except Exception as e:
            print(e)
            self.handleError()


    async def handleOutput(self, targetFrames):

        loop = asyncio.get_event_loop()

        while True:
            line = await loop.run_in_executor(None, self.process.stdout.readline)
            if not line:
                break

            match = re.search(r'frame=\s*(\d+)', line)
            if (match):
                self.progressbar['value'] = (int(match.group(1)) / targetFrames) * 100

            await asyncio.sleep(0)


    def handleError(self):
        self.isRunning = False
        self.isAlive = False
        self.statusLabel['text'] = 'ERROR :ᗡ'
        self.statusLabel['fg'] = 'red'
        self.turtleBody['text'] = TURTLE_ASCII.format(TURTLE_EYES["dead"])
        self.root.title(TURTLE_FACE.format(TURTLE_EYES['dead']) + '  F')
        self.turtleBody['fg'] = 'red'
        self.turtleLegs['fg'] = 'red'
        self.startButton['text'] = 'Start'
        self.pauseButton['state'] = 'disabled'

asyncio.run(App().exec())

# TODO
# - logging
# - better UI
# - stats
# - autorun
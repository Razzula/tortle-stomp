import asyncio
import datetime
import json
import math
import os
import psutil
import re
import shutil
import subprocess
import sys
import time
import tkinter as tk
import winreg as wr
from idlelib.tooltip import Hovertip
from mutagen.mp4 import MP4
from tkinter import filedialog, messagebox, ttk
from enum import Enum

# SETTINGS
APPLICATION_NAME = 'tortle-stomp'
LOCAL_DIR = os.path.dirname(sys.executable) if hasattr(sys, '_MEIPASS') else os.path.dirname(__file__)
PROGRAM_PATH = os.path.abspath(os.path.join(LOCAL_DIR, f'{APPLICATION_NAME}.exe'))
STARTUP_REGISTRY_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'

COMPRESSION_TAG = 'ffmpeg'
OUTPUTROOT = os.path.join(LOCAL_DIR, 'temp')
LOG_DIR = os.path.join(LOCAL_DIR, 'logs')
CONFIG_PATH = os.path.join(LOCAL_DIR, 'config.json')

# MISC
COMMENT_TEMPLATE = '{} (-c:v {} -crf {} -preset {} -c:a {} -b:a {})'
TURTLE_ASCII = '      ________    ____\n      /  \__/  \  |  {} |\n     |\__/  \__/|/ ___\|\n    < ___\__/___ _/     '
TURTLE_EYES = {
    'normal': 'o',
    'dead': 'x',
    'sleep': '–',
    'blink': '_'
}
TURTLE_FACE = '({0}\_/{0})  {1}'
POSES_ASCII = ['|_|_|  |_|_|', '|_|-/  |_|-/', '/-/_|  /-/_|']
SLEEP_EFFECT = '  ₂ z Z'

FFMPEG_SPEEDS = {
    'default': ['veryslow', 'slower', 'slow', 'medium', 'fast', 'faster', 'veryfast', 'superfast', 'ultrafast'],
    'nvenc': ['slow', 'medium', 'fast']
}

class FileSizeUnit(Enum):
    KB = 10 ** 3
    MB = 10 ** 6
    GB = 10 ** 9

class App:
    """
    Main application
    """

    async def exec(self):
        """
        Start application
        """
        print(PROGRAM_PATH)

        print(CONFIG_PATH)
        if (not os.path.exists(CONFIG_PATH)):
            with open(CONFIG_PATH, 'w') as f:
                json.dump({}, f, indent=4)

        if (not os.path.exists(OUTPUTROOT)):
            os.mkdir(OUTPUTROOT)

        if (not os.path.exists(LOG_DIR)):
            os.mkdir(LOG_DIR)

        try:
            self.window = MainWindow(asyncio.get_event_loop())
            await self.window.show()
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up tasks, including subprocesses
            asyncio.gather(*asyncio.all_tasks(), return_exceptions=True).cancel()


class MainWindow(tk.Tk):
    """
    Main tkinter window
    """

    process = None
    isAlive = False
    isRunning = False

    directoryStack = []
    fileStack = []


    # tkinter
    def __init__(self, loop):
        """
        Initialize the tkinter window
        """

        self.loop = loop
        self.root = tk.Tk()

        # WINDOW
        self.root.geometry("545x190")
        self.root.resizable(width=False, height=False)

        self.root.columnconfigure(0, minsize=76, weight=1)
        self.root.columnconfigure(1, minsize=76, weight=1)
        self.root.columnconfigure(2, weight=2)
        self.root.columnconfigure(3, minsize=76, weight=1)
        self.root.columnconfigure(4, minsize=76, weight=1)

        if (getattr(sys, 'frozen', False)):
            # bundled
            self.root.iconbitmap(default=os.path.join(sys._MEIPASS, 'dark.ico'))
        else:
            self.root.iconbitmap(default='dark.ico')
        self.root.title(TURTLE_FACE.format(TURTLE_EYES['sleep'], SLEEP_EFFECT))

        # CONTROLS
        # turtle
        self.turtleBody = tk.Label(text=f'\n{TURTLE_ASCII.format(TURTLE_EYES["blink"])}', font=('Consolas', 8))
        self.turtleBody.grid(row=0, column=2, padx=(8, 8), pady=(0, 0))

        self.turtleLegs = tk.Label(text='', font=('Consolas', 8))
        self.turtleLegs.grid(row=1, column=2, padx=(8, 8), pady=(0, 4))

        # feedback
        self.statusLabel = tk.Label(text='')
        self.statusLabel.grid(row=2, columnspan=5, padx=(8, 8), pady=(0, 0))
        
        self.progressbar = ttk.Progressbar(length=360)
        self.progressbar.grid(row=3, column=1, columnspan=3, padx=(8, 8), pady=(4, 0))
        
        # buttons
        self.startButton = tk.Button(text="Start", width=10, command=lambda: self.loop.create_task(self.handleStartAbortButtonClick()))
        self.startButton.grid(row=4, column=1, sticky='E', padx=0, pady=8)

        self.pauseButton = tk.Button(text="Pause", width=10, command=lambda: self.loop.create_task(self.handlePlayPauseButtonClick()), state='disabled')
        self.pauseButton.grid(row=4, column=3, sticky=tk.W, padx=0, pady=8)

        self.settingsButton = tk.Button(text="Settings", width=10, command=self.openSettingsWindow)
        self.settingsWindow = None
        self.settingsButton.grid(row=0, column=0, padx=2, pady=0, sticky="w")

        # stats
        self.originalSizeLabel = tk.Label(text='0.00 KB')
        self.originalSizeLabel.grid(row=3, column=0, sticky='E', padx=12, pady=0)
        self.originalFileSize = 0

        self.newSizeLabel = tk.Label(text='0.00 KB')
        self.newSizeLabel.grid(row=3, column=4, sticky=tk.W, padx=12, pady=0)
        self.newFileSize = 0

        self.timerLabel = tk.Label(text='0:00:00  |  0.0%  |  0:00:00')
        self.timerLabel.grid(row=4, column=2, sticky='EW', padx=0, pady=0)
        self.currentFileTime = 0
        self.currentProcessTime = 0
        self.timeOfLastCheck = 0

        # VARIABLES
        self.animation = 0

        # AUTORUN
        self.loop.create_task(self.handleAutorun())


    async def show(self):
        """
        Display the tkinter window
        """
        try:
            while True:
                self.root.update()
                await asyncio.sleep(0.1)
        except:
            pass # gracefully exit


    def loadSettings(self):
        """
        Load settings from config.json into class variables
        """

        # load data
        with open(CONFIG_PATH) as f:
            config = json.load(f)

        vcodec = config.get('video_codec', 'h265')

        self.acodec = config.get('audio_codec', 'libmp3lame')
        self.crf = config.get('constant_rate_factor', 0)
        self.speed = config.get('speed', 0)
        self.abitrate = config.get('bitrate', '320k')

        self.performanceMode = config.get('performanceMode', 0)

        self.autorun = config.get('autorunPath', None) if (config.get('autorun', False)) else False
        self.overwrite = config.get('overwrite', False)

        # hardware acceleration
        result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
        nvenc = 'nvenc' in result.stdout
        if (nvenc):
            if (vcodec == 'h265'):
                self.vcodec = 'hevc_nvenc' # NVIDIA NVENC hevc encoder (codec hevc)
            else:
                self.vcodec = 'h264_nvenc' # NVIDIA NVENC H.264 encoder (codec h264)
        else:
            if (vcodec == 'h265'):
                self.vcodec = 'libx265' # libx265 H.265 / HEVC (codec hevc)
            else:
                self.vcodec = 'libx264' # libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (codec h264)

        result = subprocess.run(['ffmpeg', '-hwaccels'], capture_output=True, text=True)
        self.cuda = ('cuda' in result.stdout)

        # speed
        presetConfig = 'nvenc' if nvenc else 'default'
        speed = round(self.speed / (len(FFMPEG_SPEEDS['default']) - 1) * (len(FFMPEG_SPEEDS[presetConfig]) - 1))
        self.preset = FFMPEG_SPEEDS[presetConfig][speed]

        # metadata
        self.compressionComment = COMMENT_TEMPLATE.format(COMPRESSION_TAG, self.vcodec, self.crf, self.preset, self.acodec, self.abitrate)



    def openSettingsWindow(self):
        """
        Open the settings window
        """
        if (self.isAlive):
            messagebox.showwarning("Warning", f"A compression process is currently in progress. \nAny changes made will not affect the current process.")

        if (self.settingsWindow):
            self.settingsWindow.focus_force()
        else:
            self.settingsWindow = SettingsWindow(self.loop, self)


    async def playAnimation(self): 
        """
        Play the turtle animation
        """
        while (self.isRunning):
            self.turtleLegs['text'] = POSES_ASCII[self.animation]
            self.animation = (self.animation + 1) if (self.animation + 1 < len(POSES_ASCII)) else 0

            if (self.timeOfLastCheck):
                currentTime = time.time()
                delta = currentTime - self.timeOfLastCheck
                self.currentFileTime += delta
                self.currentProcessTime += delta
                self.timeOfLastCheck = currentTime

                progress = round(self.progressbar['value'], 1)
                
                self.timerLabel['text'] = f'{self.formatTime(self.currentFileTime)}  |  {progress}%  |  {self.formatTime(self.currentProcessTime)}'

            await asyncio.sleep(0.5 - (0.45 * (self.speed / 8)))


    def formatTime(self, seconds):
        """
        Format seconds into a human-readable string
        """
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        hours = int(minutes // 60)
        minutes = int(minutes % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


    async def handleAutorun(self):
        """
        Trigger the process automatically if autorun is enabled
        """
        self.loadSettings()
        
        if (self.autorun):
            self.beginProcess(self.autorun)


    async def handleStartAbortButtonClick(self):
        """
        Start or abort the compression process
        """
        if (self.isAlive):
            # abort
            self.process.terminate()
            self.process = None
            self.isAlive = False

            await asyncio.sleep(0.1)
            self.progressbar['value'] = 0

            #TODO store all tasks and cancel them here
        else:
            # start
            self.beginProcess(filedialog.askdirectory())


    def beginProcess(self, filepath):
        """
        Start the compression process
        """
        # check ffmpeg is installed
        for command in ['ffmpeg', 'ffprobe']:
            try:
                result = subprocess.run([command, '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
                if (result.returncode != 0):
                    raise Exception(result.returncode)
            except:
                messagebox.showerror('Error', f'{command} is not installed. Please install it and try again.')
                return
        
        # check if settings are valid
        self.loadSettings()
        if (self.overwrite and self.crf > 18): # upper threshold for visually lossless is 18
            messagebox.showwarning('Warning', "Your current settings will result in a loss of quality! \n\nPlease consider disabling the 'Overwrite source' option or lowering the CRF value.")

        if (filepath):
            # final initialization
            self.directoryStack = [filepath]
            self.fileStack = []

            # start process
            self.currentProcessTime = 0
            self.timeOfLastCheck = time.time()
            self.loop.create_task(self.getNextFile())
            self.isAlive = True

            # output to GUI
            self.startButton['text'] = 'Abort'
            self.statusLabel['fg'] = 'black'
            self.turtleBody['text'] = TURTLE_ASCII.format(TURTLE_EYES['normal'])
            self.root.title(TURTLE_FACE.format(TURTLE_EYES['normal'], 'Plodding along...'))
            self.turtleBody['fg'] = 'black'
            self.turtleLegs['fg'] = 'black'
            self.pauseButton['state'] = 'normal'
        else:
            messagebox.showerror("Error", "No directory was selected.")
            self.handleError()


    async def handlePlayPauseButtonClick(self):
        """
        Pause or resume the compression process
        """ 
        if (self.process):
            if (self.isRunning):
                # pause
                psutil.Process(self.process.pid).suspend()

                self.pauseButton['text'] = 'Resume'
                self.root.title(TURTLE_FACE.format(TURTLE_EYES['sleep'], 'Taking a break...'))

            else:
                # resume
                self.timeOfLastCheck = time.time()

                psutil.Process(self.process.pid).resume()

                self.pauseButton['text'] = 'Pause'
                self.root.title(TURTLE_FACE.format(TURTLE_EYES['normal'], 'Plodding along...'))
                self.loop.create_task(self.playAnimation())


            self.isRunning = not self.isRunning


    # ffmpeg
    async def getNextFile(self):
        """
        Find and trigger compression of the next file
        This is the main loop, called cyclically by the application (as well as recursively by itself)
        """

        self.startButton['text'] = 'Abort'
        self.currentFileTime = 0
        
        if (len(self.fileStack) > 0):
            # process files
            
            file = self.fileStack.pop()
            self.loop.create_task(self.compressFile(file))

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
                self.handleDone('DONE :D')
                return # done

            await self.getNextFile()


    async def compressFile(self, file):
        """
        Compress a single file using ffmpeg
        """
        
        print(file)
        self.statusLabel['text'] = file

        availableCores =  os.cpu_count()
        if (self.performanceMode == 0):
            # background
            availableCores = 1
        elif (self.performanceMode == 1):
            # standard
            availableCores = max(1, math.floor(availableCores * 0.75))

        # trigger GUI handler
        self.isRunning = True
        self.loop.create_task(self.playAnimation())

        inputFile = file
        outputFile = os.path.join(OUTPUTROOT, 'data.mp4')

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
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if (result.returncode != 0):
                raise Exception(f'ffprobe failed with code {result.returncode}')
            
            metadata = json.loads(result.stdout)

            shouldCompress = True
            if ((comment := metadata['format']['tags'].get('comment')) != None) and (COMPRESSION_TAG in comment):
                # already compressed
                match = re.search(r'-crf (\d+) -preset (\w+)\)', comment)

                if (match):
                    crf = int(match.group(1))
                    preset = match.group(2)

                    if ((crf < self.crf) or (FFMPEG_SPEEDS['default'].index(preset) > FFMPEG_SPEEDS['default'].index(self.preset))):
                        print(f'\t\tINFO: file has already been compressed (trying with more aggressive settings)')
                    else:
                        shouldCompress = False
                        print(f'\t\tINFO: file has already been compressed (skipping)')

                else:
                    shouldCompress = False
                    print(f'\t\tINFO: file has already been compressed (skipping)')

            if (shouldCompress):
                originalFileSize = int(metadata['format']['size']) # in bytes

                if (originalFileSize > FileSizeUnit.GB.value):
                    self.originalFileSize = originalFileSize / FileSizeUnit.GB.value
                    fileSizeLabel = 'GB'
                elif (originalFileSize > FileSizeUnit.MB.value):
                    self.originalFileSize = originalFileSize / FileSizeUnit.MB.value
                    fileSizeLabel = 'MB'
                else:
                    self.originalFileSize = originalFileSize / FileSizeUnit.KB.value
                    fileSizeLabel = 'KB'

                self.originalSizeLabel['text'] = f'{self.originalFileSize:.2f} {fileSizeLabel}'
                self.newSizeLabel['fg'] = 'green'

                # COMPRESS FILE
                cmd = ['ffmpeg']

                if (self.cuda):
                    # hardware acceleration
                    cmd.append('-hwaccel')
                    cmd.append('cuda')

                for arg in [
                    '-y',
                    '-i', inputFile,
                    '-c:v', self.vcodec,
                    '-crf', str(self.crf),
                    '-cq', str(self.crf),
                    '-rc', 'vbr_hq',            # Variable Bit Rate with High Quality mode
                    '-b:v', '0',                # Set bitrate to 0 for VBR mode
                    '-preset', self.preset,
                    '-c:a', self.acodec,        # audio codec
                    '-b:a', self.abitrate,
                    '-threads', str(availableCores),
                    '-metadata', f'comment={self.compressionComment}',
                    '-x265-params', 'log-level=quiet'
                ]:
                    cmd.append(arg)

                for key, value in metadata['format']['tags'].items():
                    # metadata
                    cmd.append('-metadata')
                    cmd.append(f'{key}={value}')
                    pass

                # output file
                cmd.append(outputFile)

                self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True, creationflags=subprocess.CREATE_NO_WINDOW)
                print(' '.join(cmd))

                # limit resources
                self.setProcessPriority(list(range(availableCores)), [psutil.BELOW_NORMAL_PRIORITY_CLASS, psutil.NORMAL_PRIORITY_CLASS, psutil.REALTIME_PRIORITY_CLASS][self.performanceMode])

                # trigger progress handler
                self.loop.create_task(self.handleOutput(int(metadata['streams'][0]['nb_frames'])))

                while (self.process.poll() is None):
                    await asyncio.sleep(0)

                # HANDLE RESULT
                if (self.process.returncode != 0):
                    raise Exception(f'ffmpeg failed with code {self.process.returncode}')
                
                inputFileSize = os.path.getsize(file)
                outputFileSize = os.path.getsize(outputFile)

                if (outputFileSize >= inputFileSize):
                    print(f'\t\tERROR: result is not smaller than source')
                    os.remove(outputFile)

                    try:
                        sourceMp4 = MP4(inputFile)

                        # Set the comment field to the desired text
                        sourceMp4['\xa9cmt'] = f'< {self.compressionComment}'  # '\xa9cmt' is the atom for the comment field
                        sourceMp4.save()

                        print('\tMetadata updated successfully.')
                    except Exception as e:
                        print(f"\tError updating metadata: '{e}'")
                
                else:
                    if (self.overwrite):
                        print(f'\t\tINFO: overwriting source file')
                        shutil.move(outputFile, inputFile)
                        self.log([inputFile, f'{inputFileSize / 1000000:.2f} MB --> {outputFileSize / 1000000:.2f} MB'])
                    else:
                        print(f'\t\tINFO: saving to output directory')
                        fileName = os.path.basename(file)[:-4] #exclude .mp4
                        shutil.move(outputFile, os.path.join(os.path.dirname(inputFile), f'{fileName} (compressed).mp4'))
                        self.log([f'{inputFile} (--> ...(compressed))', f'{inputFileSize / 1000000:.2f} MB --> {outputFileSize / 1000000:.2f} MB'])

            self.isRunning = False
            self.loop.create_task(self.getNextFile())

        except Exception as e:
            if (not self.isAlive):
                self.handleDone() # error is due to abortion
            else:
                print(e)
                self.log([inputFile, f'ERROR: {e}'])
                self.handleError()


    def setProcessPriority(self, affinity, priority):
        """
        Set the priority of the ffmpeg process
        """
        if (self.process):
            psutil.Process(self.process.pid).cpu_affinity(affinity)
            psutil.Process(self.process.pid).nice(priority)


    async def handleOutput(self, targetFrames):
        """
        Display ffmpeg process' progress in the GUI
        """
        loop = asyncio.get_event_loop()

        while True:
            try:
                line = await loop.run_in_executor(None, self.process.stdout.readline)
            except:
                break
            if not line:
                break

            match = re.search(r'frame=\s*(\d+)', line)
            if (match):
                self.progressbar['value'] = (int(match.group(1)) / targetFrames) * 100
            match = re.search(r'size=\s*(\d+)kB', line)
            if (match):
                newFileSize = int(match.group(1)) * 1000 # in bytes

                if (newFileSize > FileSizeUnit.GB.value):
                    self.newFileSize = newFileSize / FileSizeUnit.GB.value
                    fileSizeLabel = 'GB'
                elif (newFileSize > FileSizeUnit.MB.value):
                    self.newFileSize = newFileSize / FileSizeUnit.MB.value
                    fileSizeLabel = 'MB'
                else:
                    self.newFileSize = newFileSize / FileSizeUnit.KB.value
                    fileSizeLabel = 'KB'

                self.newSizeLabel['text'] = f'{self.newFileSize:.2f} {fileSizeLabel}\n({int(self.newFileSize / self.originalFileSize * 100)}%)'

                if (self.newFileSize >= self.originalFileSize):
                    pass #TODO skip file


            await asyncio.sleep(0)


    def handleDone(self, message=''):
        """
        Display completion in the GUI
        """
        self.isAlive = False
        self.isRunning = False
        self.statusLabel['text'] = message
        self.statusLabel['fg'] = 'green'
        self.startButton['text'] = 'Start'
        self.turtleLegs['text'] = ''
        self.turtleBody['text'] = f'\n{TURTLE_ASCII.format(TURTLE_EYES["blink"])}'
        self.root.title(TURTLE_FACE.format(TURTLE_EYES['sleep'], SLEEP_EFFECT))
        self.pauseButton['state'] = 'disabled'


    def handleError(self):
        """
        Display error message in the GUI
        """
        self.isRunning = False
        self.isAlive = False
        self.statusLabel['text'] = 'ERROR :ᗡ'
        self.statusLabel['fg'] = 'red'
        self.turtleBody['text'] = TURTLE_ASCII.format(TURTLE_EYES["dead"])
        self.root.title(TURTLE_FACE.format(TURTLE_EYES['dead'], 'RIP'))
        self.turtleBody['fg'] = 'red'
        self.turtleLegs['fg'] = 'red'
        self.startButton['text'] = 'Start'
        self.pauseButton['state'] = 'disabled'

    
    def log(self, message):
        """
        Log a message to a file
        """
        date = datetime.datetime.now()
        fileName = os.path.join(LOG_DIR, f'{date.strftime("%d-%m-%Y")}.log')
        with open(fileName, 'a+') as f:
            f.write(f'{date.strftime("%H:%M:%S")} :\n')
            for line in message:
                f.write(f'\t\t{line}\n')


class SettingsWindow(tk.Tk):
    """
    Settings tkinter window
    """


    def __init__(self, loop, parent):
        """
        Initialize the tkinter window
        """
        super().__init__()

        self.loop = loop
        self.parent = parent

        # WINDOW
        self.resizable(width=False, height=False)
        self.title('Settings')

        self.protocol("WM_DELETE_WINDOW", self.onExit)

        # CONTROLS
        # autorun
        self.autorunLabel = tk.Label(self, text='Autorun:')
        self.autorunLabel.grid(row=0, column=0, sticky='E', padx=(10, 5), pady=(10, 0))

        self.autorunCheckbox = tk.Checkbutton(self, variable=tk.IntVar(name='autorun'), command=lambda: self.handleCheckboxClick(self.autorunCheckbox, 'autorun'))
        Hovertip(self.autorunCheckbox,'Should the compression process trigger automatically upon starting the application?', hover_delay=200)
        self.autorunCheckbox.grid(row=0, column=1, sticky='W', padx=(5, 10), pady=(10, 0))

        self.autorunDirEntry = tk.Entry(self, state='disabled', width=45)
        Hovertip(self.autorunDirEntry,'The directory which should be used when using autorun', hover_delay=200)
        self.autorunDirEntry.grid(row=1, column=0, columnspan=2, sticky='E', padx=(10, 5), pady=(0, 10))

        self.autorunDirButton = tk.Button(self, text='...', command=self.selectAutorunDirectory)
        self.autorunDirButton.grid(row=1, column=2, sticky='W', padx=(5, 10), pady=(0, 10))

        self.autorunLabel = tk.Label(self, text='Begin on Startup:')
        self.autorunLabel.grid(row=2, column=0, sticky='E', padx=(10, 5), pady=(2, 0))

        self.startupCheckbox = tk.Checkbutton(self, variable=tk.IntVar(name='startup'), command=lambda: self.handleCheckboxClick(self.startupCheckbox, 'startup'))
        Hovertip(self.startupCheckbox,'Should this application start automatically when your computer boots?', hover_delay=200)
        self.startupCheckbox.grid(row=2, column=1, sticky='W', padx=(5, 10), pady=(2, 0))

        # compression settings
        self.hr = ttk.Separator(self, orient='horizontal')
        self.hr.grid(row=3, columnspan=2, sticky='EW', padx=(10, 10), pady=(10, 5))

        self.crfLabel = tk.Label(self, text='Constant Rate Factor:', fg='green')
        self.crfLabel.grid(row=5, column=0, sticky='E', padx=(10, 5), pady=(5, 5))

        self.crfScale = tk.Scale(self, from_=0, to=51, orient=tk.HORIZONTAL, length=200, tickinterval=6, command=self.handleCrfChange)
        Hovertip(self.crfScale,'Level of compression aggression (affects data quality) \n\n0 : Lossless\n1-17: Visually Lossless\n23-51: Lossy', hover_delay=200)
        self.crfScale.grid(row=5, column=1, sticky='W', padx=(5, 10), pady=(5, 5))

        self.speedLabel = tk.Label(self, text='Efficiency:', fg='green')
        self.speedLabel.grid(row=6, column=0, sticky='E', padx=(10, 5), pady=(5, 5))

        self.speedScale = tk.Scale(self, from_=0, to=8, orient=tk.HORIZONTAL, length=200, command=self.handlePresetChange, showvalue=0, label=FFMPEG_SPEEDS['default'][0])
        Hovertip(self.speedScale,'Level of compression efficiency \n(affects compression speed) \n\n"Use the slowest preset that you have patience for"', hover_delay=200)
        self.speedScale.grid(row=6, column=1, sticky='W', padx=(5, 10), pady=(5, 5))

        self.performanceLabel = tk.Label(self, text='Performance Mode:', fg='red')
        self.performanceLabel.grid(row=7, column=0, sticky='E', padx=(10, 5), pady=(5, 5))

        self.performanceScale = tk.Scale(self, from_=0, to=2, orient=tk.HORIZONTAL, length=200, command=self.handlePerformanceModeChange, showvalue=0, label='background')
        Hovertip(self.performanceScale,'Level of resources used by the process \n(affects compression speed)', hover_delay=200)
        self.performanceScale.grid(row=7, column=1, sticky='W', padx=(5, 10), pady=(5, 5))

        # file settings
        self.hr = ttk.Separator(self, orient='horizontal')
        self.hr.grid(row=8, columnspan=2, sticky='EW', padx=(10, 10), pady=(10, 5))

        self.fileOverwriteLabel = tk.Label(self, text='Overwrite source:')
        self.fileOverwriteLabel.grid(row=9, column=0, sticky='E', padx=(10, 5), pady=(5, 5))

        self.fileOverwriteCheckbox = tk.Checkbutton(self, variable=tk.IntVar(name='overwrite'), command=lambda: self.handleCheckboxClick(self.fileOverwriteCheckbox, 'overwrite'))
        Hovertip(self.fileOverwriteCheckbox,'Replace original files upon completion? \n(ignored if output is not smaller than source)', hover_delay=200)
        self.fileOverwriteCheckbox.grid(row=9, column=1, sticky='W', padx=(5, 10), pady=(5, 5))

        # LOAD SETTINGS
        self.loadSettings()


    def onExit(self):
        """
        Close the settings window
        """

        self.saveSettings()
        
        # if (self.parent.isAlive):
        #     messagebox.showwarning("Warning", "A compression process is currently running. Please abort it for these settings to take effect.")

        self.parent.settingsWindow = None
        self.withdraw()


    def loadSettings(self):
        """
        Load settings from config.json into class variables
        """

        with open(CONFIG_PATH) as f:
            self.config = json.load(f)
        if (not self.config):
            self.config = {}

        # READ
        self.autorunCheckbox.select() if (self.config.get('autorun', False)) else self.autorunCheckbox.deselect()
        self.startupCheckbox.select() if (self.config.get('startup', False)) else self.startupCheckbox.deselect()
        self.setAutorunDirectory(self.config.get('autorunPath', ''))

        self.crfScale.set(self.config.get('constant_rate_factor', 0))
        self.speedScale.set(self.config.get('speed', 0))
        self.performanceScale.set(self.config.get('performanceMode', 0))

        self.fileOverwriteCheckbox.select() if (self.config.get('overwrite', False)) else self.fileOverwriteCheckbox.deselect()


    def saveSettings(self):
        """
        Save settings from class variables into config.json
        """
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(self.config, f, indent=4, sort_keys=True)

        try:
            # Open the registry key
            with wr.OpenKey(wr.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY, 0, wr.KEY_SET_VALUE) as registry_key:
                if (self.config.get('startup', False)):
                    # Set the registry value to the program path
                    wr.SetValueEx(registry_key, APPLICATION_NAME, 0, wr.REG_SZ, PROGRAM_PATH)
                else:
                    # Delete the registry value for the specified application
                    wr.DeleteValue(registry_key, APPLICATION_NAME)
        except FileNotFoundError:
            pass # already doesn't exist
        except Exception as e:
            print(f"Error: {e}")

    
    def setAutorunDirectory(self, directory):
        """
        Set the autorun directory
        """
        self.autorunDirEntry.config(state='normal')
        self.autorunDirEntry.delete(0, tk.END)
        self.autorunDirEntry.insert(tk.END, directory)
        self.autorunDirEntry.config(state='disabled')


    def handleCheckboxClick(self, checkbox, variable):
        """
        Handle checkbox click
        """
        self.config[variable] = int(checkbox.getvar(variable))

    
    def handlePresetChange(self, value):
        """
        Handle preset change
        """
        value= int(value)
        self.config['speed'] = value

        self.speedScale.config(label=FFMPEG_SPEEDS['default'][value])

        if (value <= 2):
            self.speedLabel['fg'] = 'green'
        elif (value == 3):
            self.speedLabel['fg'] = 'orange'
        else:
            self.speedLabel['fg'] = 'red'


    def handleCrfChange(self, value):
        """
        Handle CRF scale change
        """
        value = int(value)
        self.config['constant_rate_factor'] = value

        if (value == 0):
            self.crfLabel['fg'] = 'green'
        elif (value <= 18):
            self.crfLabel['fg'] = 'orange'
        else:
            self.crfLabel['fg'] = 'red'


    def handlePerformanceModeChange(self, value):
        """
        Handle performance mode change
        """
        value = int(value)
        self.config['performanceMode'] = value

        self.performanceScale.config(label=['background', 'standard', 'maximum'][value])

        if (value == 0):
            self.performanceLabel['fg'] = 'red'
        elif (value == 1):
            self.performanceLabel['fg'] = 'orange'
        else:
            self.performanceLabel['fg'] = 'green'

    
    def selectAutorunDirectory(self):
        """
        Handle autorun directory selection
        """
        dir = filedialog.askdirectory()
        if (dir):
            self.config['autorunPath'] = dir
            self.setAutorunDirectory(dir)


asyncio.run(App().exec())

# TODO
# - hardware acceleration https://docs.nvidia.com/video-technologies/video-codec-sdk/12.0/ffmpeg-with-nvidia-gpu/index.html

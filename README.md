
<p  align="center">
    <img width="546" height="212" src="https://github.com/Razzula/tortle-stomp/blob/main/img/window.gif">
</p>
<h1  align="center">tortle-stomp</h1>

Automated compression of video files

## Installation
### Prerequisites

Python 3
`pip install -r requirements.txt`

[ffmpeg](https://ffmpeg.org/) (and ffprobe)

###  Building
Use `build.bat`, or build manually with `pyinstaller`

## Running
### Settings
The program comes with some configurable settings, modifiable from the UI.
##### tortle-stomp
`autorun`: begin the compression process in the designated directory when the application starts
`startup`: launch the application on boot

`overwrite`: overwrite or duplicate the source file
`performance mode`:  limit number of cores/threads  used, and set `nice` priority

##### ffmpeg
`crf`: [Constant Rate Factor](https://trac.ffmpeg.org/wiki/Encode/H.265#ConstantRateFactorCRF) (or CQ for NVENC)
`preset`: [Preset](https://trac.ffmpeg.org/wiki/Encode/H.265#ConstantRateFactorCRF)

### Additional Settings
Additional control over the ffmpeg process can be exercised by manually modifying the `config.json` file:

`vcodec`: [Video Codec](https://ffmpeg.org/ffmpeg-codecs.html) (`h264` or `h265` ; default `h265`: `libx265`/`hevc_nvenc`)
`acodec`: [Audio Codec](https://ffmpeg.org/ffmpeg-codecs.html) (default `libmp3lame`)
`abitrate`: [Bitrate](https://trac.ffmpeg.org/wiki/Limiting%20the%20output%20bitrate) (default `320k`)

### Hardware Acceleration
The program supports hardware acceleration for encoding and decoding video files. The application will automatically use NVENC and make use of CUDA if the ffmpeg binary is compiled with the necessary libraries.

## License
### GNU GPLv3

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

See [LICENSE.md](https://github.com/Razzula/ible-app/blob/main/LICENSE.md) for details.

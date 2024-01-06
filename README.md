
# tortle-stomp
Automated compression of video files

## Installation
### Prerequisites

Python 3
`pip install -r requirements.txt`

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
`crf`: [Constant Rate Factor](https://trac.ffmpeg.org/wiki/Encode/H.265#ConstantRateFactorCRF)
`preset`: [Preset](https://trac.ffmpeg.org/wiki/Encode/H.265#ConstantRateFactorCRF)

### Additional Settings
Additional control over the ffmpeg process can be exercised by manually modifying the `config.json` file:

`vcodec`: [Video Codec](https://ffmpeg.org/ffmpeg-codecs.html) (default `libx265`)
`acodec`: [Audio Codec](https://ffmpeg.org/ffmpeg-codecs.html) (default `libmp3lame`)
`abitrate`: [Bitrate](https://trac.ffmpeg.org/wiki/Limiting%20the%20output%20bitrate) (default `320k`)

## License
### GNU GPLv3

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

See [LICENSE.md](https://github.com/Razzula/ible-app/blob/main/LICENSE.md) for details.

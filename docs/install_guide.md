# Install Guide

## Updating a packaged release

Do not extract a new release over an existing Marvel LCG Digital folder. Extract
each release into a new, empty folder so old application, data, and interface
files cannot be mixed with the new build.

Copy `campaign_settings.json` from the old build folder into the new build
folder, replacing or overwriting the destination file if prompted. This file
contains the saved setup choices for every campaign. Also copy any personal
saves, replays, or custom decks that you want to keep. You may also copy
`assets/cache` to reuse downloaded card artwork; updating the game does not
require discarding these images. Do not copy the previous
executable, `public`, `data`, or `launch.json` unless you
intentionally need to migrate a setting. If a build older than `1.0.0.1r` was
previously opened, clear the browser's site data for
`127.0.0.1:2345` once if the interface still appears out of date.

Packaged builds open a versioned main-menu URL after the local server starts.
The version in that URL changes with each application build, preventing an
older cached HTML document from replacing the current menu. Menu navigation
uses the same version when opening setup and utility pages.

## Running the development build on Windows

### 1. Install the prerequisites

Install [Python](https://www.python.org/downloads/) and
[Node.js](https://nodejs.org/en/download). Python 3.10 through Python 3.14 are
supported for running the source-code development build. The commands below use
Python 3.14 because the current development build has been verified with that
version.

This development environment is separate from the environment used to create
official releases. Reproducible release builds must use exactly Python 3.12.13
and the pinned release dependencies described in the [release guide](release_guide.md).

### 2. Download the source

Clone the repository and enter its root folder:

```powershell
git clone https://github.com/sdolle1775/marvel-lcg.git
cd marvel-lcg
```

Alternatively, download the repository ZIP from GitHub, extract it into a new
folder, and open PowerShell in that folder.

### 3. Create the Python environment

Run these commands from the repository root:

```powershell
py -3.14 -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
```

If Python 3.14 is not installed, replace `-3.14` with the version you installed.

### 4. Compile the TypeScript client

Install TypeScript and compile the browser client once:

```powershell
npm install --global typescript
cmd /c tsc -p public\js\tsconfig.json
```

Using `cmd /c` avoids PowerShell execution-policy errors that can prevent the
`tsc.ps1` wrapper from running. Contributors actively editing TypeScript can
instead run `public\js\watch.bat` and leave that terminal open.

### 5. Start the game

Run the game from the repository root so its relative data and asset paths
resolve correctly:

```powershell
& ".\.venv\Scripts\python.exe" ".\main.py"
```

Open <http://127.0.0.1:2345/scene> if the setup page does not open
automatically. Close any older running copy of the game first because port
`2345` must be available.

### 6. Card images

The repository includes the small sounds and interface textures required to run the game. Standard card artwork is downloaded on demand from the image servers configured in `launch.json` and stored in `assets/cache`.

If an image server is unavailable, existing cached artwork still works. Keep
your previous installation's `assets/cache` folder and copy it into the new
installation to reuse those downloads. The text-only cards are fallback
images, not missing card definitions. In v1.3.3, restart the game and refresh
the browser to retry images that failed earlier in the session. The updated
source build retries failed downloads when you refresh after a 30-second
cooldown, and skips temporarily unreachable servers while trying the next
configured provider.

For offline play, an optional image package can be placed in `assets/pics` or referenced through `image_folders` in `launch.json`.

## Updating the development build

The development build does not update automatically when changes are added to
GitHub. Close the game before updating, then follow the instructions that match
how you originally downloaded it.

### If you used `git clone`

Open PowerShell in your existing `marvel-lcg` folder and run:

```powershell
git pull origin master
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
cmd /c tsc -p public\js\tsconfig.json
& ".\.venv\Scripts\python.exe" ".\main.py"
```

The first command downloads the newest game files. The next two commands make
sure any updated Python requirements and browser files are ready, and the last
command starts the updated game. You normally do not need to clone the
repository again or recreate `.venv`.

If Git reports local changes, a merge conflict, or files that would be
overwritten, stop and ask for help rather than deleting or resetting files.

### If you used **Download ZIP** on GitHub

A downloaded ZIP cannot use `git pull`. Download the newest repository ZIP,
extract it into a new empty folder, and repeat steps 3 through 5 above. Do not
extract it over the old source folder. Copy personal saves, replays, custom
decks, and `campaign_settings.json` from the old folder if you want to keep
them.

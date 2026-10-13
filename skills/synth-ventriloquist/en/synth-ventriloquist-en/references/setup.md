# Setup

Everything runs on the machine where the agent works: LMMS renders without opening a window, and the Python toolkit in `scripts/` drives it. Nothing needs a GPU. Machines differ a great deal, so this page gives a way of deciding, with examples, and leaves the exact commands to what the machine offers.

## Contents

- Look first
- Whose machine is it
- Getting LMMS
- Getting ffmpeg
- Drum kit
- Python packages
- Settings
- Render mode: the user's choice
- Model downloads
- What was tested
- Troubleshooting
- Self-test

## Look first

```bash
python scripts/lmms_tool.py doctor
```

`doctor` changes nothing. It reports:

- `environment`: operating system, Python version, whether Python is an isolated environment, whether the process has administrator rights, whether this looks like a container, whether a display exists, and which package managers are on the PATH.
- `lmms`: the launcher that will be used, how it was found (settings, PATH, a known folder, Flatpak), its version, whether it runs in a sandbox, and every other LMMS that was found.
- `ffmpeg`, `python_packages`: what is present, and what each missing piece disables.
- `settings`: the values in effect.

Install only what the task needs. An instrumental song needs LMMS and four Python packages. When `doctor` already shows a working LMMS, use it: do not install a second one, and do not upgrade, downgrade or remove the user's.

## Whose machine is it

The same missing piece calls for different behaviour depending on where the agent runs. Read `environment` and decide:

| Situation | Signs | How to proceed |
|---|---|---|
| Disposable container or cloud sandbox | `looks_like_container` or `administrator` is true, no display, nothing of the user's on the disk | Install what is missing with the system package manager without stopping to ask. Report afterwards what was installed. Settings go in environment variables, since nothing persists |
| A person's desktop or laptop | A display, a normal user account, a home folder with their files | Say what is missing, how large it is and which way of installing you propose, then wait for the answer. Prefer ways that need no administrator rights and touch nothing outside the user's home folder. Never run a command with administrator rights yourself: give the user the command to run if they choose that way |
| Shared server or managed workstation | No administrator rights, policies unknown | User-level installs only (AppImage, a virtual environment). Ask before any download |

On any machine that is not disposable:

- Python packages go into an isolated environment (a virtual environment, or the project's own environment manager such as conda or uv). Do not install into the system Python.
- Do not edit shell start-up files, system paths or the user's LMMS configuration. The toolkit starts LMMS with its own temporary configuration file, so the user's LMMS settings, recent files and working folder are never read or changed.
- Renders write only into the output folder you name, and temporary folders are removed after each render.
- Remove nothing you did not create.

## Getting LMMS

The toolkit was written against LMMS 1.2.x (see What was tested). LMMS is packaged in many ways, and the best one is whichever fits the machine. Find out what is available instead of assuming:

- A distribution package. Search the package manager that `doctor` lists (`apt-cache policy lmms`, `dnf info lmms`, `pacman -Si lmms`, `zypper info lmms`, `apk search lmms`, `nix-env -qaP lmms`, and so on). This is the simplest way in a container. It usually brings the LADSPA effect plugins and factory samples. It needs administrator rights.
- An AppImage from the LMMS download page (https://lmms.io/download). One file, no administrator rights, nothing installed system-wide. Put it in a folder such as `~/Applications`, make it executable, and `doctor` finds it there. A good default on a person's Linux desktop.
- A Flatpak (`flatpak search lmms`), installable per user with `flatpak install --user`. `doctor` finds installed Flatpak apps whose id contains "lmms".
- A Snap (`snap find lmms`). It lands on the PATH.
- macOS: the disk image from the download page, or a package manager (`brew search lmms`). The app bundle in `/Applications` or `~/Applications` is found automatically.
- Windows: the installer from the download page, or a package manager (`winget search lmms`, `choco search lmms`, `scoop search lmms`). The usual install folders are searched.
- A build the user made themselves, anywhere: point the `lmms_command` setting at it.

Check the version the source offers before installing. When several sources exist, prefer in this order: an LMMS that is already installed, a user-level 1.2.x (AppImage or Flatpak), the system package.

LMMS found in an unusual place, or one that needs a wrapper, is set once:

```bash
python scripts/lmms_tool.py configure --set lmms_command=/path/to/lmms-1.2.2-linux-x86_64.AppImage
python scripts/lmms_tool.py configure --set 'lmms_command=["flatpak", "run", "--command=lmms", "{grants}", "<app id shown by flatpak list --app>"]'
```

A command written as a list may contain `{grants}`. For a Flatpak it is replaced with permissions for exactly the folders one render needs (the project folder, the output folder, a scratch folder), valid for that one run. Nothing is changed in the Flatpak's stored permissions.

## Getting ffmpeg

ffmpeg is needed only for ogg, mp3 and flac files. Without it `produce` still delivers the WAV and says so. Ways to get it, by the same logic as above: the system package manager, a static build in the user's home folder with the `ffmpeg` setting pointing at it, or the Python package `imageio-ffmpeg`, which brings an ffmpeg binary into the Python environment without administrator rights and is picked up automatically.

## Drum kit

The skill ships no audio. The first time a song with drums is saved (or the self-test runs), the toolkit makes the drum kit on this machine: it computes the named kicks and a noise loop, and records the drum-machine hits from the DrumSynth presets of the installed LMMS in one short render. This takes a few seconds, needs a working LMMS with its factory samples, downloads nothing, and writes only into the kit folder (`kit_dir`, by default a `kit` folder under the cache folder).

```bash
python scripts/lmms_tool.py kit            # what is there
python scripts/lmms_tool.py kit --build    # make it now
```

- On a person's computer the kit is made once and reused. In a disposable container it is made again in each new container, which costs a few seconds.
- Songs sound the same on every render on one machine. Between machines the noise-based hits differ slightly, so a song rendered elsewhere is not sample-identical to the same song rendered here. To carry exactly the same drums to another machine, copy the kit folder, or use a project pack, which holds the sounds a song uses.
- `kit --rebuild` records the hits anew and so changes how existing songs render. Do it only on purpose.

## Python packages

`doctor` lists each package under the name to install. Use the installer that belongs to the environment (pip, uv, conda, poetry).

| Group | Packages | Needed for |
|---|---|---|
| Core | numpy, scipy, soundfile, matplotlib | Measurements, mixing, checks, figures. Enough for instrumental songs |
| Vocals | onnxruntime, kokoro-onnx, pyworld, onnx | Kokoro voices singing |
| More voices | piper-tts | Piper voices |
| Lyric check | faster-whisper | Recognition scores for sung lines |
| Voicebanks | pyyaml | Singer voicebanks the user supplies |
| Optional | xmlschema, imageio-ffmpeg | DAWproject validation, ffmpeg without admin rights |

## Settings

Every setting is looked up in this order: an environment variable, a settings file, discovery on the machine. `python scripts/lmms_tool.py configure` prints all of them with their meaning and the files that are read.

| Setting | Environment variable | Meaning |
|---|---|---|
| `lmms_command` | `LMMS_BIN` | LMMS launcher: a path, or a command as a JSON list |
| `lmms_data_dir` | `LMMS_DATA_DIR` | Folder with the LMMS factory `samples/` and `presets/` |
| `ffmpeg` | `LMMSKIT_FFMPEG` | Path of the ffmpeg binary |
| `cache_dir` | `LMMSKIT_CACHE` | Where downloaded speech models and vocal caches are kept. Default: the user cache folder of the operating system |
| `kit_dir` | `LMMSKIT_KIT_DIR` | Where the drum kit made on this machine is kept. Default: `kit` under `cache_dir` |
| `scratch_dir` | `LMMSKIT_SCRATCH` | Where temporary render folders are made. Default: the system temp folder, or beside the project for a sandboxed LMMS |
| `pin_cpu` | `LMMSKIT_PIN_CPU` | Hold each LMMS process to one CPU core: `auto`, `on`, `off` |
| `stem_workers` | `LMMSKIT_STEM_WORKERS` | Parallel LMMS renders for stems. 0 means one per CPU core. Lower it on a machine the user is working on |
| `render_timeout_s` | `LMMSKIT_RENDER_TIMEOUT` | Longest a single render may take |
| `qt_platform` | `QT_QPA_PLATFORM` | Qt platform plugin for rendering, `offscreen` by default |
| `figure_fonts` | `LMMSKIT_FONTS` | Font families tried in order for the figures |

- In a container, set environment variables. Nothing needs to be written.
- On a desktop, `configure --set KEY=VALUE` stores a value in the user's settings file (under the operating system's configuration folder), and `configure --here --set ...` writes `lmmskit.json` in the current folder for one project. `configure --unset KEY` removes a value. `LMMSKIT_CONFIG` names an extra settings file.
- Outside the folders you name, the toolkit writes only the settings file (through `configure`), the drum kit and the model cache.

## Render mode: the user's choice

How LMMS uses the CPU trades exact repeatability against speed and against how usable the computer stays while rendering. This is the user's machine and time, so present the three modes with what each costs during planning and apply the answer. With nobody to ask, use the first.

| Mode | Settings | What the user gets | What it costs |
|---|---|---|---|
| Repeatable (default) | `pin_cpu=auto`, `stem_workers=0` | Every render of a song gives the same file, which `produce` proves by rendering twice. Stems render side by side on all cores | Each LMMS process is held to one core, so the three or four full-mix renders of `produce` are slower |
| Fast | `pin_cpu=off` | Full-mix renders finish sooner. Measured on two cores with a 3:41 song: 30 s against 40 s per render | Songs with timing-dependent sources (several Kicker tracks with noise, automated instrument knobs) can differ slightly from one render to the next, and `produce` then reports `not_repeatable`. The test song rendered identically both ways. The effect on the stem stage was not measured |
| Gentle | `stem_workers=1` or `2` | The computer stays responsive for other work while a song renders | The stem stage, the longest part of `produce`, takes longer in proportion |

- Holding LMMS to one core exists only on Linux. On macOS and Windows LMMS always runs free, so only the number of parallel renders is a choice there, and the repeat check of `produce` tells whether a song came out the same twice.
- Fast and Gentle can be combined.
- Apply the choice with environment variables for one session (`LMMSKIT_PIN_CPU=off`, `LMMSKIT_STEM_WORKERS=2`) or store it with `configure --set`. Name the mode used in the delivery note.

## Model downloads

Speech and recognition models are downloaded on first use into `cache_dir` and the Hugging Face cache:

- Kokoro speech model with timing output, pinned to a fixed revision: about 330 MB, plus under 1 MB per voice.
- A Piper voice: 60 to 115 MB each.
- Recognition model (`base.en`, or `base` for other languages): about 140 MB.

Tell the user before the first vocal render that these downloads will happen. If the download host is blocked, the error message names the file and the place to put it by hand. Singer voicebanks are never downloaded by the toolkit. The user supplies them (see `vocals.md`).

## What was tested

- Tested: Linux, Python 3.13, LMMS 1.2.2 from the Debian package, numpy 2.5, scipy 1.18, onnxruntime 1.30, kokoro-onnx 0.6, piper-tts 1.8, faster-whisper 1.2, pyworld 0.3.5. Discovery of an AppImage by file name and the Flatpak command path were exercised with stand-ins for those launchers.
- Not tested: a real AppImage, Flatpak or Snap of LMMS, macOS, Windows, and LMMS versions other than 1.2.2. The discovery code covers them, and the self-test below is what proves a given machine. Say so to the user when working on one of these.
- Holding LMMS to one CPU core exists only where the operating system offers it (Linux). Elsewhere LMMS runs unrestricted, renders can differ slightly between runs, and the repeat check of `produce` reports it.
- LMMS versions after 1.2 changed the project format and some instruments. `doctor` adds a note when the version is not 1.2.x. Run the self-test, and if it fails, offer the user a 1.2.x AppImage beside their own version.

## Troubleshooting

- LMMS refuses to run as administrator: the toolkit adds `--allowroot` itself when needed.
- An AppImage does not start (no FUSE, common in containers): run it once with `--appimage-extract` in a folder of your own and set `lmms_command` to `squashfs-root/AppRun` there.
- A sandboxed LMMS (Flatpak, Snap) renders nothing: it cannot see the folders. Keep the project and the output folder inside the user's home folder (not in a hidden top-level folder), and leave `scratch_dir` unset so scratch folders are made beside the project.
- LMMS fails with a Qt platform error: the build lacks the `offscreen` plugin. Try `configure --set qt_platform=minimal`, or on a machine with a display leave the variable to the system with `qt_platform=xcb` (Linux), `cocoa` (macOS) or `windows`.
- The kit cannot be built ("LMMS rendered no sound for ... DrumSynth presets"): this LMMS has no factory samples or lays them out differently. Check that `samples/drumsynth` exists in its data folder, use a complete build, or copy a kit folder from another machine and point `kit_dir` at it. With a Snap, which cannot see hidden folders, set `kit_dir` to a visible folder in the home folder.
- A render produces silence or a tiny file: look at `missing_samples` in the `inspect` output. Drum sounds live in `samples/kit/` beside the project. `Song.save()` puts them there, and a project moved without its `samples/` folder loses them.
- A LADSPA effect has no effect: that LMMS build came without the plugin. `fx.catalog()` lists what the toolkit expects. Distribution packages and the official builds include them.
- A render takes very long: check the song length and part count, and try `render --bars 1:16` first. LMMS renders about five times faster than real time per pass, and `produce` needs one short pass per part plus three or four full passes.
- The machine becomes sluggish while rendering: set `stem_workers` to 1 or 2.
- Figures show boxes instead of text: none of the `figure_fonts` is installed. Add a font family that exists on the machine to the setting.
- `pyworld` fails to import with a `pkg_resources` error: the toolkit works around it. If it still fails, install `setuptools` into the environment.

## Self-test

```bash
python scripts/lmms_tool.py selftest            # instrumental pipeline, under a minute
python scripts/lmms_tool.py selftest --vocal    # adds one sung line with the default speech voice (downloads models on first use)
```

The self-test makes the drum kit if it is missing, builds an eight-bar song in a temporary folder, renders it twice, and checks that the two renders are identical, that the lint and the mix checks run, and that MIDI, JSON and DAWproject exports are written and read back. It prints one line per check and ends with `self-test passed` or the list of failures. Run it after installing, on any launcher or platform listed as not tested, and whenever a render behaves strangely.

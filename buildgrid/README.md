# Build your engine's drivable grid on your computer

A custom engine you design on the Dyno page needs a **drivable grid** before
you can drive it. The app can build one in the browser, but that takes a
long time (1.5 to 2.5 hours on a laptop). This script builds **the same
file** on your computer, which is 1.5–1.9× faster than a browser tab on the
same machine. It can also use more cores. Then you load the file in the app.
The app itself doesn't change.

## 1. Export your engine from the app

Open the app, go to **Dyno**, choose **Custom**, set up your engine, and
click **Export**. It saves `<name>.json` (for example `my-engine.json`).

## 2. Get the repository (once)

`git clone https://github.com/jenilclaudeai/diesel-simulator.git`, or
download it as a zip from GitHub and unpack it. To match the live site's
physics, use the `main` branch and update it (`git pull`) before building.
The script checks this and tells you if your copy differs.

## 3. Run the script

It needs Python 3.10 or newer. It puts numpy into its own
`buildgrid/.venv`, so nothing else on your computer changes.

- macOS / Linux: `sh buildgrid/build.sh path/to/my-engine.json`
- Windows: `buildgrid\build.bat path\to\my-engine.json`

It prints its progress and an estimate of the time left. On an M2 MacBook
(6 workers) a full grid took 84 minutes (23 of cells, 61 of the weather
table); expect 1 to 1.5 hours on a laptop, less on a desktop that keeps its
speed under load. When it finishes, it prints
where the file is, by default `out/grids/<name>.grid.json`.

| option | what |
|---|---|
| `--no-weather` | cells only, about a quarter of the time. Driving at sea level is the same; in other places (Leh, desert…) Drive can't correct for the air and says so |
| `--workers N` | how many solver processes (default: up to 6). On a machine with more cores, try more |
| `--out PATH` | where to write the grid |
| `--offline` | skip checking your copy against the live site |

## 4. Load it in the app

Open **Drive** or **Enjoy**, click **Import grid**, and pick the file. You
can send the file to a phone, or to a friend, the same way.

## If something goes wrong

- *"vehicle must be one of …"*: the engine file has no vehicle. Export it
  again from the Dyno page (the export includes it).
- *"this copy's solver is not the live site's"*: your copy of the repository
  is older or newer than the site. The grid still works, with your copy's
  physics. Run `git pull` on `main` for the site's.
- *"could not compare … certificate verify failed"*: only the check failed,
  and the build carries on. The script installs `certifi` to avoid this.

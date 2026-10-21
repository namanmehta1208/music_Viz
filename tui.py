"""Launcher: pick the audio input and the visualization, then start it.

    uv run python tui.py

The visualizer runs as a separate process (its window needs a main thread of
its own), started with the choices made here. Its output shows in the log at
the bottom. The launcher finds the built audio_dsp module in build/ by itself,
so PYTHONPATH doesn't need to be set.

Keys: S start / restart, X stop, Q quit (also stops the visualizer).
"""

import asyncio
import os
import sys
from pathlib import Path

# Same as visualizer.py: on Linux, record what the speakers play. Must be set
# before sounddevice is imported.
os.environ.setdefault("PULSE_SOURCE", "@DEFAULT_MONITOR@")

import sounddevice as sd
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    RadioButton,
    RadioSet,
    RichLog,
    Static,
    Switch,
)

from audio_capture import LOOPBACK_NAMES, find_loopback_device
from visualizations import VISUALIZATIONS

ROOT = Path(__file__).parent


def input_devices():
    """All inputs: the automatic pick first, then other loopback-looking ones,
    then the rest (probably microphones)."""
    auto = find_loopback_device()["index"]
    devices = [info for info in sd.query_devices() if info["max_input_channels"] > 0]

    def group(info):
        if info["index"] == auto:
            return 0
        name = info["name"].lower()
        return 1 if any(keyword in name for keyword in LOOPBACK_NAMES) else 2

    return sorted(devices, key=lambda info: (group(info), info["index"])), auto


def visualizer_env(device_index):
    """Environment for the visualizer process: the chosen device, and
    PYTHONPATH pointing at the built audio_dsp module."""
    env = os.environ.copy()
    env["MUSIC_VIZ_DEVICE"] = str(device_index)
    env["PYTHONUNBUFFERED"] = "1"  # show its output as it happens
    for folder in (ROOT / "build" / "Release", ROOT / "build"):
        if any(folder.glob("audio_dsp*.pyd")) or any(folder.glob("audio_dsp*.so")):
            paths = [str(folder), env.get("PYTHONPATH", "")]
            env["PYTHONPATH"] = os.pathsep.join(p for p in paths if p)
            break
    return env


class Launcher(App):
    TITLE = "Music Visualizer"
    CSS = """
    #top { height: 1fr; }
    #devices { width: 3fr; border: round $primary; }
    #side { width: 2fr; border: round $primary; padding: 0 1; }
    #side RadioSet { width: 100%; margin-bottom: 1; }
    #description { color: $text-muted; margin-bottom: 1; }
    .row { height: auto; margin-bottom: 1; }
    .row Label { padding: 1 1 0 0; }
    #buttons Button { margin-right: 1; }
    #status { margin-top: 1; }
    #log { height: 10; border: round $secondary; }
    """
    BINDINGS = [
        ("s", "start", "Start / restart"),
        ("x", "stop", "Stop"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.devices, self.auto_device = input_devices()
        self.viz_keys = list(VISUALIZATIONS)
        self.proc = None  # the running visualizer process, if any

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top"):
            yield DataTable(id="devices", cursor_type="row", zebra_stripes=True)
            with Vertical(id="side"):
                with RadioSet(id="viz"):
                    for i, key in enumerate(self.viz_keys):
                        yield RadioButton(VISUALIZATIONS[key].name, value=i == 0)
                yield Static(id="description")
                with Horizontal(classes="row"):
                    yield Label("Fullscreen")
                    yield Switch(id="fullscreen")
                with Horizontal(id="buttons", classes="row"):
                    yield Button("Start", id="start", variant="success")
                    yield Button("Stop", id="stop", variant="error")
                yield Static(id="status")
        yield RichLog(id="log", wrap=True)
        yield Footer()

    def on_mount(self):
        self.query_one("#devices").border_title = "Audio input  (★ = automatic pick)"
        self.query_one("#side").border_title = "Visualization"
        self.query_one("#log").border_title = "Visualizer output"

        table = self.query_one(DataTable)
        table.add_columns("", "#", "Name", "Host API", "Rate")
        for info in self.devices:
            table.add_row(
                "★" if info["index"] == self.auto_device else "",
                str(info["index"]),
                info["name"],
                sd.query_hostapis(info["hostapi"])["name"],
                f"{int(info['default_samplerate'])} Hz",
            )
        table.focus()
        self.show_description(0)
        self.update_status()

    # ------------------------------------------------------------- choices

    def on_radio_set_changed(self, event: RadioSet.Changed):
        self.show_description(event.index)

    def show_description(self, index):
        self.query_one("#description", Static).update(
            VISUALIZATIONS[self.viz_keys[index]].description
        )

    def chosen_device(self):
        return self.devices[self.query_one(DataTable).cursor_row]

    def chosen_viz(self):
        index = self.query_one("#viz", RadioSet).pressed_index
        return self.viz_keys[max(index, 0)]

    def update_status(self):
        running = self.proc is not None and self.proc.returncode is None
        self.query_one("#start", Button).label = "Restart" if running else "Start"
        self.query_one("#status", Static).update(
            "[green]● running[/]" if running else "[dim]○ stopped[/]"
        )

    # ------------------------------------------------------------- process

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "start":
            self.run_worker(self.action_start())
        elif event.button.id == "stop":
            self.run_worker(self.action_stop())

    async def action_start(self):
        await self.action_stop()
        device = self.chosen_device()
        viz = self.chosen_viz()
        args = [sys.executable, str(ROOT / "visualizer.py"), "--viz", viz]
        if self.query_one("#fullscreen", Switch).value:
            args.append("--fullscreen")

        log = self.query_one(RichLog)
        log.write(Text(f"Starting {viz} on [{device['index']}] {device['name']}", style="bold"))
        self.proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=ROOT,
            env=visualizer_env(device["index"]),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self.update_status()
        self.run_worker(self.show_output(self.proc))

    async def show_output(self, proc):
        """Copy the visualizer's output into the log until it exits."""
        log = self.query_one(RichLog)
        async for line in proc.stdout:
            # Text(), not a string, so brackets in the output aren't read as markup.
            log.write(Text(line.decode(errors="replace").rstrip()))
        code = await proc.wait()
        if proc is self.proc:  # it ended by itself (Esc, closed, crashed)
            log.write(Text(f"Visualizer exited (code {code})", style="dim"))
        else:  # we stopped it (Windows reports that as code 1)
            log.write(Text("Visualizer stopped", style="dim"))
        self.update_status()

    async def action_stop(self):
        proc, self.proc = self.proc, None
        if proc is not None and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)
            except asyncio.TimeoutError:
                proc.kill()
        self.update_status()

    async def action_quit(self):
        await self.action_stop()
        self.exit()


if __name__ == "__main__":
    Launcher().run()

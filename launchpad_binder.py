#!/usr/bin/env python

import launchpad_py
import wx
import json
import os
import subprocess
import shlex
import time
import argparse

colors = {"black": 0}


class Util:
    def choose_color(self, lp):
        lp.ButtonFlush()
        color = 20
        ev = None
        colors = None
        starting_color = 0
        while ev == None:
            colors = self.draw_color_page(lp, starting_color)
            raw_event = lp.ButtonStateXY()
            time.sleep(0.2)
            if raw_event != []:
                ev = Event(raw_event)
                if ev.is_left() or ev.is_right():
                    if ev.is_left():
                        starting_color = 0
                    else:
                        starting_color = 64
                    ev = None

        color = colors[(ev.x, ev.y)]
        lp.LedAllOn(0)
        return color

    def draw_color_page(self, lp, starting_color=0):
        x_range = range(0, 8)
        y_range = range(1, 9)
        color = starting_color
        colors = {}
        for x in x_range:
            for y in y_range:
                colors[(x, y)] = color
                lp.LedCtrlXYByCode(x, y, color)
                color += 1
        return colors

    def get_input(self, prompt):
        frame = wx.Frame(None, -1, "launchpad_binder.py")
        frame.SetSize(0, 0, 200, 50)
        dlg = wx.TextEntryDialog(frame, prompt, prompt)
        dlg.SetValue("")
        if dlg.ShowModal() == wx.ID_OK:
            return dlg.GetValue()
        dlg.Destroy()
        return None


class Event:
    def __init__(self, raw_event):
        if raw_event == []:
            return
        self.x = raw_event[0]
        self.y = raw_event[1]
        self.action_code = raw_event[2]

    def print(self):
        print(f"{self.x}, {self.y}: {self.is_down()}")

    def is_left(self):
        return self.x == 2 and self.y == 0

    def is_right(self):
        return self.x == 3 and self.y == 0

    def is_down(self):
        return self.action_code == 127

    def is_released(self):
        return self.action_code == 0


class LaunchBinder:
    EXECUTE = "execute"
    RECORD = "record"

    def __init__(self, config_path, lp=None, wxApp=wx.App()):
        self.possibly_load_shared_lp(lp)
        self.data = None
        self.keys = {}
        self.util = Util()
        self.last_run = time.time()
        self.run_interval_min = 0.2
        self.executor = Executor(self)
        self.state = LaunchBinder.EXECUTE
        self.config_path = config_path
        self.quit = False
        self.level = 0

    def possibly_load_shared_lp(self, lp):
        if lp != None:
            self.lp = lp
            self.shared_lp = True
        else:
            self.lp = launchpad_py.LaunchpadMk2()
            self.shared_lp = False

    def set_recording(self):
        self.state = LaunchBinder.RECORD

    def is_recording(self):
        return self.state == LaunchBinder.RECORD

    def set_executing(self):
        self.state = LaunchBinder.EXECUTE

    def is_executing(self):
        return self.state == LaunchBinder.EXECUTE

    def new_binding(self, key):
        binding = self.util.get_input("Your down keybinding:")
        if binding != None:
            key.update_command(binding)

        binding = self.util.get_input("Your release keybinding:")
        if binding != None and binding != "":
            key.update_command(binding, key_action="up")

        color = self.util.choose_color(self.lp)
        if color != None:
            color = key.update_color(color)
        self.all_keys_color_changed()

    def all_keys_color_changed(self):
        for key in self.keys.values():
            key.color_changed = True

    def load_bindings(self):
        with open(self.config_path, "r") as read_file:
            self.data = json.load(read_file)
        for binding, value in self.data["bindings"].items():
            self.keys[binding] = Key(binding, value, self.executor)
        print(f"loaded {len(self.data['bindings'])} keys")

    def save_bindings(self, file_path=None):
        if file_path == None:
            file_path = self.config_path
        result = '{ "bindings": { '
        for key, value in self.keys.items():
            result += f'"{key}": {value.to_json()},'
        result = result.strip(",")
        result += "} }"
        with open(file_path, "w") as write_file:
            write_file.write(result)

    def show(self):
        printed = "keys:\n"
        for key in self.keys:
            printed += "\t\t" + str(self.keys[key])
        return printed

    def update(self):
        for key in self.keys.values():
            key.smart_execute()
            key.update(self.lp)
        return

    def process_input(self):
        raw_event = self.lp.ButtonStateXY()
        if raw_event != []:
            event = Event(raw_event)
            event.print()
            key = self.key_for_event(event)
            if key != None:
                if event.is_down():
                    key.on_down()
                else:
                    key.on_up()

    def key_for_event(self, event):
        lookup = f"{event.x}{event.y}"
        if lookup in self.keys:
            return self.keys[lookup]
        if self.is_recording():
            new_key = Key(
                lookup,
                {"down_command": "#new", "up_command": 'echo "new"', "color": "17"},
                self.executor,
            )
            self.keys[lookup] = new_key
            return new_key
        return None

    def override_key(self, key):
        self.keys[key.lookup()] = key

    def run(self):
        opened = self.lp.Open()
        if not opened:
            return False

        self.reset_start()
        while not self.quit:
            if self.should_execute():
                self.process_input()
                self.update()
        self.cleanup()

    def should_execute(self):
        remaining = (self.last_run + self.run_interval_min) - time.time()
        if remaining < 0:
            self.last_run = time.time()
            return True
        time.sleep(remaining)
        return False

    def reset_start(self):
        self.lp.LedAllOn(colors["black"])
        self.all_keys_color_changed()

    def cleanup(self):
        self.lp.LedAllOn(colors["black"])
        self.lp.ButtonFlush()
        if not self.shared_lp:
            self.lp.Close()


class Key:
    UP = 0
    DOWN = 1

    def __init__(self, binding, data, executor):
        self.data = data
        self.executor = executor
        self._x = int(binding[0])
        self._y = int(binding[1])
        self.state = Key.UP
        self.changed = False
        self.last_released = True
        self.color_changed = True

    def lookup(self):
        return f"{self._x}{self._y}"

    def to_json(self):
        return json.dumps(self.data)

    def __str__(self):
        return (
            f"{self._x},{self._y}:\t{self.data['down_command']}\t{self.data['color']}"
        )

    def on_down(self):
        self.state = Key.DOWN
        self.changed = True

    def on_up(self):
        self.state = Key.UP
        self.changed = True

    def smart_execute(self):
        if self.changed:
            self.changed = False
            if self.state == Key.UP:
                self.execute_up()
            if self.state == Key.DOWN:
                self.execute_down()

    def update(self, lp):
        if self.color_changed:
            lp.LedCtrlXYByCode(self.x(), self.y(), self.color())
            self.color_changed = False

    def x(self):
        return self._x

    def y(self):
        return self._y

    def update_command(self, command, key_action="down"):
        if key_action == "down":
            self.data["down_command"] = command
        elif key_action == "up":
            self.data["up_command"] = command

    def update_color(self, color):
        self.data["color"] = color
        self.color_changed = True

    def command(self):
        return self.data["down_command"]

    def down_command(self):
        return self.data["down_command"]

    def up_command(self):
        if "up_command" in self.data:
            return self.data["up_command"]
        return None

    def color(self):
        return int(self.data["color"])

    def execute_up(self):
        if self.up_command() != None and self.up_command() != "":
            ran = self.executor.execute(self.up_command(), self)
            return ran
        return False

    def execute_down(self):
        if self.down_command() != None and self.down_command() != "":
            ran = self.executor.execute(self.down_command(), self)
            return ran
        return False


class Commands:
    def __init__(self, binder):
        self.binder = binder

    def quit(self, command, key):
        print("quitting..")
        self.binder.quit = True

    def save(self, command, key):
        self.binder.save_bindings()

    def record(self, command, key):
        self.binder.set_recording()

    def load(self, command, key):
        print("load...", command)
        words = command.split(" ")
        if len(words) != 2:
            return None
        bindings_file = words[1]
        bindings_file = os.path.expanduser(bindings_file)
        binder = LaunchBinder(bindings_file, self.binder.lp)
        binder.level = self.binder.level + 1
        binder.load_bindings()
        release_to_quit_key = Key(
            key.lookup(),
            {"down_command": "", "up_command": key.up_command(), "color": "10"},
            binder.executor,
        )
        binder.override_key(release_to_quit_key)
        binder.run()
        self.binder.reset_start()
        print("sub binder finished...")


class Executor:
    def __init__(self, binder):
        self.binder = binder
        commands = Commands(binder)
        self.command_dict = {
            "quit": commands.quit,
            "save": commands.save,
            "record": commands.record,
            "load": commands.load,
        }

    def lookup_command(self, command):
        words = command.split(" ")
        if self.binder.is_recording():
            return None

        if len(words) == 0:
            return None

        command = words[0]
        if not command in self.command_dict:
            return None

        return self.command_dict[command]

    def execute(self, command, key):
        quit = self.binder.quit
        if command == None:
            return

        action = self.lookup_command(command)
        if action != None:
            action(command, key)
        else:
            if binder.is_recording():
                print("binding..")
                binder.new_binding(key)
                binder.set_executing()
            else:
                args = shlex.split(command)
                pid = subprocess.Popen(args).pid


parser = argparse.ArgumentParser(description="Start the binding service")
parser.add_argument(
    "--bindings-file",
    type=str,
    help="the location of the stored bindings file",
    default="bindings.json",
)
args = parser.parse_args()
try:
    binder = LaunchBinder(args.bindings_file)
    binder.load_bindings()
    binder.run()
except:
    binder.save_bindings("temp.json")
    print("exception occurred, attempted to store bindings to temp.json")
    raise


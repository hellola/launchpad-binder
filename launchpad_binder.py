import launchpad_py
import wx
import json
import os
import time
import argparse

colors = {
  "black": 0
}

class Util:
  def choose_color(self, lp):
    x_range = range(0,9)
    y_range = range(0,9)
    colors = {}
    color = 0
    for x in x_range:
      for y in y_range:
        colors[(x,y)] = color
        lp.LedCtrlXYByCode(x,y,color)
        color += 1
    lp.ButtonFlush()
    time.sleep(5)
    raw_event = lp.ButtonStateXY()
    color = 20
    if raw_event != []:
      ev = Event(raw_event)
      color = colors[(ev.x,ev.y)]
    lp.LedAllOn(0)
    return color

  def get_input(self, prompt):
    app = wx.App()
    frame = wx.Frame(None, -1, "launchpad_binder.py")
    frame.SetDimensions(0,0,200,50)
    dlg = wx.TextEntryDialog(frame, prompt, prompt)
    dlg.SetValue("")
    if dlg.ShowModal() == wx.ID_OK:
      return dlg.GetValue()
    dlg.Destroy()
    return None

quit = False
class Event:
  def __init__(self, raw_event):
    if raw_event == []:
      return
    self.x = raw_event[0]
    self.y = raw_event[1]
    self.action_code = raw_event[2]
  
  def print(self):
    print(f"{self.x}, {self.y}: {self.is_down()}")

  def is_down(self):
    return self.action_code == 127

  def is_released(self):
    return self.action_code == 0

class LaunchBinder:
  EXECUTE = "execute"
  RECORD = "record"
  def __init__(self, config_path):
    self.lp = launchpad_py.LaunchpadMk2()
    self.data = None
    self.keys = {}
    self.util = Util()
    self.executor = Executor(self)
    self.state = LaunchBinder.EXECUTE
    self.config_path = config_path
  
  def set_recording(self):
    self.state = LaunchBinder.RECORD

  def is_recording(self):
    return self.state == LaunchBinder.RECORD
  
  def set_executing(self):
    self.state = LaunchBinder.EXECUTE

  def is_executing(self):
    return self.state == LaunchBinder.EXECUTE

  def save_bindings(self):
    result = '{ "bindings": { '
    for key, value in self.keys.items():
      result += f'"{key}": {value.to_json()},'
    result = result.strip(',')
    result += "} }"

    with open(self.config_path, "w") as write_file:
      write_file.write(result)

  def new_binding(self, key):
    binding = self.util.get_input("Your keybinding:")
    if binding != None:
      key.update_command(binding)
    color = self.util.choose_color(self.lp)
    if color != None:
      color = key.update_color(color)
    #TODO: have to save this..

  def load(self):
    with open(self.config_path, "r") as read_file:
      self.data = json.load(read_file)
    for binding, value in self.data['bindings'].items():
      self.keys[binding] = Key(binding, value, self.executor)
  
  def show(self):
    printed = "keys:\n"
    for key in self.keys:
      printed += "\t\t" + str(self.keys[key])
    return printed

  def key_for_event(self, event):
    lookup = f"{event.x}{event.y}"
    if lookup in self.keys:
      return self.keys[lookup]
    if self.is_recording():
      new_key = Key(lookup, { "command": "", "color": "17"}, self.executor)
      self.keys[lookup] = new_key
      return new_key
    return None

  def update(self):
    for key in self.keys.values():
      key.smart_execute()
      self.lp.LedCtrlXYByCode(key.x(), key.y(), key.color())
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

  def run(self):
    opened = self.lp.Open()
    if not opened:
      return False

    self.reset_start()
    global quit
    while not quit:
      self.process_input()
      self.update()
    self.cleanup()

  def cleanup(self):
    self.lp.LedAllOn(colors["black"])
    self.lp.ButtonFlush()
    self.lp.Close()

  def reset_start(self):
    self.lp.LedAllOn(colors["black"])

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
  
  def to_json(self):
    return json.dumps(self.data)

  def __str__(self):
    return f"{self._x},{self._y}:\t{self.data['command']}\t{self.data['color']}"
  
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
        self.last_released = True
      if self.state == Key.DOWN and self.last_released == True:
        self.execute()
        self.last_released == False

  def x(self):
    return self._x

  def y(self):
    return self._y

  def update_command(self, command):
    self.data['command'] = command

  def update_color(self, color):
    self.data['color'] = color

  def command(self):
    return self.data['command']
  
  def color(self):
    return int(self.data['color'])

  def execute(self):
    ran = self.executor.execute(self)
    return ran


class Executor:
  def __init__(self, binder):
    self.binder = binder

  def execute(self, key):
    command = key.command()
    global quit
    if command == "quit":
      print("quitting..")
      quit = True
    elif command == "save":
      binder.save_bindings()
    elif command == "record":
      print("recording..")
      binder.set_recording()
    else:
      if binder.is_recording():
        print("binding..")
        binder.new_binding(key)
        binder.set_executing()
      else:
        os.system(command)

parser = argparse.ArgumentParser(description='Start the binding service')
parser.add_argument('--bindings-file', type=str, help='the location of the stored bindings file', default="bindings.json")
args = parser.parse_args()

binder = LaunchBinder(args.bindings_file)
binder.load()
binder.run()
    
# launchpad-binder
Simple system call binding for [Novation Launchpad][1]

Uses [FMMT666's launchpad_py][2] to interface with the launchpad. At the moment it's hardcoded to use the Mk2.

## Installation 
At this stage just git clone the repo and run the python file
You will probably need to `pip install pygame launchpad_py`

## Running
```sh
./launchpad_binder.py --bindings-file <file>
```

## Overview
I wanted to keep it super simple - you can keybind up and down events.
There is a very limited set of built in commands, everything that doesn't match these will be ran as a system call.

You can start with a basic confguration of: 
```json
{ 
  "bindings": { 
    "88": {"down_command": "quit", "color": "10"},
    "87": {"down_command": "record", "color": "20"},
    "85": {"down_command": "save", "color": "30"}
  }
}
```

## Basic Built-in Commands
| command     | :meaning                                                        |
| ----------- | -------------------------------------------------------------- |
| record      | records a new keybinding                                       |
| save        | saves the current bindings into the file provided              |
| quit        | closes the binder                                              |
| load <file> | loads the json file provided and starts a new binding instance |

#### `> record`
Pressing record puts the binder in record mode, the next key pushed is the key that it will bind. 
You will then be prompted for:
- Key Down action (can be left empty)
- Key Up action (can be left empty)
- A set of colors will show on the launchpad and you choose a color by pushing the corresponding button. (You can page right or left with the left or right arrow at the top)

#### `> save`
saving will write all of the currently loaded bindings into the file that was provided when the launchpad-binder was executed

#### `> load`
Load can be configured in two ways, when a `up_command` is provided it will override the key in the loaded file to perform the provided `up_command`. This is great for using a key as a modifier, for example, press key x, it loads the alternate bindings and when key x is released it will quit the binder, reverting to the previously loaded bindings file. Alternatively with no `up_command` provided, the binding will stay in place until a key with a `quit` command is used.



### Alternatives:
[LPHK][3] is different in that it provides a GUI, along with a custom scripting language

[1]: https://global.novationmusic.com/launch/launchpad
[2]: https://github.com/FMMT666/launchpad.py
[3]: https://github.com/nimaid/LPHK
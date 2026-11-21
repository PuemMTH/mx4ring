#!/usr/bin/python3
"""Launch an interactive assistant in the Nautilus folder captured by the ring."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from gi.repository import Gio, GLib


def resolve_folder(windows, window, title):
    if window is None:  # Old extension, before the next login.
        locations = [uri for uris in windows.values() for uri in uris]
        if len(windows) != 1 or len(locations) != 1:
            raise ValueError('Log out and back in to enable active-folder detection, or keep just one Files tab open.')
    else:
        if not window.startswith('/org/gnome/Nautilus/window/') or window not in windows:
            raise ValueError('Open the action ring while a Files folder is focused.')
        locations = windows[window]
    locations = list(dict.fromkeys(locations))
    if len(locations) > 1:
        matches = []
        for uri in locations:
            f = Gio.File.new_for_uri(uri)
            names = {f.get_basename()}
            try:
                names.add(f.query_info('standard::display-name', Gio.FileQueryInfoFlags.NONE, None).get_display_name())
            except GLib.Error:
                pass
            if f.get_path() == str(Path.home()):
                names.add('Home')
            if title in names:
                matches.append(uri)
        locations = matches
    if len(locations) != 1:
        raise ValueError('Cannot uniquely identify this tab. Move it to its own Files window and try again.')
    path = Gio.File.new_for_uri(locations[0]).get_path()
    if not path or not Path(path).is_dir():
        raise ValueError('Choose a local folder in Files (not Recent, Search, Trash, or a remote location).')
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tool', choices=['claude', 'codex', 'terminal', 'code', 'copy-path'])
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        result = bus.call_sync('org.freedesktop.FileManager1', '/org/freedesktop/FileManager1',
            'org.freedesktop.DBus.Properties', 'Get',
            GLib.Variant('(ss)', ('org.freedesktop.FileManager1', 'OpenWindowsWithLocations')),
            None, Gio.DBusCallFlags.NONE, 3000, None)
        windows = result.unpack()[0]
        folder = resolve_folder(windows, os.environ.get('MX4_NAUTILUS_WINDOW'),
                                os.environ.get('MX4_NAUTILUS_TITLE', ''))
        if args.tool == 'copy-path':
            command = ['/usr/bin/xclip', '-selection', 'clipboard']
        elif args.tool == 'code':
            command = ['/snap/bin/code', '--new-window', folder]
        else:
            command = ['/usr/bin/ptyxis', '--new-window', '--working-directory', folder,
                       '--', '/usr/bin/zsh']
            # Load mise, aliases, and the user's CLI wrappers.
            command += (['-i'] if args.tool == 'terminal' else
                        ['-ic', args.tool + '; exec /usr/bin/zsh -i'])
        if args.dry_run:
            print(json.dumps({'folder': folder, 'command': command}))
        elif args.tool == 'copy-path':
            subprocess.run(command, input=folder, text=True, check=True)
            subprocess.run(['notify-send', 'Path copied', folder], check=False)
        else:
            subprocess.run(command, check=True)
    except (ValueError, OSError, GLib.Error, subprocess.CalledProcessError) as exc:
        subprocess.run(['notify-send', 'Action Ring', str(exc)], check=False)
        raise SystemExit(str(exc))


if __name__ == '__main__':
    main()

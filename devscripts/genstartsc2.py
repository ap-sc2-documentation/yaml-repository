"""
Script for generating an sc2-only world, starting a local server, and opening a client to connect to it.
Place this script in the Archipelago root, and configure your Players/ folder as normal.

This script assumes only one yaml is present and that it holds a single sc2 world
"""

from typing import *
import glob
import os
import shutil
import subprocess
import sys
import time

PLAYERS_FOLDER = './Players'
OUTPUT_FOLDER = './output'

PYTHON = 'python'
GENERATE = 'Generate.py'
SERVER = 'MultiServer.py'
CLIENT = 'Starcraft2Client.py'
PORT = 38281


class Error:
    def __init__(self, *msg: str) -> None:
        self.msg = msg

    def printmsg(self) -> None:
        for entry in self.msg[:-1]:
            print(entry)
            print()
        if len(self.msg):
            print(f"Error: {self.msg[-1]}")


def clean(verbose = False) -> None:
    shutil.rmtree('_worlds/__pycache__', ignore_errors=True)
    worlds = glob.glob('worlds/*')
    print("Removing all unnecessary worlds for faster run times")
    for world in worlds:
        if os.path.basename(world) in ('_bizhawk', '_sc2common', 'sc2', 'alttp', 'generic'):
            continue
        if os.path.splitext(world)[1] == '.py':
            continue
        if verbose:
            print(f'Removing {world}')
        shutil.move(world, world.replace('worlds', '_worlds'))


def restore(verbose = False) -> None:
    worlds = glob.glob('_worlds/*')
    print("Restoring all worlds")
    for world in worlds:
        if verbose:
            print(f'Restoring {world}')
        shutil.move(world, world.replace('_worlds', 'worlds'))


def get_player_name() -> str|Error:
    player_yamls = glob.glob(f'{PLAYERS_FOLDER}/*.yaml')
    if len(player_yamls) == 0:
        return Error("No player yamls specified")
    if len(player_yamls) > 1:
        return Error("Too many yamls supplied; only one supported")
    yaml = player_yamls[0]
    with open(yaml, 'r') as fp:
        lines = fp.readlines()
    if lines and lines[0].startswith('ï»¿'):
        lines[0] = lines[0][len('ï»¿'):]
    for line in lines:
        line = line.strip()
        if line.lower().startswith('name'):
            return line.split(':', 1)[-1].strip()
    return Error(f"Could not find player name in yaml {yaml}")
    

def generate() -> str|Error:
    print("Generating")
    RESULT_LINE_PREFIX = 'Creating final archive at '
    # Note: Supplying an input is necessary as otherwise Generate.py hangs on failure
    # because of the 'press enter to continue'
    proc = subprocess.run([PYTHON, GENERATE], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, input='\n')
    if proc.returncode != 0:
        return Error(f"{proc.stderr}\n\nError: Generation ended in failure!")
    lines = proc.stdout.split('\n')
    for line in lines[::-1]:
        if line.startswith(RESULT_LINE_PREFIX):
            filename = line[len(RESULT_LINE_PREFIX):].strip()
            print(f"Generated world {filename}")
            return filename
    return Error(proc.stdout, "Could not find Generation output location.")


def is_server_running() -> bool:
    result = subprocess.call(
        ['powershell', '-Command', f'Get-NetTCPConnection -LocalPort {PORT} -RemotePort 0'],
        stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL
    )
    return result == 0


def start_server(zip_location: str) -> None|Error:
    print("Starting server")
    if is_server_running():
        return Error("An existing server is already running; close it first")
    cmd = ['start', 'cmd', '/k', SERVER, zip_location]
    subprocess.call(cmd, shell=True)


def wait_for_server_to_listen(poll_period_seconds: float = 0.1, timeout_seconds: float = 10.0) -> None|Error:
    time_start = time.perf_counter()
    while True:
        if is_server_running():
            return
        time.sleep(poll_period_seconds)
        if time.perf_counter() - time_start > timeout_seconds:
            return Error("Timed out waiting for server to listen")


def start_client(name: str) -> None|Error:
    print("Starting client")
    result = subprocess.call([PYTHON, CLIENT, '--connect', 'localhost', '--name', name])
    if result != 0:
        return Error(f"Client exited with exit code {result}")


class Defer:
    def __init__(self, func: Callable, args: tuple = ()) -> None:
        self.func = func
        self.args = args

    def __enter__(self) -> Self:
        return self
    
    def __exit__(self, *args, **kwargs) -> None:
        self.func(*self.args)


def main() -> None:
    name = get_player_name()
    if isinstance(name, Error):
        name.printmsg()
        sys.exit(1)

    clean()
    with Defer(restore):
        world_file = generate()
        if isinstance(world_file, Error):
            world_file.printmsg()
            sys.exit(1)
        server_okay = start_server(world_file)
        if isinstance(server_okay, Error):
            server_okay.printmsg()
            sys.exit(1)
        wait_okay = wait_for_server_to_listen()
        if isinstance(wait_okay, Error):
            wait_okay.printmsg()
            sys.exit(1)
        client = start_client(name)
        if isinstance(client, Error):
            client.printmsg()
            sys.exit(1)


if __name__ == '__main__':
    main()

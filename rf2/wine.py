from pathlib import Path
from sys import platform
from os.path import exists
from json import loads
from subprocess import Popen as Popen_Native
import logging

logger = logging.getLogger(__name__)

def read_webserver_config() -> dict:
    server_config_path = str(Path(__file__).absolute()).replace(
        "rf2/wine.py", "server.json" if platform != "linux" else "server_linux.json"
    )
    if not exists(server_config_path):
        raise Exception("Server config was not found")
    config = None
    with open(server_config_path, "r") as file:
        config = loads(file.read())
    return config

def Popen(args, bufsize=- 1, executable=None, stdin=None, stdout=None, stderr=None, preexec_fn=None, close_fds=True, shell=False, cwd=None, env=None, universal_newlines=None, startupinfo=None, creationflags=0, restore_signals=True, start_new_session=False, pass_fds=(), *, group=None, extra_groups=None, user=None, umask=- 1, encoding=None, errors=None, text=None, pipesize=- 1):

  config = read_webserver_config()
  wine_root = config["wine_root_path"]
  root = config["root_path"]
  layer = config["abstractionlayer"] # in case of somebody needs proton vs wine

  # server start call
  final_call = args
  if "Dedicated.exe +path=" in args:
    final_call = f"{layer} \"{wine_root}server\\Bin64\\rFactor 2 Dedicated.exe\" +path=\"{wine_root}server\" +profile=player +oneclick"

  if "rf2WeatherClient.exe" in args:
    final_call = f"{wine_root}weatherclient\\rf2WeatherClient.exe"


  final_call = "{layer} " + final_call.replace(root, wine_root)
  logger.info(f"Running on {layer}: {final_call}")

  Popen_Native(args, stdin, stdout, stderr, shell, cwd, creationflags)


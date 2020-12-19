from requests import get
from zipfile import ZipFile
from rf2.steam import run_steamcmd
from os.path import join
from pywinauto import Application

STEAMCMD_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"


def install_server(server_config: dict) -> bool:
    root_path = server_config["server"]["root_path"]
    steamcmd_path = join(root_path, "steamcmd.zip")
    steamcmd_folder_path = join(root_path, "steamcmd")
    r = get(STEAMCMD_URL)

    with open(steamcmd_path, 'wb') as f:
        f.write(r.content)

    zf = ZipFile(steamcmd_path, 'r')
    zf.extractall(steamcmd_folder_path)
    zf.close()
    run_steamcmd(server_config, "install")
    # start the server
    server_root_path = join(root_path, "server")

    server_path = join(server_root_path, "Bin64", "rFactor2 Dedicated.exe") + \
        f" +path=\"{server_root_path}\""

    app = Application().start(server_path)

    start_Window = app.window(best_match=root_path)
    start_Window.wait('visible', timeout=100)
    app.kill()
    return True

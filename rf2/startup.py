from os.path import join, exists
from os import remove
from time import sleep

from pywinauto import Application, WindowSpecification
from rf2.util import (
    set_slider_value,
    set_updown_value,
    select_from_list,
    set_window_elements_value,
    get_server_port,
    get_max_players,
)
from rf2.interaction import chat, do_action, Action
from requests import get
from json import loads, load, dumps
import logging
from math import floor, ceil
from collections import OrderedDict


def oneclick_start_server(server_config: dict) -> bool:
    root_path = server_config["server"]["root_path"]
    server_root_path = join(server_config["server"]["root_path"], "server")
    mod = server_config["mod"]["mod"]
    event = server_config["mod"]
    server_binary_path = join(server_root_path, "Bin64", "rFactor2 Dedicated.exe")
    server_binary_commandline = (
        server_binary_path
        + f' +path="{server_root_path}"'
        + f"  +profile=player  +oneclick"
    )

    # make sure the Dedicated<modname>.ini has the correct content
    mod_ini_path = join(
        server_root_path, "UserData", "player", "Dedicated" + mod["name"] + ".ini"
    )

    max_clients_overwrite = get_max_players(server_config)

    if exists(mod_ini_path):
        remove(mod_ini_path)
    with open(mod_ini_path, "w") as file:
        file.write("[SETTINGS]\n")
        file.write("MaxClients=" + str(max_clients_overwrite) + "\n")
        file.write("[TRACKS]\n")

    # inject weather, if needed
    if event["real_weather"] and event["real_weather_key"]:
        logging.info("Trying to poll real weather")
        lon = 0
        lat = 0
        folder = ""
        wet_name = ""
        key = event["real_weather_key"]
        temp_offset = event["temp_offset"]
        geo_json_path = join(root_path, "reciever", "geo.json")

        with open(geo_json_path, "r") as file:
            geo_data = loads(file.read())
            lon = float(geo_data["Longitude"])
            lat = float(geo_data["Latitude"])
            folder = geo_data["SettingsFolder"]
            wet_name = geo_data["WET"]

        weather_file_path = join(
            root_path,
            "server",
            "UserData",
            "player",
            "Settings",
            folder,
            wet_name.replace(".WET", "s.WET").replace(".wet", "s.wet"),
        )
        player_json_path = join(
            root_path, "server", "UserData", "player", "player.JSON"
        )
        weather_inject(weather_file_path, lon, lat, key, temp_offset, player_json_path)

    rf2_server = Application().start(server_binary_commandline)
    return True


def weather_inject(weather_file, lon, lat, key, temp_offset, player_json_path):
    lat = 63.096
    lon = 21.61577
    forecast = loads(
        get(
            "https://api.openweathermap.org/data/2.5/onecall?lat={}&lon={}&appid={}&exclude=minutely,daily,alerts,current&units=metric".format(
                lat, lon, key
            )
        ).text
    )
    weather_blocks = []
    hourly = forecast["hourly"]
    # based on https://forum.studio-397.com/index.php?threads/wet-file-pease-isi-help.41666/

    for hour in hourly:
        block = {}
        # clouds: API gives percentage, will be clustered in 5 intervals
        api_clouds = float(hour["clouds"])
        block_clouds = 0
        rain_density = 0
        if api_clouds == 0 or api_clouds < 20:
            block_clouds = 0
            rain_density = 1
        if api_clouds >= 20 and api_clouds < 30:
            block_clouds = 1
            rain_density = 2
        if api_clouds >= 30 and api_clouds < 50:
            block_clouds = 2
            rain_density = 3
        if api_clouds >= 50 and api_clouds < 70:
            block_clouds = 3
            rain_density = 3
        if api_clouds >= 70:
            block_clouds = 4
            rain_density = 3

        time = hour["dt"]
        block["Sky"] = block_clouds
        block["Humidity"] = hour["humidity"]
        block["Temperature"] = floor(hour["temp"]) + floor(float(temp_offset))
        # wind
        api_wind = hour["wind_speed"]
        block["WindSpeed"] = floor(api_wind * 3.6)
        api_wind_direction = float(hour["wind_deg"])
        # direction
        # North: 0
        # NorthEast: 1
        # NorthWest: 7
        # South: 4
        # SouthEast: 3
        # SouthWest:  5
        # East: 2
        # West: 6
        block_wind_direction = 0
        if api_wind_direction > 45 and api_wind_direction < 90:
            block_wind_direction = 1
        if api_wind_direction > 90 and api_wind_direction < 135:
            block_wind_direction = 2
        if api_wind_direction > 135 and api_wind_direction < 180:
            block_wind_direction = 3
        if api_wind_direction > 180 and api_wind_direction < 225:
            block_wind_direction = 4
        if api_wind_direction > 225 and api_wind_direction < 270:
            block_wind_direction = 5
        if api_wind_direction > 270 and api_wind_direction < 315:
            block_wind_direction = 6
        if api_wind_direction > 315 and api_wind_direction < 360:
            block_wind_direction = 7
        block["WindDirection"] = block_wind_direction

        # Rain
        probability_rain = hour["pop"]
        amount_rain = 0
        if "rain" in hour:
            api_rain = hour["rain"]
            amount_rain = float(hour["rain"]["1h"])

        if "snow" in hour:
            amount_rain = float(hour["snow"]["1h"]) + amount_rain
            logging.warning(
                "The location has snow forecast for {}. We will use the sum of snow and rain to continue. Consider setting a temperature offset in the server settings.".format(
                    time
                )
            )

        amount_rain = amount_rain
        # the API will return rain as a volume for last hour in mm
        no_rain = 0
        max_rain = 50
        percentage_rain = 0
        block["RainChange"] = 0
        # https://en.wikipedia.org/wiki/Rain
        if amount_rain > max_rain:
            amount_rain = 50

        if amount_rain > 0:
            percentage_rain = ceil(100 / (max_rain / amount_rain))
            logging.warning(
                "We will see rain for {}. Amount is {}".format(time, percentage_rain)
            )

        block["RainChange"] = percentage_rain
        if percentage_rain > 0:
            # in the moment the rain is existing, we switch from the dry clouds to the variant with rain
            block["Sky"] = block["Sky"] + 4
            # storm mode of the game is not supporteda
        block["StartTime"] = hour["dt"]
        block["RainDensity"] = rain_density if percentage_rain > 0 else 0
        weather_blocks.append(block)

    # we add "intermediate" blocks in case rain will occur
    final_weather_blocks = []
    time_offset = forecast["timezone_offset"]
    for index, block in enumerate(weather_blocks):

        # hours after midnight
        start_time = floor((block["StartTime"] + time_offset) / 3600) % 24

        start_time_minutes = start_time * 60
        block["StartTime"] = start_time_minutes
        block["Duration"] = 60
        if index != 0:
            prev_block = weather_blocks[index - 1]
            prev_rain = prev_block["RainChange"]
            now_rain = block["RainChange"]

            # rain difference now and then
            # Prev 50, now 25 ---> -25
            # Prev 25, now 50 ---> 50
            rain_difference = now_rain - prev_rain

        final_weather_blocks.append(block)

    result_data = OrderedDict()
    result_data["Practice Info"] = final_weather_blocks
    result_data["Qualifying Info"] = final_weather_blocks
    result_data["Race Info"] = final_weather_blocks
    # search for the first start of a weather block
    file_contents = []
    with open(weather_file, "r") as weather_file_handle:
        file_contents = weather_file_handle.readlines()
        final_content = []
        for line in file_contents:
            if "RealRoad" in line or "abstractnodes" in line or "Weather" in line:
                final_content.append(line)
        final_content.append("\n")
        for key, weather in result_data.items():
            final_content.append("[{}]\n".format(key))
            for block in weather_blocks:
                for property in [
                    "StartTime",
                    "Duration",
                    "Sky",
                    "RainChange",
                    "RainDensity",
                    "Temperature",
                    "Humidity",
                    "WindSpeed",
                    "WindDirection",
                ]:
                    final_content.append("{}=({})\n".format(property, block[property]))

    # write new weather file
    with open(weather_file, "w") as weather_file_handle:
        weather_file_handle.writelines(final_content)

    # make sure the weather is scripted
    parsed = load(open(player_json_path, "r"))
    overwrite_options = {"Race Conditions": {"MULTI Weather": 5, "GPRIX Weather": 5}}
    for option, options in overwrite_options.items():
        for option_key, option_value in options.items():
            parsed[option][option_key] = option_value

    with open(player_json_path, "w") as overwrite_file_handle:
        overwrite_file_handle.write(dumps(parsed, indent=4, separators=(",", ": ")))

    return True


def stop_server(server_config: dict) -> bool:
    """
    Stops the server

    Args:
        server_config: The global configuration for this instance

    Returns:
        The success of the operation
    """
    chat(server_config, "Server is shutting down NOW")

    do_action(server_config, Action.RESTARTWEEKEND)
    root_path = join(server_config["server"]["root_path"], "server")
    binary_path = join(root_path, "Bin64", "rFactor2 Dedicated.exe")
    app = Application(backend="uia")
    app.connect(path=binary_path)
    app.kill()
    return True


def select_mod_and_admin_password(
    window: WindowSpecification, admin_password: str, mod_name: str, mod_version: str
):
    """
    Select the mod and inserts the admin password

    Args:
        window: WindowSpecification
        admin_password: The admin password string
        mod_name: The mod name string
        mod_version: The mod version: Important: WITHOUT a "v" prefix!
    """
    mod_Box = window.window(
        best_match="Select which game database to use for this server:ComboBox"
    )
    mods = mod_Box.item_texts()
    mod_Box.select(mods.index(f"{mod_name} v{mod_version}"))

    window.window(best_match="Edit").set_text(admin_password)


def select_grip(
    start_window: WindowSpecification,
    grips: dict,
    tracks: dict,
    server_root_path: str,
    rf2_server: Application,
):
    """
    Select the mod and inserts the admin password

    Args:
        start_window: WindowSpecification
        grips: A dictionary containing the session keyed grip infos
        tracks: The workshop_id keyed track infos
        server_root_path: The root path of the server
        rf2_server: The Application instance of the rf2 server
    """

    # select the track
    for _, track in tracks.items():
        layout = track["layout"]
        event_list = start_window.window(best_match="Selected Events:ListBox")
        select_from_list(event_list, [layout])
        sleep(1)
        # open weather and grip window
        start_window.window(best_match="Weather").click()
        grip_window = rf2_server.window(best_match=server_root_path)
        grip_window.wait("visible")
        grip_window.minimize()

        # Select the grip itself
        session_select = grip_window.window(best_match="ComboBox11")
        grip_mode_select = grip_window.window(best_match="Real Road:ListBox")
        grip_scale_select = grip_window.window(
            best_match="Real Road Time Scale:ComboBox13"
        )
        for session, grip in grips.items():
            grip_mode = grip["grip_mode"]
            grip_scale = grip["grip_scale"]
            select_from_list(session_select, [session])
            select_from_list(grip_mode_select, [grip_mode])
            select_from_list(grip_scale_select, [grip_scale])

        grip_window.window(best_match="Save").click()

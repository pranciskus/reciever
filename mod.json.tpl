{
  "server": {
    "overwrites": {
      "Multiplayer.JSON": {
        "Multiplayer Server Options": {
          "Join Password": "",
          "Admin Password": "apx",
          "Race Rejoin": 0,
          "Max MP Players": 30,
          "Maximum AI": 30,
          "Enforce Real Name": true,
          "Default Game Name": "[APX] PLACEHOLDER EVENT 1337",
          "Allowed Traction Control": 3,
          "Allowed Antilock Brakes": 2,
          "Allowed Stability Control": 2,
          "Allowed Auto Shift": 2,
          "Allowed Steering Help": 2,
          "Allowed Brake Help": 2,
          "Allowed Auto Clutch": true,
          "Allowed Invulnerability": false,
          "Allowed Auto Pit": false,
          "Allowed Opposite Lock": false,
          "Allowed Spin Recovery": false,
          "Allow AI Toggle": true
        },
        "Multiplayer General Options": {
          "Download Custom Skins": false,
          "Net Connection Type": 6,
          "Downstream Rated KBPS": 30000,
          "Upstream Rated KBPS": 30000,
          "HTTP Server Port": 23456,
          "Simulation Port": 12345
        }
      },
      "Player.JSON": {
        "Game Options": {
          "MULTI Damage Multiplier": 100,
          "Record Replays": false,
          "CURNT Fuel Consumption Multiplier": 1,
          "GPRIX Fuel Consumption Multiplier": 1,
          "MULTI Fuel Consumption Multiplier": 1,
          "RPLAY Fuel Consumption Multiplier": 1,
          "CHAMP Fuel Consumption Multiplier": 1,
          "CURNT Tire Wear Multiplier": 1,
          "GPRIX Tire Wear Multiplier": 1,
          "MULTI Tire Wear Multiplier": 1,
          "RPLAY Tire Wear Multiplier": 1,
          "CHAMP Tire Wear Multiplier": 1
        },
        "Race Conditions": {
          "MULTI Flag Rules": 2,
          "RPLAY Flag Rules": 2,
          "CHAMP Flag Rules": 2,
          "CURNT Flag Rules": 2,
          "GPRIX Flag Rules": 2,
          "MULTI RaceTimeScale": 1,
          "RPLAY RaceTimeScale": 1,
          "CHAMP RaceTimeScale": 1,
          "CURNT RaceTimeScale": 1,
          "GPRIX RaceTimeScale": 1
        },
        "Miscellaneous": {
          "WebUI port": 1335
        }
      }
    }
  },
  "conditions": {
    "P1": null,
    "Q1": null,
    "WU": null,
    "R1": null
  },
  "sessions": [
    {
      "type": "P1",
      "length": 60,
      "laps": 0,
      "start": "10:00:00",
      "weather": ""
    },
    {
      "type": "Q1",
      "length": 15,
      "laps": 0,
      "start": "12:00:00",
      "weather": ""
    },
    {
      "type": "WU",
      "length": 15,
      "laps": 0,
      "start": "13:00:00",
      "weather": ""
    },
    {
      "type": "R1",
      "length": 120,
      "laps": 0,
      "start": "16:00:00",
      "weather": ""
    }
  ],
  "cars": {
    "2559701680": {
      "entries": [],
      "entries_overwrites": {},
      "component": {
        "version": "latest",
        "name": "Tatuus_MSV_F3-020_2020",
        "update": false,
        "short": "F3-2020",
        "numberplates": []
      }
    }
  },
  "track": {
    "1559152337": {
      "layout": "Autopolis International",
      "component": {
        "version": "latest",
        "name": "Autopolis",
        "update": true
      }
    }
  },
  "start_type": 0,
  "real_weather": false,
  "temp_offset": 0,
  "comp": "pre-beta",
  "plugins": {},
  "welcome_message": "",
  "mod": {
    "name": "apx_ee966151",
    "version": "1.0.aeibh"
  },
  "suffix": null,
  "branch": "public",
  "update_on_build": false,
  "callback_target": "http://localhost:8000/addmessage/adhdfiggbccafccbadfa"
}
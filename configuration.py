# /bin/python3
# Configuration loader
import json
import math
from typing import Any


def load_config() -> None:
    global config, guild_ids
    # LINK - config.json
    with open("config.json", "r", encoding="utf8") as file:
        config = json.loads(file.read())
    guild_ids = [int(x) for x in config["server_settings"].keys()]


def save_config() -> None:
    global config
    # LINK - config.json
    with open("config.json", "w", encoding="utf8") as file:
        file.write(json.dumps(config, indent=4))


# SyntaxError: annotated name 'config' can't be global
config = dict()  # : dict[str, Any] = {}
guild_ids = list()  # : list[int] = []
load_config()

### Rate-limiting ###
config["rate_limit"]["element_count_exp"] = round(
    math.log(config["rate_limit"]["max_calls"], config["rate_limit"]["max_elements"]), 2
)  # 1.17

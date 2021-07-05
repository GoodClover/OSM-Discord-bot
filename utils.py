# /bin/python3
# Utility functions, such as coordinate calculations or data transformations.

import math
from datetime import datetime
from typing import Union
from discord import Member
## UTILS ##
def is_powerful(member: Member, guild: Guild) -> bool:
    return guild.get_role(config["server_settings"][str(guild.id)]["power_role"]) in member.roles


def str_to_date(text: str, suffix: str = "Z") -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S" + suffix)


def sanitise(text: str) -> str:
    """Make user input safe to just copy."""
    text = text.replace("@", "�")
    return text


def get_suffixed_tag(
    tags: dict[str, str],
    key: str,
    suffix: str,
) -> tuple[str, str] | tuple[None, None]:
    # Looks like two style checkers tend to disagree on argument whitespacing.
    suffixed_key = key + suffix
    if suffixed_key in tags:
        return suffixed_key, tags[suffixed_key]
    elif key in tags:
        return key, tags[key]
    else:
        return None, None


def msg_to_link(msg: Union[Message, SlashMessage]) -> str:
    return f"https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}"


def user_to_mention(user: Member) -> str:
    return f"<@{user.id}>"


def frag_to_bits(URL: str) -> tuple[int, float, float]:
    matches = re.findall(regexes.MAP_FRAGEMT_CAPTURING, URL)
    if len(matches) != 1:
        raise ValueError("Invalid map fragment URL.")
    zoom, lat, lon = matches[0]
    return int(zoom), float(lat), float(lon)


def bits_to_frag(match: tuple[int, float, float]) -> str:
    zoom, lat, lon = match
    return f"#map={zoom}/{lat}/{lon}"


def deg2tile(lat_deg: float, lon_deg: float, zoom: int) -> tuple[int, int]:
    # Previously this function was same as deg2tile_float, but output was rounded down.
    # Rounded in this way as type checher was throwing a fit at map() having unknown length
    x, y = deg2tile_float(lat_deg, lon_deg, zoom)
    return int(x), int(y)


def tile2deg(zoom: int, x: int, y: int) -> tuple[float, float]:
    """Get top-left coordinate of a tile."""
    lat_rad = math.pi - 2 * math.pi * y / (2 ** zoom)
    lat_rad = 2 * math.atan(math.exp(lat_rad)) - math.pi / 2
    lat = lat_rad * 180 / math.pi
    # Handling latitude out of range is not necessary
    # longitude maps linearly to map, so we simply scale:
    lng = -180 + (360 * x / (2 ** zoom) % 360)
    return (lat, lng)


def deg2tile_float(lat_deg: float, lon_deg: float, zoom: int) -> tuple[float, float]:
    # This is not really supposed to work, but it works.
    # By removing rounding down from deg2tile function, we can estimate
    # position where to draw coordinates during element export.
    lat_rad = math.radians(lat_deg)
    n = 2 ** zoom
    xtile = (lon_deg + 180.0) / 360 * n
    # Sets safety bounds on vertical tile range.
    if lat_deg >= 89:
        return (xtile, 0)
    if lat_deg <= -89:
        return (xtile, n - 1)
    ytile = (1 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2 * n
    return (xtile, max(min(n - 1, ytile), 0))
from __future__ import annotations
from inspect import indentsize

from typing import Any, Iterable, Union

## IMPORTS ##
import os
import random
import json
import re
import math
import requests
import time
from datetime import datetime
from urllib.parse import quote, unquote
from io import BytesIO

from dotenv import load_dotenv
import discord
from discord import Message, Client, Embed, AllowedMentions, File, Member, Intents, Guild
from discord_slash import SlashCommand, SlashContext
from discord_slash.model import SlashMessage
from discord_slash.utils.manage_commands import create_choice, create_option
from PIL import Image
from PIL import ImageDraw  # For drawing elements

try:
    import overpy
    Overpass_URL = 'https://overpass.kumi.systems/api/interpreter'
    overpass_api = overpy.Overpass(url=Overpass_URL)
except ModuleNotFoundError:
    print('OverPy was not found')

## SETUP ##
# Regex
SS = r"(?<!\/|\w)"  # Safe Start
SE = r"(?!\/|\w)"  # Safe End
DECIMAL = r"[+-]?(?:[0-9]*\.)?[0-9]+"
POS_INT = r"[0-9]+"


def load_config() -> None:
    global config, guild_ids
    # LINK - config.json
    with open("config.json", "r", encoding="utf8") as file:
        config = json.loads(file.read())
    # guild_ids = [int(x) for x in config["server_settings"].keys()]
    guild_ids = [735922875931820033, 413070382636072960]  # FIXME: Temporary whilst testing.


def save_config() -> None:
    global config
    # LINK - config.json
    with open("config.json", "w", encoding="utf8") as file:
        file.write(json.dumps(config, indent=4))


config: dict[str, Any] = {}
guild_ids: list[int] = []
load_config()

with open(config["ohno_file"], "r", encoding="utf8") as file:
    ohnos = [entry for entry in file.read().split("\n\n") if entry != ""]

with open(config["josm_tips_file"], "r", encoding="utf8") as file:
    josm_tips = [entry for entry in file.read().split("\n\n") if entry != ""]

client = Client(
    intents=Intents.all(),
    allowed_mentions=AllowedMentions(
        # I also use checks elsewhere to prevent @ injection.
        everyone=False,
        users=True,
        roles=False,
        replied_user=False,
    ),
)
slash = SlashCommand(client, sync_commands=True)


## UTILS ##
map_save_path="data/cluster.png"

def str_to_date(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


def sanitise(text: str) -> str:
    """Make user input safe to just copy."""
    text = text.replace("@", "�")
    return text


def get_suffixed_tag(
        tags: dict[str, str],
        key: str,
        suffix: str,
) -> tuple[str, str] | tuple[None, None]:
    suffixed_key = key + suffix
    if suffixed_key in tags:
        return suffixed_key, tags[suffixed_key]
    elif key in tags:
        return key, tags[key]
    else:
        return None, None


# This doesn't work correct.
# def comma_every_three(text: str) -> str:
#     return ",".join(re.findall("...", str(text)[::-1]))[::-1]


def msg_to_link(msg: Union[Message, SlashMessage]) -> str:
    return f"https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}"


def user_to_mention(user: Member) -> str:
    return f"<@{user.id}>"


## CLIENT ##


@client.event  # type: ignore
async def on_ready() -> None:
    print(f"{client.user} is connected to the following guilds:\n")
    for guild in client.guilds:
        try:
            # Update member count when bot starts up
            await update_member_count(member.guild)
        except:
            pass
        print(f" - {guild.name}: {guild.id}")
    # print(" - " + "\n - ".join([f"{guild.name}: {guild.id}" for guild in client.guilds]))


# I got annoyed by people using googlebad so often, so i implemented an easter egg.
# Set of unix timestamps.
recent_googles = set()
# Google Bad
@slash.slash(name="googlebad", description="Find your fate of using Google Maps.", guild_ids=guild_ids)  # type: ignore
async def googlebad_command(ctx: SlashContext) -> None:
    global recent_googles
    time_now = time.time()
    recent_googles = set(filter(lambda x: x > time_now - 60, recent_googles)).union({time_now})
    if len(recent_googles) > 11 and random.random() > 0.7:
        # Alternative output is triggered at 30% chance after 12 /googlebads are used in 1 minute.
        recent_googles = set()
        await ctx.send(random.choice(ohnos).replace("...", "Whenever you use `/googlebad` command,"))
        return
    await ctx.send(random.choice(ohnos).replace("...", "Whenever you mention Google Maps,"))


# JOSM Tip
@slash.slash(name="josmtip", description="Get a JOSM tip.", guild_ids=guild_ids)  # type: ignore
async def josmtip_command(ctx: SlashContext) -> None:
    await ctx.send(random.choice(josm_tips))


### TagInfo ###
@slash.slash(
    name="taginfo",
    description="Show taginfo for a tag.",
    guild_ids=guild_ids,
    options=[
        create_option(
            name="tag",
            description="The tag or key.\ne.g. `highway=road` or `building=*`",
            option_type=3,
            required=True,
        )
    ],
)  # type: ignore
async def taginfo_command(ctx: SlashContext, tag: str) -> None:
    split_tag = tag.replace("`", "").split("=", 1)

    if len(split_tag) == 2:
        if split_tag[1] == "*" or "":
            del split_tag[1]

    if len(split_tag) == 1:
        await ctx.defer()
        await ctx.send(embed=taginfo_embed(split_tag[0]))
    elif len(split_tag) == 2:
        await ctx.defer()
        await ctx.send(embed=taginfo_embed(split_tag[0], split_tag[1]))
    else:
        await ctx.send("Please provide a tag.", hidden=True)


def taginfo_embed(key: str, value: str | None = None) -> Embed:
    if value:
        data = requests.get(config["taginfo_url"] + f"api/4/tag/stats?key={quote(key)}&value={quote(value)}").json()
        data_wiki = requests.get(
            config["taginfo_url"] + f"api/4/tag/wiki_pages?key={quote(key)}&value={quote(value)}"
        ).json()
    else:
        data = requests.get(config["taginfo_url"] + f"api/4/key/stats?key={quote(key)}").json()
        data_wiki = requests.get(config["taginfo_url"] + f"api/4/key/wiki_pages?key={quote(key)}").json()

    data_wiki_en_list = [lang for lang in data_wiki["data"] if lang["lang"] == "en"]
    data_wiki_en = data_wiki_en_list[0] if data_wiki_en_list else None

    #### Embed ####
    embed = Embed()
    embed.type = "rich"

    embed.title = key
    if value:
        embed.title += "=" + value

    if value:
        embed.url = config["taginfo_url"] + "tags/" + quote(key) + "=" + quote(value)
    else:
        embed.url = config["taginfo_url"] + "keys/" + quote(key)

    embed.set_footer(
        text=config["taginfo_copyright_notice"],
        icon_url=config["taginfo_icon_url"],
    )

    if data_wiki_en and data_wiki_en["image"]["image_url"]:
        embed.set_thumbnail(
            url=data_wiki_en["image"]["thumb_url_prefix"]
                + str(config["thumb_size"])
                + data_wiki_en["image"]["thumb_url_suffix"]
        )
    else:
        embed.set_thumbnail(url=config["symbols"]["tag" if value else "key"])

    # This is the last time taginfo updated:
    embed.timestamp = str_to_date(data["data_until"])

    # embed.set_author(name="taginfo", url=config["taginfo_url"] + "about")

    if data_wiki_en:
        embed.description = data_wiki_en["description"]

    #### Fields ####
    d = data["data"][0]
    embed.add_field(
        # This gets the emoji. Removes "s" from the end if it is there to do this.
        name=config["emoji"][d["type"] if d["type"][-1] != "s" else d["type"][:-1]] + " " + d["type"],
        value=(f"{d['count']} - {d['count_fraction']*100}%" + (f"\n{d['values']} values" if not value else ""))
        if d["count"] > 0
        else "*None*",
        inline=False,
    )
    del data["data"][0]
    for d in data["data"]:
        embed.add_field(
            # This gets the emoji. Removes "s" from the end if it is there to do this.
            name=config["emoji"][d["type"] if d["type"][-1] != "s" else d["type"][:-1]] + " " + d["type"],
            value=(f"{d['count']} - {d['count_fraction']*100}%" + (f"\n{d['values']} values" if not value else ""))
            if d["count"] > 0
            else "*None*",
            inline=True,
        )

    return embed


### Elements ###
@slash.slash(
    name="elm",
    description="Show details about an element.",
    guild_ids=guild_ids,
    options=[
        create_option(
            name="type",
            description="The element's type",
            option_type=3,
            required=True,
            choices=[
                create_choice(name="node", value="node"),
                create_choice(name="way", value="way"),
                create_choice(name="relation", value="relation"),
            ],
        ),
        create_option(
            name="ID",
            description="ID of the element",
            option_type=4,
            required=True,
        ),
        create_option(
            name="extras",
            description="Comma seperated list of extras from `info`, `tags` and `members`.",
            option_type=3,
            required=False,
        ),
    ],
)  # type: ignore
async def elm_command(ctx: SlashContext, elm_type: str, elm_id: str, extras: str = "") -> None:
    extras_list = [e.strip() for e in extras.lower().split(",")]

    for extra in extras_list:
        if extra != "" and extra not in ["info", "tags", "members"]:
            await ctx.send(
                f"Unrecognised extra `{extra}`.\nPlease choose from `info`, `tags` and `members`.", hidden=True
            )
            return

    if elm_type != "relation" and "members" in extras_list:
        await ctx.send("Cannot show `members` of non-relation element.", hidden=True)
        return

    try:
        elm = get_elm(elm_type, elm_id)
    except ValueError:
        await ctx.send(f"{elm_type.capitalize()} `{elm_id}` not found.", hidden=True)
        return

    await ctx.defer()
    await ctx.send(embed=elm_embed(elm, extras_list))


def get_elm(elm_type: str, elm_id: str | int) -> dict:
    res = requests.get(config["api_url"] + f"api/0.6/{elm_type}/{elm_id}.json")

    try:
        elm = res.json()["elements"][0]
    except (json.decoder.JSONDecodeError, IndexError, KeyError):
        raise ValueError(f"Element `{elm_type}` `{elm_id}` not found")

    return elm


def elm_embed(elm: dict, extras: Iterable[str] = []) -> Embed:
    embed = Embed()
    embed.type = "rich"

    embed.url = config["site_url"] + elm["type"] + "/" + str(elm["id"])

    embed.set_footer(
        text=config["copyright_notice"],
        icon_url=config["icon_url"],
    )

    embed.set_thumbnail(url=config["symbols"][elm["type"]])

    embed.timestamp = str_to_date(elm["timestamp"])

    # embed.set_author(name=elm["user"], url=config["site_url"] + "user/" + elm["user"])

    embed.title = elm["type"].capitalize() + ": "
    if "tags" in elm:
        key, name = get_suffixed_tag(elm["tags"], "name", ":en")
    else:
        name = None
    if name:
        embed.title += f"{name} ({elm['id']})"
    else:
        embed.title += str(elm["id"])

    if elm["type"] == "node":
        embed.description = f"[{elm['lat']}, {elm['lon']}](<geo:{elm['lat']},{elm['lon']}>)\n"
    else:
        embed.description = ""

    embed.description += (
        f"[Edit](<https://www.osm.org/edit?{elm['type']}={elm['id']}>)"
        " • "
        f"[Level0](<http://level0.osmz.ru/?url={elm['type']}/{elm['id']}>)"
        "\n"
        f"[OSM History Viewer](<https://pewu.github.io/osm-history/#/{elm['type']}/{elm['id']}>)"
        " • "
        # Note: https://aleung.github.io/osm-visual-history is basically identical, but has some minor fixes missing.
        # I'm using "Visual History" as the name, despite linking to deep history, as it decribes it's function better.
        f"[Visual History](<https://osmlab.github.io/osm-deep-history/#/{elm['type']}/{elm['id']}>)"
        " • "
        f"[Mapki/Deep Diff](<http://osm.mapki.com/history/{elm['type']}.php?id={elm['id']}>)"
    )

    # ? Maybe make it read `colour=` tags for some extra pop?
    # if "colour" in elm["tags"]:
    #     embed.colour = str_to_colour(elm["tags"]["colour"])

    #### Image ####
    # * This would create significant stress to the OSM servers, so I don't reccomend it.
    # ! This doesn't work due to the OSM servers having some form of token check.
    # img_url = (
    #     "https://render.openstreetmap.org/cgi-bin/export?bbox="
    #     f"{elm['lon']-0.001},{elm['lat']-0.001},{elm['lon']+0.001},{elm['lat']+0.001}"
    #     "&scale=1800&format=png"
    # )
    # embed.set_image(url=img_url)
    # Image of element is handled separately.

    #### Fields ####
    if "info" in extras:
        embed.add_field(name="ID", value=elm["id"])
        embed.add_field(name="Version", value=f"#{elm['version']}")
        embed.add_field(name="Last edited", value=elm["timestamp"])
        embed.add_field(
            name="Last changeset", value=f"[{elm['changeset']}](<https://www.osm.org/changeset/{elm['changeset']}>)"
        )
        embed.add_field(name="Last editor", value=f"[{elm['user']}](<https://www.osm.org/user/{quote(elm['user'])}>)")

        if elm["type"] == "node":
            # Discord doesn't appear to link the geo: URI :( I've left incase it gets supported at some time.
            embed.add_field(
                name="Position (lat/lon)", value=f"[{elm['lat']}, {elm['lon']}](<geo:{elm['lat']},{elm['lon']}>)"
            )

        if "tags" in elm:
            if "wikidata" in elm["tags"]:
                embed.add_field(
                    name="Wikidata",
                    value=f"[{elm['tags']['wikidata']}](<https://www.wikidata.org/wiki/{elm['tags']['wikidata']}>)",
                )
                elm["tags"].pop("wikidata")

            if "wikipedia" in elm["tags"]:
                # Will automatically redirect to language linked in tag.
                embed.add_field(
                    name="Wikipedia",
                    value=f"[{elm['tags']['wikipedia']}](<https://wikipedia.org/wiki/{quote(elm['tags']['wikipedia'])}>)",
                )
                elm["tags"].pop("wikipedia")

            # "description", "inscription"
            for key in ["note", "FIXME", "fixme"]:
                key_languaged, value = get_suffixed_tag(elm["tags"], "note", ":en")
                if value:
                    elm["tags"].pop(key_languaged)
                    embed.add_field(name=key.capitalize(), value="> " + value, inline=False)

    if "tags" in extras:
        if "tags" in elm:
            embed.add_field(
                name="Tags",
                value="\n".join([f"`{k}={v}`" for k, v in elm["tags"].items()]),
                inline=False,
            )
        else:
            embed.add_field(name="Tags", value="*(no tags)*", inline=False)

    if "members" in extras:
        if elm["type"] != "relation":
            raise ValueError("Cannot show members of non-relation element.")
        if "members" in elm:
            text = "- " + "\n- ".join(
                [
                    f"{config['emoji'][member['type']]} "
                    + (f"`{member['role']}` " if member["role"] != "" else "")
                    + f"[{member['ref']}](https://osm.org/{member['type']}/{member['ref']})"
                    for member in elm["members"]
                ]
            )
            if len(text) > 1024:
                text = f"Too many members to list.\n[View on OSM.org](https://osm.org/{elm['type']}/{elm['id']})"
            embed.add_field(name="Members", value=text, inline=False)
        else:
            embed.add_field(name="Members", value="*(no members)*", inline=False)

    return embed


### Changesets ###
@slash.slash(
    name="changeset",
    description="Show details about a changeset.",
    guild_ids=guild_ids,
    options=[
        create_option(
            name="ID",
            description="ID of the changeset",
            option_type=4,
            required=True,
        ),
        create_option(
            name="extras",
            description="Comma seperated list of extras from `info`, `tags`.",
            option_type=3,
            required=False,
        ),
    ],
)  # type: ignore
async def changeset_command(ctx: SlashContext, changeset_id: str, extras: str = "") -> None:
    extras_list = [e.strip() for e in extras.lower().split(",")]

    for extra in extras_list:
        if extra != "" and extra not in ["info", "tags"]:
            await ctx.send(f"Unrecognised extra `{extra}`.\nPlease choose from `info` and `tags`.", hidden=True)
            return

    try:
        changeset = get_changeset(changeset_id)
    except ValueError:
        await ctx.send(f"Changeset `{changeset_id}` not found.", hidden=True)
        return

    await ctx.defer()
    await ctx.send(embed=changeset_embed(changeset, extras_list))


def get_changeset(changeset_id: str | int) -> dict:
    """Shorthand for `get_elm("changeset", changeset_id)`"""
    try:
        return get_elm("changeset", changeset_id)
    except ValueError:
        raise ValueError(f"Changeset `{changeset_id}` not found")


def changeset_embed(changeset: dict, extras: Iterable[str] = []) -> Embed:
    embed = Embed()
    embed.type = "rich"

    embed.url = config["site_url"] + "changeset/" + str(changeset["id"])

    embed.set_footer(
        text=config["copyright_notice"],
        icon_url=config["icon_url"],
    )

    # There doesn't appear to be a changeset icon
    # embed.set_thumbnail(url=config["symbols"]["changeset"])

    embed.timestamp = str_to_date(changeset["closed_at"])

    embed.set_author(name=changeset["user"], url=config["site_url"] + "user/" + quote(changeset["user"]))

    embed.title = f"Changeset: {changeset['id']}"

    #### Description ####
    embed.description = ""

    if "tags" in changeset and "comment" in changeset["tags"]:
        embed.description += "> " + changeset["tags"]["comment"].strip().replace("\n", "\n> ") + "\n\n"
        changeset["tags"].pop("comment")
    else:
        embed.description += "*(no comment)*\n\n"

    embed.description += f"[OSMCha](<https://osmcha.org/changesets/{changeset['id']}>)"

    #### Image ####
    # * This would create significant stress to the OSM servers, so I don't reccomend it.
    # ! This doesn't work due to the OSM servers having some form of token check.
    # img_url = (
    #     "https://render.openstreetmap.org/cgi-bin/export?bbox="
    #     f"{changeset['minlon']},{changeset['minlat']},{changeset['maxlon']},{changeset['maxlat']}"
    #     "&scale=1800&format=png"
    # )
    # embed.set_image(url=img_url)
    # Easiest way to handle changeset rendering is to just draw bounding box to top tile.

    #### Fields ####
    if "info" in extras:
        embed.add_field(name="Comments", value=changeset["comments_count"])
        embed.add_field(name="Changes", value=changeset["changes_count"])
        embed.add_field(name="Created", value=changeset["created_at"])
        embed.add_field(name="Closed", value=changeset["closed_at"])

        if "tags" in changeset:
            if "source" in changeset["tags"]:
                embed.add_field(name="Source", value=changeset["tags"]["source"])
                changeset["tags"].pop("source")

            if "created_by" in changeset["tags"]:
                embed.add_field(name="Created by", value=changeset["tags"]["created_by"])
                changeset["tags"].pop("created_by")

    if "tags" in extras:
        if "tags" in changeset:
            embed.add_field(
                name="Tags",
                value="- " + "\n- ".join([f"`{k}={v}`" for k, v in changeset["tags"].items()]),
                inline=False,
            )
        else:
            embed.add_field(name="Tags", value="*(no tags)*", inline=False)

    return embed


### Users ###
@slash.slash(
    name="user",
    description="Show details about a user.",
    guild_ids=guild_ids,
    options=[
        create_option(
            name="username",
            description="Username of the user.",
            option_type=3,
            required=True,
        ),
        create_option(
            name="extras",
            description="Comma seperated list of extras from `info`.",
            option_type=3,
            required=False,
        ),
    ],
)  # type: ignore
async def user_command(ctx: SlashContext, username: str, extras: str = "") -> None:
    extras_list = [e.strip() for e in extras.lower().split(",")]

    for extra in extras_list:
        if extra != "" and extra not in ["info"]:
            await ctx.send(f"Unrecognised extra `{extra}`.\nPlease choose from `info`.", hidden=True)
            return

    try:
        # Both will raise ValueError if the user isn't found, get_id_from_username will usually error first.
        # In cases where the account was only removed recently, get_user will error.
        user_id = get_id_from_username(username)
        user = get_user(user_id)
    except ValueError:
        await ctx.send(f"User `{username}` not found.", hidden=True)
        return

    await ctx.defer()
    await ctx.send(embed=user_embed(user, extras_list))


def get_id_from_username(username: str, ) -> int:
    whosthat = requests.get(config["whosthat_url"] + "whosthat.php?action=names&q=" + username).json()
    if len(whosthat) > 0:
        return whosthat[0]["id"]
    else:
        raise ValueError(f"User `{username}` not found")


def get_user(user_id: str | int) -> dict:
    res = requests.get(config["api_url"] + f"api/0.6/user/{user_id}.json")

    try:
        user = res.json()["user"]
    except (json.decoder.JSONDecodeError, IndexError, KeyError):
        raise ValueError(f"User `{user_id}` not found")

    return user


def user_embed(user: dict, extras: Iterable[str] = []) -> Embed:
    embed = Embed()
    embed.type = "rich"

    url_safe_user = quote(user["display_name"])

    embed.url = config["site_url"] + "user/" + url_safe_user

    embed.set_footer(
        text=config["copyright_notice"],
        icon_url=config["icon_url"],
    )

    if "img" in user:
        embed.set_thumbnail(url=user["img"]["href"])
    else:
        embed.set_thumbnail(url=config["symbols"]["user"])

    # embed.timestamp = datetime.now()
    # embed.timestamp = str_to_date(user["account_created"])

    embed.title = "User: " + user["display_name"]

    embed.description = (
        f"[HDYC](<https://hdyc.neis-one.org/?{url_safe_user}>)"
        " • "
        f"[YOSMHM](<https://yosmhm.neis-one.org/?{url_safe_user}>)"
    )

    #### Fields ####
    if "info" in extras:
        if len(user["roles"]) > 0:
            embed.add_field(name="Roles", value=", ".join(user["roles"]))
        embed.add_field(name="Changesets", value=user["changesets"]["count"])
        embed.add_field(name="Traces", value=user["traces"]["count"])
        embed.add_field(name="Contributor Terms", value="Agreed" if user["contributor_terms"]["agreed"] else "Unknown")
        embed.add_field(name="User since", value=user["account_created"][:10])
        if user["blocks"]["received"]["count"] > 0:
            embed.add_field(
                name="Blocks",
                value=f"Count: {user['blocks']['received']['count']}\nActive: {user['blocks']['received']['active']}",
            )

    return embed


### Show Map ###
@slash.slash(
    name="showmap",
    description="Show the map of an area from URL fragment.",
    guild_ids=guild_ids,
    options=[
        create_option(
            name="URL",
            description="URL that ends in a fragment, or just the fragment. e.g. `#map=19/33.45169/126.48982`",
            option_type=3,
            required=True,
        )
    ],
)  # type: ignore
async def showmap_command(ctx: SlashContext, URL: str) -> None:
    try:
        zoom_int, lat_deg, lon_deg = frag_to_bits(URL)
    except ValueError:
        await ctx.send("Invalid map fragment. Expected to be in format `#map=zoom/lat/lon`", hidden=True)
        return

    # * Discord has a weird limitation where you can't send an attachment (image) in the first slash command respose.
    first_msg = await ctx.send("Getting image…")
    with ctx.channel.typing():

        image_file, errorlog = await get_image_cluster(lat_deg, lon_deg, zoom_int)

        # TODO: I probabbly need to get some better injection protection at some point.
        # This works though so eh ¯\_(ツ)_/¯
        msg = f"<{config['site_url']}#map={zoom_int}/{lat_deg}/{lon_deg}>"

        img_msg = await ctx.channel.send(msg, file=image_file)

    await first_msg.edit(content=f'Getting image… Done[!](<{msg_to_link(img_msg)}> "Link to message with image") :map:')


MAP_FRAGEMT_CAPTURING_REGEX = rf"#map=({POS_INT})\/({DECIMAL})\/({DECIMAL})"


def frag_to_bits(URL: str) -> tuple[int, float, float]:
    matches = re.findall(MAP_FRAGEMT_CAPTURING_REGEX, URL)
    if len(matches) != 1:
        raise ValueError("Invalid map fragment URL.")
    zoom, lat, lon = matches[0]
    return int(zoom), float(lat), float(lon)


def bits_to_frag(match: tuple[int, float, float]) -> str:
    zoom, lat, lon = match
    return f"#map={zoom}/{lat}/{lon}"


def deg2tile(lat_deg: float, lon_deg: float, zoom: int): -> tuple[int, int]
    # I have no clue how this works.
    # Taken from https://github.com/ForgottenHero/mr-maps
    # Previously this function was same as deg2tile_float, but output was rounded down.
    return tuple(map(int, deg2tile_float(lat_deg, lon_deg, zoom)))


def tile2deg(zoom: int, x: int, y: int) -> tuple[float, float]:
    # Gets top-left coordinate of tile.
    lat_rad = math.pi - 2 * math.pi * y / (2 ** zoom)
    lat_rad = 2 * math.atan(math.exp(lat_rad)) - math.pi / 2
    lat = lat_rad * 180.0 / math.pi
    # Handling latitude out of range is not necessary
    # longitude maps linearly to map, so we simply scale:
    lng = -180.0 + (360.0 * x / (2 ** zoom) % 360)
    return (lat, lng)


def deg2tile_float(lat_deg: float, lon_deg: float, zoom: int) -> tuple[int, int]:
    # This is not really supposed to work, but it works.
    # By removing rounding down from deg2tile function, we can estimate
    # position where to draw coordinates during element export.
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = (lon_deg + 180.0) / 360.0 * n
    # Sets safety bounds on vertical tile range.
    if lat_deg >= 89:
        return (xtile, 0)
    if lat_deg <= -89:
        return (xtile, n - 1)
    ytile = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n
    return (xtile, max(min(n - 1, ytile), 0))


def elms_to_render(elem_type: str, elem_id: str | int, no_reduction=False: bool) -> list[list[tuple[float, float]]]:
    # Inputs:   element_type (node / way / relation)
    #           elem_id     element's OSM ID as string
    # Queries OSM element geometry via overpass API.
    # Example: elms_to_render('relation', '60189')  (Russia)
    # To be tested with relation 908054 - Public transport network of Sofia.
    # Possible alternative approach to rendering by creating very rough drawing on bot-side.
    # Using overpass to query just geometry.
    # And then draw just very few nodes onto map retrieved by showmap
    # Even easier alternative is drawing bounding box
    # Throws IndexError if element was not found
    # Needs handling for Overpass's over quota error.
    # Future improvement possibility: include tags into output to control rendering, especially colours.
    result = overpass_api.query('[out:json][timeout:15];' + elem_type + '(id:' + str(elem_id) + ');out skel geom;')
    # Since we are querying for single element, top level result will have just 1 element.
    node_count = 0
    if elem_type == 'relation':
        segments = []
        seg_ends = dict()
        elems = result.relations[0].members
        prev_last = None
        for i in range(len(elems)):
            # Previously it skipped elements based on role, but it was buggy.
            # New, recursive approach.
            if type(elems[i]) == overpy.RelationRelation:
                seg=elms_to_render('relation', elems[i].ref, True)
                segments+=seg
            elif type(elems[i]) == overpy.RelationNode:  # Single node as member of relation
                segments.append([(float(elems[i].attributes['lat']), float(elems[i].attributes['lon']))])
                
            elif type(elems[i]) == overpy.RelationWay:
                geom = elems[i].geometry
                segments.append(list(map(lambda x: (float(x.lat), float(x.lon)), geom)))
    elif elem_type == 'way':
        elems = result.ways[0]
        segments = [list(map(lambda x: (float(x.lat), float(x.lon)), elems.get_nodes(True)))]  # True means resolving node references.
    elif elem_type == 'node':
        # Creates simply a single-node segment.
        segments = [[float(result.nodes[0].lat), float(result.nodes[0].lon)]]
    else:  # If encountered unknown element type.
        return []
    if no_reduction:
        return segments
    #segments=merge_segments(segments)
    segments = reduce_segment_nodes(segments)
    # We now have list of lists of (lat, lon) coordinates to be rendered.
    # These lists of segments can be joined, if multiple elements are requested
    # In order to add support for colours, just create segment-colour pairs.
    return segments


def merge_segments(segments: list[list[tuple[float, float]]]): -> list[list[tuple[float, float]]]
    # Other bug occurs in case some ways of relation are reversed.
    # Ideally, this should merge two segments, if they share same end and beginning node.
    # Merges some ways together. For russia, around 4000 ways became 34 segments.
    seg_ends=dict()
    # first = (float(geom[0].lat), float(geom[0].lon))
    # last = (float(geom[-1].lat), float(geom[-1].lon))
    # # Adding and removing elements is faster at end of list
    # if first in seg_ends:
    #     # Append current segment to end of existing one
    #     segments[seg_ends[first]] += geom[1:]
    #     seg_ends[last] = seg_ends[first]
    #     del seg_ends[first]
    # elif last in seg_ends:
    #     # Append current segment to beginning of existing one
    #     segments[seg_ends[last]] += geom[:-1]
    #     seg_ends[first] = seg_ends[last]
    #     del seg_ends[last]
    # else:
    #     # Create new segment
    #     segments.append(geom)
    #     seg_ends[last] = len(segments) - 1
    #     seg_ends[first] = len(segments) - 1
    return segments


def reduce_segment_nodes(segments: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    # Relative simple way to reduce nodes by just picking every n-th node.
    # Ignores ways with less than 50 nodes.
    # Excel equivalent is =IF(A1<50;A1;SQRT(A1-50)+50)
    Limiter_offset = 50  # Minimum number of nodes.
    Reduction_factor = 2  # n-th root by which array length is reduced.
    calc_limit = lambda x: x if x < Limiter_offset else int(
        (x - Limiter_offset) ** (1 / Reduction_factor) + Limiter_offset)
    for seg_num in range(len(segments)):
        segment = segments[seg_num]  # For each segment
        seg_len = len(segment)
        limit = calc_limit(seg_len)  # Get number of nodes allowed
        step = seg_len / limit  # Average number of nodes to be skipped
        position = 0
        temp_array = []
        while position < seg_len:  # Iterates over segment
            temp_array.append(segment[int(position)])  # And select only every step-th node
            position += step  # Using int(position) because step is usually float.
        if int(position - step) != seg_len - 1:  # Always keep last node,
            temp_array.append(segment[-1])  # But only if it's not added already.
        # Convert overpy-node-objects into (lat, lon) pairs.
        try:
            segments[seg_num] = list(map(lambda x: (float(x.lat), float(x.lon)), temp_array))
        except AttributeError:
            pass  # Encountered relation node, see ln 794
    reduced = list(map(list, set(map(tuple, segments))))
    print(len(segments), len(reduced))
    # with elms_to_render('relation','908054')
    # Result:  15458 vs 6564
    return reduced


def get_render_queue_bounds(segments: list[list[tuple[float, float]]]): -> tuple[float, float, float, float]
    # Finds bounding box of rendering queue (segments)
    # Rendering queue is bunch of coordinates that was calculated in previous function.
    min_lat, max_lat, min_lon, max_lon = 90, -90, 180, -180
    precision = 5  # https://xkcd.com/2170/
    for segment in segments:
        for coordinates in segment:
            lat, lon = coordinates
            if lat > max_lat: max_lat = round(lat, precision)
            if lat < min_lat: min_lat = round(lat, precision)
            if lon > max_lon: max_lon = round(lon, precision)
            if lon < min_lon: min_lon = round(lon, precision)
    if min_lat == max_lat:  # In event when all coordinates are same...
        min_lat -= 10 ** (-precision)
        max_lat += 10 ** (-precision)
    if min_lon == max_lon:  # Add small variation to not end up in ZeroDivisionError
        min_lon -= 10 ** (-precision)
        max_lon += 10 ** (-precision)
    return (min_lat, max_lat, min_lon, max_lon)


def calc_preview_area(queue_bounds: tuple[float, float, float, float]) -> tuple[int, float, float]:
    # Input: tuple (min_lat, max_lat, min_lon, max_lon)
    # Output: tuple (int(zoom), float(lat), float(lon))
    # Based on old showmap function and https://wiki.openstreetmap.org/wiki/Zoom_levels
    # Finds map area, that should contain all elements.
    min_lat, max_lat, min_lon, max_lon = queue_bounds
    tiles_x, tiles_y = 5, 5
    delta_lat = max_lat - min_lat
    delta_lon = max_lon - min_lon
    zoom_x = int(math.log2((360 / delta_lon) * tiles_x))
    center = delta_lat / 2 + min_lat, delta_lon / 2 + min_lon
    zoom_y = 22  # Zoom level is determined by trying to fit x/y bounds into 5 tiles.
    while (deg2tile(min_lat, 0, zoom_y)[1] - deg2tile(max_lat, 0, zoom_y)[1] + 1) > tiles_y:
        zoom_y -= 1  # Bit slow and dumb approach
    zoom = min(zoom_x, zoom_y, 19)
    return (zoom, *center)


HEADERS = {
    "User-Agent": "OSM Discord Bot <https://github.com/GoodClover/OSM-Discord-bot>",
    "Accept": "image/png",
    "Accept-Charset": "utf-8",
    "Accept-Encoding": "none",
    "Accept-Language": "en-GB,en",
    "Connection": "keep-alive",
}


async def get_image_cluster_old(
        lat_deg: float,
        lon_deg: float,
        zoom: int,
        tile_url: str = config["tile_url"],
) -> File:
    # Modified from https://github.com/ForgottenHero/mr-maps
    delta_long = 0.00421 * math.pow(2, 19 - int(zoom))
    delta_lat = 0.0012 * math.pow(2, 19 - int(zoom))
    lat_deg = float(lat_deg) - (delta_lat / 2)
    lon_deg = float(lon_deg) - (delta_long / 2)
    i = 0
    j = 0
    xmin, ymax = deg2tile(lat_deg, lon_deg, zoom)
    xmax, ymin = deg2tile(lat_deg + delta_lat, lon_deg + delta_long, zoom)
    Cluster = Image.new("RGB", ((xmax - xmin + 1) * 256 - 1, (ymax - ymin + 1) * 256 - 1))
    for xtile in range(xmin, xmax + 1):
        for ytile in range(ymin, ymax + 1):
            try:
                res = requests.get(tile_url.format(zoom=zoom, x=xtile, y=ytile), headers=HEADERS)
                tile = Image.open(BytesIO(res.content))
                Cluster.paste(tile, box=((xtile - xmin) * 256, (ytile - ymin) * 255))
                i = i + 1
            except Exception as e:
                print(e)
        j = j + 1
    Cluster.save(map_save_path)
    # return File(map_save_path)
    return Cluster


def get_image_tile_range(
        lat_deg: float,
        lon_deg: float,
        zoom: int) -> tuple[int, int, int, int]:
    # Following line is duplicataed at calc_preview_area()
    tiles_x, tiles_y = 5, 5
    center_x, center_y = deg2tile(lat_deg, lon_deg, zoom)
    xmin, xmax = center_x - int(tiles_x / 2), center_x + int(tiles_x / 2)
    n = 2.0 ** zoom  # N is number of tiles in one direction on zoom level
    if tiles_x % 2 == 0: xmax -= 1
    ymin, ymax = center_y - int(tiles_y / 2), center_y + int(tiles_y / 2)
    if tiles_y % 2 == 0: ymax -= 1
    ymin = max(ymin, 0)  # Sets vertical limits to area.
    ymax = min(ymax, n)
    return xmin, xmax, ymin, ymax


async def get_image_cluster(
        lat_deg: float,
        lon_deg: float,
        zoom: int,
        tile_url: str = config["tile_url"],
) -> File:
    # Rewrite of https://github.com/ForgottenHero/mr-maps
    # Following line is duplicataed at calc_preview_area()
    n = 2.0 ** zoom  # N is number of tiles in one direction on zoom level
    tile_w, tile_h = 256, 256
    xmin, xmax, ymin, ymax = get_image_tile_range(lat_deg, lon_deg, zoom)
    errorlog = []
    tile_offset=deg2tile_float(lat_deg, lon_deg, zoom)
    # tile_offset - By how many tiles should tile grid shifted up left.
    tile_offset=(tile_offset[0] % 1, tile_offset[1] % 1)
    Cluster = Image.new("RGB", ((xmax - xmin + 1) * tile_w - 1, (ymax - ymin + 1) * tile_h - 1))
    for xtile in range(xmin, xmax + 2):
        xtile = xtile % n  # Repeats tiles across -180/180 meridian.
        for ytile in range(ymin, ymax + 2):
            try:
                res = requests.get(tile_url.format(zoom=zoom, x=xtile, y=ytile), headers=HEADERS)
                tile = Image.open(BytesIO(res.content))
                Cluster.paste(tile, box=((xtile - xmin - tile_offset[0]) * tile_w, (ytile - ymin - tile_offset[1]) * tile_h))
            except Exception as e:
                print(e)
                errorlog.append(('map tile', tile_url.format(zoom=zoom, x=xtile, y=ytile)))
    Cluster.save(map_save_path)
    return Cluster, errorlog


def draw_line(segment: list[tuple[float, float]], draw, colour='red'): -> None
    # https://stackoverflow.com/questions/59060887
    # This is polyline of all coordinates on array.
    draw.line(segment, fill=colour, width=2)


def draw_node(coord: tuple[float, float], draw, colour='red') -> None:
    # https://stackoverflow.com/questions/2980366
    r = 3
    x, y = coord
    leftUpPoint = (x - r, y - r)
    rightDownPoint = (x + r, y + r)
    twoPointList = [leftUpPoint, rightDownPoint]
    draw.ellipse(twoPointList, fill=colour)


def render_elms_on_cluster(Cluster, render_queue: list[list[tuple[float, float]]], frag: Iterable[int, float, float]):
    # Inputs:   Cluster - PIL image
    #           render_queue - [[(lat, lon), ...], ...]
    #           frag  - zoom, lat, lon used  for cluster rendering input.
    # Renderer requires epsg 3587 crs converter. Implemented in deg2tile_float.
    # Use solution similar to get_image_cluster, but use deg2tile_float function to get xtile/ytile.
    # I think tile calculation should be separate from get_image_cluster.
    zoom, lat_deg, lon_deg = frag
    n = 2.0 ** zoom  # N is number of tiles in one direction on zoom level
    tile_w, tile_h = 256, 256
    xmin, xmax, ymin, ymax = get_image_tile_range(lat_deg, lon_deg, zoom)
    # Convert geographical coordinates to X-Y coordinates to be used on map.
    draw = ImageDraw.Draw(Cluster)  # Not sure what it does, just following https://stackoverflow.com/questions/59060887
    tile_offset=deg2tile_float(lat_deg, lon_deg, zoom)
    # tile_offset - By how many tiles should tile grid shifted up left.
    tile_offset=(tile_offset[0] % 1, tile_offset[1] % 1)
    # Basic demo for colour picker.
    colors = ['#000', '#700', '#f00', '#070', '#0f0', '#f60']
    len_colors = len(colors)
    for seg_num in range(len(render_queue)):
        for i in range(len(render_queue[seg_num])):
            coord = render_queue[seg_num][i]
            # Following returns X/Y similar to tile number, but as floats.
            coord = deg2tile_float(coord[0], coord[1], zoom)
            coord = round((coord[0] - xmin - tile_offset[0]) * tile_w), round((coord[1] - ymin - tile_offset[1]) * tile_h)
            # Coord is now actual pixels, where line must be drawn on image.
            render_queue[seg_num][i] = coord
        # Draw segment onto image
        color = colors[seg_num % len_colors]
        draw_line(render_queue[seg_num], draw, color)
        # Maybe nodes shouldn't be rendered, if way has many, let's say 80+ nodes, 
        # because it would become too cluttered?
        if len(render_queue[seg_num]) < 80:
            draw_node(render_queue[seg_num][0], draw, color)
            if len(render_queue[seg_num]) > 1:
                for node_num in range(1, len(render_queue[seg_num])):
                    draw_node(render_queue[seg_num][node_num], draw, color)
    Cluster.save(map_save_path)
    return Cluster
    # I barely know how to draw lines in PIL


@client.event  # type: ignore
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
    # Probably needs testing. It should maybe remove bot's own message,
    # if someone reacts with wastebasket emoji
    # For safety reasons, it should also authenticate reacting user
    # Currently anyone can delete bot's message.
    waste_basket = b'\xf0\x9f\x97\x91\xef\xb8\x8f'
    if (payload.emoji.name.encode('utf8') != waste_basket):
        return
    # Fetch message is rather slow operation, that's why it only takes place if user reacts with wastebasket
    msg = await client.get_channel(payload.channel_id).fetch_message(payload.message_id)
    # Safety check
    if (msg.author != client.user and msg.author != payload.member):
        return  # Delete message only if it's made by bot or the user who reacted.
    # Allow only users whom bot originally replied to delete message.
    # This portion of if-statements is not tested.
    if (msg.author == client.user and msg.reference):  # If bot replied to someone
        if not msg.reference.fail_if_not_exists:  # If replied message exists
            msg2 = await client.get_channel(msg.reference.channel_id).fetch_message(msg.reference.message_id)
            if (msg2.author != payload.member):  # If current reacting user isn't author of original message
                return  # who added reaction.
    await msg.delete()


### Inline linking ###
ELM_INLINE_REGEX = rf"{SS}(node|way|relation)(s? |\/)({POS_INT}(?:(?:, | and | or | )(?:{POS_INT}))*){SE}"
CHANGESET_INLINE_REGEX = rf"{SS}(changeset)(s? |\/)({POS_INT}(?:(?:, | and | or | )(?:{POS_INT}))*){SE}"
USER_INLINE_REGEX = rf"{SS}user\/[\w\-_]+{SE}"
# FIXME: For some reason this allows stuff after the end of the map fragment.
MAP_FRAGMENT_INLINE_REGEX = rf"{SS}#map={POS_INT}\/{DECIMAL}\/{DECIMAL}{SE}"


@client.event  # type: ignore
async def on_message(msg: Message) -> None:
    if msg.author == client.user:
        return

    #### Try my commands, those are gone ####
    if msg.content.startswith("?josmtip"):
        await msg.channel.send("Try `/josmtip` :thinking:")
    elif msg.content.startswith("?googlebad"):
        await msg.channel.send("Try `/googlebad` :wink:")
    elif msg.content.startswith("€showmap"):
        await msg.channel.send("Try `/showmap` :map:")

    #### Inline linking ####
    # Find matches
    # elm[0] - element type (node/way/relation/changeset)
    # elm[1] - separator used
    # elm[2] - element ID
    elms = [(elm[0], tuple(re.findall('\d+', elm[2])), elm[1]) for elm in re.findall(ELM_INLINE_REGEX, msg.clean_content)]
    changesets = [(elm[0], tuple(re.findall('\d+', elm[2])), elm[1]) for elm in re.findall(CHANGESET_INLINE_REGEX, msg.clean_content)]
    users = [thing.split("/")[1] for thing in re.findall(USER_INLINE_REGEX, msg.clean_content)]
    map_frags = re.findall(MAP_FRAGMENT_INLINE_REGEX, msg.clean_content)

    if (len(elms) + len(changesets) + len(users) + len(map_frags)) == 0:
        return
    ask_confirmation = False
    for match in elms + changesets:
        if match[2] != '/' or len(match[1]) > 1:  # Found case when user didn't use standard node/123 format
            ask_confirmation = True
    # Ask user confirmation by reacting with :mag_right: emoji.
    if ask_confirmation:
        reaction_string = '\U0001f50e'  # :mag_right:
        await msg.add_reaction(reaction_string)

        def check(reaction, user_obj):
            return user_obj == msg.author and str(reaction.emoji) == reaction_string

        try:
            reaction, user_obj = await client.wait_for('reaction_add', timeout=15.0, check=check)
        except asyncio.TimeoutError:  # User didn't respond
            await message.clear_reaction(reaction_string)
            return
        else:  # User responded
            await message.clear_reaction(reaction_string)
    render_queue: list[list[tuple[float]]] = []

    # TODO: Give a message upon stuff being 'not found', rather than just ignoring it.

    async with msg.channel.typing():
        # Create the messages
        embeds: list[Embed] = []
        files: list[File] = []
        errorlog: list[Str] = []

        for elm_type, elm_ids, separator in elms:
            for elm_id in elm_ids:
                try:
                    embeds.append(elm_embed(get_elm(elm_type, elm_id)))
                    render_queue += elms_to_render(elm_type, elm_id)
                except ValueError:
                    errorlog.append((elm_type, elm_id))

        for elm_type, changeset_ids, separator in changesets:
            # changeset_ids = (<tuple: list of changesets>, <str: separator used>)
            for changeset_id in changeset_ids:
                try:
                    embeds.append(changeset_embed(get_changeset(changeset_id)))
                except ValueError:
                    errorlog.append((elm_type, changeset_id))

        # Next step is to calculate map area for render.
        if render_queue:
            bbox = get_render_queue_bounds(render_queue)
            zoom, lat, lon = calc_preview_area(bbox)
            cluster, errors=await get_image_cluster(lat, lon, zoom)
            errorlog+=errors
            cluster=render_elms_on_cluster(cluster, render_queue, (zoom, lat, lon))
            file=File(map_save_path)
            files.append(file)

        for username in users:
            try:
                embeds.append(user_embed(get_user(get_id_from_username(username))))
            except ValueError:
                errorlog.append(('user', username))

        for map_frag in map_frags:
            zoom, lat, lon = frag_to_bits(map_frag)
            cluster, errors = await get_image_cluster(lat, lon, zoom)
            file=File(map_save_path)
            errorlog += errors
            files.append(file)

        # Send the messages
        if len(embeds) > 0:
            await msg.channel.send(embed=embeds[0], reference=msg)
            for embed in embeds[1:]:
                await msg.channel.send(embed=embed)
            for file in files:
                await msg.channel.send(file=file)
        # Sending files is also handled in embeds messaging.
        elif len(files) > 0:
            await msg.channel.send(file=files[0], reference=msg)
            for file in files[1:]:
                await msg.channel.send(file=file)
        if len(errorlog) > 0:
            for element_type, element_id in errorlog:
                await msg.channel.send(f"Error occurred while processing {element_type}/{element_id}.")


### Member count ###
@client.event  # type: ignore
async def on_member_join(member: Member) -> None:
    await update_member_count(member.guild)


@client.event  # type: ignore
async def on_member_remove(member: Member) -> None:
    await update_member_count(member.guild)


async def update_member_count(guild: Guild) -> None:
    mappers_count_channel = guild.get_channel(config["server_settings"][str(guild.id)]["mappers_count_channel"])
    text = config["mappers_count_text"].replace("{mappers}", str(guild.member_count))
    await mappers_count_channel.edit(name=text)


### Suggestions ###
@slash.slash(
    name="suggest",
    description="Send a suggestion.",
    guild_ids=guild_ids,
    options=[
        create_option(
            name="Suggestion",
            description="Your suggestion, be sensible.",
            option_type=3,
            required=True,
        )
    ],
)  # type: ignore
async def suggest_command(ctx: SlashContext, suggestion: str) -> None:
    if not config["server_settings"][str(ctx.guild.id)]["suggestions_enabled"]:
        await ctx.send("Suggestions are not enabled on this server.", hidden=True)
        return

    await ctx.defer(hidden=True)

    suggestion_chanel = client.get_channel(config["server_settings"][str(ctx.guild.id)]["suggestion_channel"])

    suggestion = sanitise(suggestion).replace("\n", "\n> ")

    sugg_msg = await suggestion_chanel.send(
        f"""
__**New suggestion posted**__
By: <@!{ctx.author.id}>
> {suggestion}

Vote with {config['emoji']['vote_yes']}, {config['emoji']['vote_abstain']} and {config['emoji']['vote_no']}.
"""
    )
    await ctx.send(
        f"Sent suggestion in <#{config['server_settings'][str(ctx.guild.id)]['suggestion_channel']}>."
        + msg_to_link(sugg_msg),
        hidden=True,
    )
    await sugg_msg.add_reaction(config["emoji"]["vote_yes"])
    await sugg_msg.add_reaction(config["emoji"]["vote_abstain"])
    await sugg_msg.add_reaction(config["emoji"]["vote_no"])


@slash.slash(
    name="close_suggestion",
    description="Closes a suggestion. This can be run on already closed suggestions to change the result.",
    guild_ids=guild_ids,
    options=[
        create_option(
            name="ID",
            description="The message ID of the suggestion. With developer mode on, right click the message → `Copy ID`",
            option_type=3,
            required=True,
        ),
        create_option(
            name="result",
            description="The result of the suggestion, e.g. `accepted`. Freeform value.",
            option_type=3,
            required=True,
        ),
    ],
)  # type: ignore
async def close_suggestion_command(ctx: SlashContext, msg_id: int, result: str) -> None:
    if not config["server_settings"][str(ctx.guild.id)]["suggestions_enabled"]:
        await ctx.send("Suggestions are not enabled on this server.", hidden=True)
        return

    if not ctx.guild.get_role(config["server_settings"][str(ctx.guild.id)]["power_role"]) in ctx.author.roles:
        await ctx.send("You do not have permission to run this command.", hidden=True)
        return

    await ctx.defer(hidden=True)

    suggestion_chanel = client.get_channel(config["server_settings"][str(ctx.guild.id)]["suggestion_channel"])

    try:
        msg = await suggestion_chanel.fetch_message(msg_id)
    except discord.errors.NotFound:
        await ctx.send("Message not found. Likely an incorrect ID or it is not in the suggestion channel.", hidden=True)
        return

    if msg.author.id != client.user.id:
        await ctx.send("I can't modify that message, as it was not created by me :P", hidden=True)
        return

    sugg_msg = await msg.edit(
        content=msg.content.split("\n\n")[0]
                + f"\n\nVoting closed by {user_to_mention(ctx.author)}.\nResult: **{sanitise(result)}**"
    )

    await ctx.send(
        f"Closed suggestion with result '{result}'.\nYou can re-run this command to change the reuslt.\n{msg_to_link(msg)}",
        hidden=True,
    )


## MAIN ##

if __name__ == "__main__":
    load_dotenv()
    client.run(os.getenv("DISCORD_TOKEN"))

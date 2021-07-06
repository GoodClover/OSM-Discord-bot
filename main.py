# /bin/python3
from __future__ import annotations

import asyncio
import functools
import json
import math
import os
import random
import re
import time
from datetime import datetime
from io import BytesIO
from multiprocessing import Pool
from typing import Any
from typing import Iterable
from typing import Union
from urllib.parse import quote

import aiohttp
import discord
import overpy
import requests
from discord import AllowedMentions
from discord import Client
from discord import Embed
from discord import File
from discord import Guild
from discord import Intents
from discord import Member
from discord import Message
from discord_slash import SlashCommand
from discord_slash import SlashContext
from discord_slash.context import ComponentContext
from discord_slash.model import ButtonStyle
from discord_slash.model import SlashMessage
from discord_slash.utils import manage_components
from discord_slash.utils.manage_commands import create_choice
from discord_slash.utils.manage_commands import create_option
from dotenv import load_dotenv
from PIL import Image
from PIL import ImageDraw  # For drawing elements

import regexes
from utils import *
import utils
from configuration import config, guild_ids

## SETUP ##
cached_files: set = set()  # Global set of saved filenames. If on_message fails, it will remove cached files in way similar to /googlebad.
recent_googles: set = set()  # Set of unix timestamps.
command_history: dict = dict()  # Global per-user dictionary of sets to keep track of rate-limiting per-user.

### Rendering ###
# max_zoom - Maximum zoom level without notes.
# Max_note_zoom - Maximum zoom, when notes are present on map.
# tile_w/tile_h - Tile size used for renderer
# tiles_x/tiles_y - Dimensions of output map fragment
# tile_margin_x / tile_margin_y - How much free space is left at edges
# Used in render_elms_on_cluster. List of colours to be cycled.
# Colours need to be reworked for something prettier, therefore don't relocate them yet.
element_colors = ["#000", "#700", "#f00", "#070", "#0f0", "#f60"]

overpass_api = overpy.Overpass(url=config["overpass_url"])

res = requests.get(config["symbols"]["note_solved"], headers=config["rendering"]["HEADERS"])
closed_note_icon = Image.open(BytesIO(res.content))
res = requests.get(config["symbols"]["note_open"], headers=config["rendering"]["HEADERS"])
open_note_icon = Image.open(BytesIO(res.content))
open_note_icon_size = open_note_icon.size
closed_note_icon_size = closed_note_icon.size

INSPECT_EMOJI = config["emoji"]["inspect"]  # :mag_right:  
IMAGE_EMOJI = config["emoji"]["image"]  # :frame_photo:
EMBEDDED_EMOJI = config["emoji"]["embedded"]  # :bed:
CANCEL_EMOJI = config["emoji"]["cancel"]  # :x:
DELETE_EMOJI = config["emoji"]["inspect"]  # :wastebasket:
LOADING_EMOJI = config["emoji"]["delete"]  # :loading:
LEFT_SYMBOL = config["emoji"]["left"]  # "←"
RIGHT_SYMBOL = config["emoji"]["right"]  # "→"
CANCEL_SYMBOL = config["emoji"]["cancel_utf"]  # "✘"

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
def check_rate_limit(user, extra=0):
    # Sorry for no typehints, i don't know what types to have
    tnow = round(time.time(), 1)
    if user not in command_history:
        command_history[user] = set()
    # Extra is useful in case when user queries lot of elements in one query.
    command_history[user].add(tnow + extra)
    command_history[user] = set(filter(lambda x: x > tnow - config["rate_limit"]["time_period"], command_history[user]))
    # print(user, command_history[user])
    if len(command_history[user]) > config["rate_limit"]["max_calls"]:
        return False
    return True



## CLIENT ##


@client.event  # type: ignore
async def on_ready() -> None:
    print(f"{client.user} is connected to the following guilds:\n")
    for guild in client.guilds:
        try:
            # Update member count when bot starts up
            await update_member_count(guild)
        except:
            pass
        print(f" - {guild.name}: {guild.id}")
    # print(" - " + "\n - ".join([f"{guild.name}: {guild.id}" for guild in client.guilds]))


# I got annoyed by people using googlebad so often, so i implemented an easter egg.
# Google Bad
@slash.slash(name="googlebad", description="Find your fate of using Google Maps.", guild_ids=guild_ids)  # type: ignore
async def googlebad_command(ctx: SlashContext) -> None:
    global recent_googles
    time_now = time.time()
    recent_googles = set(filter(lambda x: x > time_now - 60, recent_googles)).union({time_now})
    if len(recent_googles) > 4 and random.random() > 0.7:
        # Alternative output is triggered at 30% chance after 5 /googlebads are used in 1 minute.
        recent_googles = set()
        await ctx.send(random.choice(ohnos).replace("…", "Whenever you use `/googlebad`,"))
    else:
        await ctx.send(random.choice(ohnos).replace("…", "Whenever you mention Google Maps,"))


# JOSM Tip
@slash.slash(name="josmtip", description="Get a JOSM tip.", guild_ids=guild_ids)  # type: ignore
async def josmtip_command(ctx: SlashContext) -> None:
    if not check_rate_limit(ctx.author_id):
        await ctx.send("You have hit the limiter.", hidden=True)
        return
    await ctx.send(random.choice(josm_tips))


# Quota query
@slash.slash(name="quota", description="Shows your spam limit.", guild_ids=guild_ids)  # type: ignore
async def quota_command(ctx: SlashContext) -> None:
    if not check_rate_limit(ctx.author_id):
        await ctx.send("You have hit the limiter.", hidden=True)
    tnow = time.time()
    msg = "\n".join(
        list(
            map(
                lambda x: f"Command available in {round(x+config["rate_limit"]["time_period"]-tnow)} sec.",
                sorted(command_history[ctx.author_id]),
            )
        )
    )
    msg += f"\nYou can still send {config["rate_limit"]["max_calls"]-len(command_history[ctx.author_id])} actions to this bot."
    await ctx.send(msg, hidden=True)


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
    if not check_rate_limit(ctx.author_id):
        await ctx.send("You have hit the limiter.", hidden=True)
        return
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
    embed.timestamp = utils.str_to_date(data["data_until"])

    # embed.set_author(name="taginfo", url=config["taginfo_url"] + "about")

    if data_wiki_en:
        embed.description = data_wiki_en["description"]

    #### Fields ####
    d = data["data"][0]
    embed.add_field(
        # This gets the emoji. Removes "s" from the end if it is there to do this.
        name=config["emoji"][d["type"] if d["type"][-1] != "s" else d["type"][:-1]] + " " + d["type"],
        value=(f"{d['count']} - {round(d['count_fraction']*100,2)}%" + (f"\n{d['values']} values" if not value else ""))
        if d["count"] > 0
        else "*None*",
        inline=False,
    )
    del data["data"][0]
    for d in data["data"]:
        embed.add_field(
            # This gets the emoji. Removes "s" from the end if it is there to do this.
            name=config["emoji"][d["type"] if d["type"][-1] != "s" else d["type"][:-1]] + " " + d["type"],
            value=(
                f"{d['count']} - {round(d['count_fraction']*100,2)}%" + (f"\n{d['values']} values" if not value else "")
            )
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
            name="elm_type",
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
            name="elm_id",
            description="ID of the element",
            option_type=4,
            required=True,
        ),
        create_option(
            name="extras",
            description="Comma seperated list of extras from `info`, `tags`, `map` and `members`.",
            option_type=3,
            required=False,
        ),
    ],
)  # type: ignore
async def elm_command(ctx: SlashContext, elm_type: str, elm_id: str, extras: str = "") -> None:
    if not check_rate_limit(ctx.author_id):
        await ctx.send("You have hit the limiter.", hidden=True)
        return
    extras_list = [e.strip() for e in extras.lower().split(",")]

    for extra in extras_list:
        if extra != "" and extra not in ["info", "tags", "members", "map"]:
            await ctx.send(
                f"Unrecognised extra `{extra}`.\nPlease choose from `info`, `tags` and `members`.", hidden=True
            )
            return

    if elm_type != "relation" and "members" in extras_list:
        await ctx.send("Cannot show `members` of non-relation element.", hidden=True)
        return

    try:
        elm = get_elm(elm_type, elm_id)
    except ValueError as error_message:
        await ctx.send(error_message, hidden=True)
        return
    files = []
    if "map" in extras_list:
        await ctx.defer()
        render_queue = await elms_to_render(elm_type, elm_id)
        check_rate_limit(ctx.author_id, extra=len(render_queue) ** config["rate_limit"]["rendering_rate_exp"])
        bbox = get_render_queue_bounds(render_queue)
        zoom, lat, lon = calc_preview_area(bbox)
        cluster, filename, errors = await get_image_cluster(lat, lon, zoom)
        cached_files.add(filename)
        cluster, filename2 = render_elms_on_cluster(cluster, render_queue, (zoom, lat, lon))
        cached_files.add(filename2)
    embed = elm_embed(elm, extras_list)
    file = None
    if "map" in extras_list:
        print("attachment://" + filename2.split("/")[-1])
        embed.set_image(url="attachment://" + filename2.split("/")[-1])
        file = File(filename2)
    await ctx.send(embed=embed, file=file)


def get_elm(elm_type: str, elm_id: str | int, suffix: str = "") -> dict:
    res = requests.get(config["api_url"] + f"api/0.6/{elm_type}/{elm_id}.json" + suffix)
    code = res.status_code
    if code == 410:
        raise ValueError(f"{elm_type.capitalize()} `{elm_id}` has been deleted.")
    elif code == 404:
        raise ValueError(f"{elm_type.capitalize()} `{elm_id}` has never existed.")
    try:
        elm = res.json()["elements"][0]
    except (json.decoder.JSONDecodeError, IndexError, KeyError):
        raise ValueError(f"{elm_type.capitalize()} `{elm_id}` was not found.")
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

    embed.timestamp = utils.str_to_date(elm["timestamp"])

    # embed.set_author(name=elm["user"], url=config["site_url"] + "user/" + elm["user"])

    embed.title = elm["type"].capitalize() + ": "
    if "tags" in elm:
        key, name = utils.get_suffixed_tag(elm["tags"], "name", ":en")
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
    # str_to_colour is not needed because PIL supports
    # both hex and string coulors just like OSM.
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
                key_languaged, value = utils.get_suffixed_tag(elm["tags"], "note", ":en")
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
            name="changeset_id",
            description="ID of the changeset",
            option_type=4,
            required=True,
        ),
        create_option(
            name="extras",
            description="Comma seperated list of extras from `info`, `tags`, `map`, `discussion`.",
            option_type=3,
            required=False,
        ),
    ],
)  # type: ignore
async def changeset_command(ctx: SlashContext, changeset_id: str, extras: str = "") -> None:
    if not check_rate_limit(ctx.author_id):
        await ctx.send("You have hit the limiter.", hidden=True)
        return
    extras_list = [e.strip() for e in extras.lower().split(",")]

    for extra in extras_list:
        if extra != "" and extra not in ["info", "tags", "map", "discussion"]:
            await ctx.send(f"Unrecognised extra `{extra}`.\nPlease choose from `info` and `tags`.", hidden=True)
            return

    try:
        changeset = get_changeset(changeset_id, "discussion" in extras)
    except ValueError as error_message:
        await ctx.send(error_message, hidden=True)
        return

    files = []
    if "map" in extras_list:
        await ctx.defer()
        render_queue = changeset["geometry"]
        check_rate_limit(ctx.author_id)
        bbox = get_render_queue_bounds(render_queue)
        zoom, lat, lon = calc_preview_area(bbox)
        cluster, filename, errors = await get_image_cluster(lat, lon, zoom)
        cached_files.add(filename)
        cluster, filename2 = render_elms_on_cluster(cluster, render_queue, (zoom, lat, lon))
        cached_files.add(filename2)
    embed = changeset_embed(changeset, extras_list)
    file = None
    if "map" in extras_list:
        print("attachment://" + filename2.split("/")[-1])
        embed.set_image(url="attachment://" + filename2.split("/")[-1])
        file = File(filename2)
    await ctx.send(embed=embed, file=file)


def get_changeset(changeset_id: str | int, discussion: bool = False) -> dict:
    """Shorthand for `get_elm("changeset", changeset_id)`"""
    try:
        discussion_suffix = ""
        if discussion:
            discussion_suffix = "?include_discussion=true"
        changeset = get_elm("changeset", changeset_id, discussion_suffix)
        changeset["geometry"] = [
            [
                (changeset["minlat"], changeset["minlon"]),
                (changeset["minlat"], changeset["maxlon"]),
                (changeset["maxlat"], changeset["maxlon"]),
                (changeset["maxlat"], changeset["minlon"]),
                (changeset["minlat"], changeset["minlon"]),
            ]
        ]
        return changeset
    except ValueError as error_message:
        raise ValueError(error_message)


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

    embed.timestamp = utils.str_to_date(changeset["closed_at"])

    embed.set_author(name=changeset["user"], url=config["site_url"] + "user/" + quote(changeset["user"]))

    embed.title = f"Changeset: {changeset['id']}"

    #### Description ####
    embed.description = ""

    if "tags" in changeset and "comment" in changeset["tags"]:
        embed.description += "> " + changeset["tags"]["comment"].strip().replace("\n", "\n> ") + "\n\n"
        changeset["tags"].pop("comment")
    else:
        embed.description += "*(no comment)*\n\n"

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
    # ?include_discussion=true
    if "discussion" in extras:
        # Example: *- User opened on 2020-04-14 08:00*
        embed.description += utils.format_discussions(changeset["discussion"])
    if len(embed.description) > 1980:
        embed.description = embed.description[:1970].strip() + "…\n\n"
    embed.description += f"[OSMCha](https://osmcha.org/changesets/{changeset['id']})"
    return embed


### Notes ###
# Notes support was added based on changeset
@slash.slash(
    name="note",
    description="Show details about a note.",
    guild_ids=guild_ids,
    options=[
        create_option(
            name="note_id",
            description="ID of the note",
            option_type=4,
            required=True,
        ),
        create_option(
            name="extras",
            description="Comma seperated list of extras from `info`, `discussion`.",
            option_type=3,
            required=False,
        ),
    ],
)  # type: ignore
async def note_command(ctx: SlashContext, note_id: str, extras: str = "") -> None:
    if not check_rate_limit(ctx.author_id):
        await ctx.send("You have hit the limiter.", hidden=True)
        return
    extras_list = [e.strip() for e in extras.lower().split(",")]

    for extra in extras_list:
        if extra != "" and extra not in ["info", "discussion"]:
            await ctx.send(f"Unrecognised extra `{extra}`.\nPlease choose from `info`.", hidden=True)
            return

    try:
        note = get_note(note_id)
    except ValueError as error_message:
        await ctx.send(error_message, hidden=True)
        return

    await ctx.defer()
    await ctx.send(embed=note_embed(note, extras_list))


def get_note(note_id: str | int) -> dict:
    """Shorthand for get_elm didn't work"""
    res = requests.get(config["api_url"] + f"api/0.6/notes/{note_id}.json")
    try:
        elm = res.json()
    except (json.decoder.JSONDecodeError, IndexError, KeyError):
        raise ValueError(f"Note `{note_id}` does not exist.")
    return elm


def note_embed(note: dict, extras: Iterable[str] = []) -> Embed:
    embed = Embed()
    embed.type = "rich"
    embed.url = config["site_url"] + "note/" + str(note["properties"]["id"])
    embed.set_footer(
        text=config["copyright_notice"],
        icon_url=config["icon_url"],
    )
    # API returns very different result for notes

    if note["properties"]["status"] == "closed":
        closed = True
        embed.set_thumbnail(url=config["symbols"]["note_solved"])
    else:
        closed = False
        embed.set_thumbnail(url=config["symbols"]["note_open"])
    embed.timestamp = utils.str_to_date(note["properties"]["date_created"].replace(" ", "T")[:19] + "Z")
    if "user" in note["properties"]["comments"][0]:
        creator = note["properties"]["comments"][0]["user"]
        embed.set_author(name=creator, url=note["properties"]["comments"][0]["user_url"])
    else:
        creator = "*Anonymous*"
        embed.set_author(name=creator)

    embed.title = f"Note: {note['properties']['id']}"

    #### Description ####
    embed.description = ""
    if "comments" in note["properties"] and len(note["properties"]) > 0:
        embed.description += "> " + note["properties"]["comments"][0]["text"].strip().replace("\n", "\n> ") + "\n\n"
        note["properties"]["comments"].pop(0)
    else:
        embed.description += "*(no comment)*\n\n"

    #### Image ####
    # * This would create significant stress to the OSM servers, so I don't reccomend it.
    # ! This doesn't work due to the OSM servers having some form of token check.
    # embed.set_image(url=img_url)
    # Easiest way to handle note rendering is to just draw on map.

    #### Fields ####
    if "info" in extras:
        embed.add_field(name="Comments", value=str(len(note["properties"]["comments"])))
        embed.add_field(name="Created", value=note["properties"]["date_created"])
        if ["closed_at"] in note["properties"]["closed_at"]:
            embed.add_field(name="Closed", value=note["properties"]["closed_at"])

    if "discussion" in extras:
        # Example: *- User opened on 2020-04-14 08:00*
        embed.description += utils.format_discussions(note["properties"]["comments"])
    if creator != "*Anonymous*":
        embed.description += f"[Other notes by {creator}.](https://www.openstreetmap.org/user/{creator}/notes)"
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
    if not check_rate_limit(ctx.author_id):
        await ctx.send("You have hit the limiter.", hidden=True)
        return
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
    except ValueError as error_message:
        await ctx.send(error_message, hidden=True)
        return

    await ctx.defer()
    await ctx.send(embed=user_embed(user, extras_list))


def get_id_from_username(username: str) -> int:
    whosthat = requests.get(config["whosthat_url"] + "whosthat.php?action=names&q=" + username).json()
    if len(whosthat) > 0:
        return whosthat[0]["id"]
    # Backup solution via changesets
    res = requests.get(config["api_url"] + f"api/0.6/changesets/?display_name={username}").text
    if res == "Object not found":
        raise ValueError(f"User `{username}` does not exist.")
    if "uid=" in res:
        # +5 and -2 are used to isolate uid from `uid="123" `.
        return res[res.find('uid="') + 5 : res.find('user="') - 2]
    # Backup of a backup by using notes lookup.
    res = requests.get(config["api_url"] + f"api/0.6/notes/search.json/?display_name={username}").json()
    for feat in res["features"]:
        for comm in feat["properties"]["comments"]:
            try:
                if comm["user"] == username:
                    return str(comm["uid"])
            except KeyError:
                pass  # Encountered anonymous note
    raise ValueError(f"User `{username}` does exist, but has no changesets nor notes.")


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
    # embed.timestamp = utils.str_to_date(user["account_created"])

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
            name="url",
            description="URL that ends in a fragment, or just the fragment. e.g. `#map=19/33.45169/126.48982`",
            option_type=3,
            required=True,
        )
    ],
)  # type: ignore
async def showmap_command(ctx: SlashContext, url: str) -> None:
    if not check_rate_limit(ctx.author_id):
        await ctx.send("You have hit the limiter.", hidden=True)
        return
    try:
        zoom_int, lat_deg, lon_deg = frag_to_bits(url)
    except ValueError:
        await ctx.send("Invalid map fragment. Expected to be in format `#map=zoom/lat/lon`", hidden=True)
        return

    # * Discord has a weird limitation where you can't send an attachment (image) in the first slash command respose.
    first_msg = await ctx.send("Getting image…")
    with ctx.channel.typing():

        image_file, filename, errorlog = await get_image_cluster(lat_deg, lon_deg, zoom_int)

        # TODO: I probabbly need to get some better injection protection at some point.
        # This works though so eh ¯\_(ツ)_/¯
        msg = f"<{config['site_url']}#map={zoom_int}/{lat_deg}/{lon_deg}>"

        img_msg = await ctx.channel.send(msg, file=File(filename))

    await first_msg.edit(content=f'Getting image… Done[!](<{utils.msg_to_link(img_msg)}> "Link to message with image") :map:')


async def elms_to_render(
    elem_type,
    elem_id,
    no_reduction=False,
    get_bbox=False,
    recursion_depth=0,
    status_msg: Message | None = None,
):
    # Inputs:   elem_type (node / way / relation)
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
    # I have currently odd bug that when get_bbox is fixed to True, all following queries also have bbox.

    get_center = False
    if elem_type != "relation":
        get_bbox = False
    elif 1 < recursion_depth:
        get_center = True
    if get_bbox:
        output_type = "bb"
    elif get_center:
        output_type = "center"
    else:
        output_type = "skel geom"  # Original version
    Q = "[out:json][timeout:45];" + elem_type + "(id:" + str(elem_id) + ");out " + output_type + ";"
    if status_msg:
        await status_msg.edit(
            content=f"{LOADING_EMOJI} Querying `" + Q + "`"
        )  # I hope this works. uncomment on live instance
    # Above line may introduce error when running it from /element, not on_message.
    try:
        result = overpass_api.query(Q)
    except exception.OverpassRuntimeError:
        print("Overpass timeout")
        if not get_bbox:
            # recursion_depth is not increased, because this is retry of same element
            return await elms_to_render(elem_type, elem_id, no_reduction, True, recursion_depth, status_msg=status_msg)
        else:
            Q = Q.replace("bb;", "skel center;")
            get_center = True
            if status_msg:
                await status_msg.edit(content=f"{LOADING_EMOJI} Querying `" + Q + "`")
            result = overpass_api.query(Q)
    # return result
    # Since we are querying for single element, top level result will have just 1 element.
    node_count = 0
    # Combining all queries together is much faster
    # Let's say that maximum recursion depth can be 2 levels (EU > Belgium > Counties; Sofia network > Bus line > Bus stops)
    if get_center:
        if "center" in result.relations[0].attributes:
            center = result.relations[0].attributes["center"]
            return [[(float(center["lat"]), float(center["lon"]))]]
    elif get_bbox:
        if "bounds" in result.relations[0].attributes:
            bound = result.relations[0].attributes["bounds"]
            # {'minlat': Decimal('59.4'), 'minlon': Decimal('24.6'), 'maxlat': Decimal('59.5'), 'maxlon': Decimal('24.7')
            return [
                [
                    (float(bound["minlat"]), float(bound["minlon"])),
                    (float(bound["minlat"]), float(bound["maxlon"])),
                    (float(bound["maxlat"]), float(bound["maxlon"])),
                    (float(bound["maxlat"]), float(bound["minlon"])),
                    (float(bound["minlat"]), float(bound["minlon"])),
                ]
            ]
    if elem_type == "relation":
        segments = []
        elems = result.relations[0].members
        prev_last = None
        for i in range(len(elems)):
            # Previously it skipped elements based on role, but it was buggy.
            # New, recursive approach.
            if type(elems[i]) == overpy.RelationRelation:
                seg = await elms_to_render(
                    "relation", elems[i].ref, True, get_bbox, recursion_depth + 1, status_msg=status_msg
                )
                segments += seg
            elif type(elems[i]) == overpy.RelationNode:  # Single node as member of relation
                segments.append([(float(elems[i].attributes["lat"]), float(elems[i].attributes["lon"]))])
            elif type(elems[i]) == overpy.RelationWay:
                geom = elems[i].geometry
                segments.append(list(map(lambda x: (float(x.lat), float(x.lon)), geom)))
    elif elem_type == "way":
        elems = result.ways[0]
        segments = [
            list(map(lambda x: (float(x.lat), float(x.lon)), elems.get_nodes(True)))
        ]  # True means resolving node references.
    elif elem_type == "node":
        # Creates simply a single-node segment.
        segments = [[(float(result.nodes[0].lat), float(result.nodes[0].lon))]]
    else:  # If encountered unknown element type.
        return []
    if no_reduction:
        return segments
    # segments=merge_segments(segments)
    segments = reduce_segment_nodes(segments)
    # We now have list of lists of (lat, lon) coordinates to be rendered.
    # These lists of segments can be joined, if multiple elements are requested
    # In order to add support for colours, just create segment-colour pairs.
    return segments


def merge_segments(segments: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    # Other bug occurs in case some ways of relation are reversed.
    # Ideally, this should merge two segments, if they share same end and beginning node.
    # Merges some ways together. For russia, around 4000 ways became 34 segments.

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
    calc_limit = (
        lambda x: x if x < Limiter_offset else int((x - Limiter_offset) ** (1 / Reduction_factor) + Limiter_offset)
    )
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


def get_render_queue_bounds(
    segments: list[list[tuple[float, float]]], notes: list[tuple[float, float, bool]] = []
) -> tuple[float, float, float, float]:
    # Finds bounding box of rendering queue (segments)
    # Rendering queue is bunch of coordinates that was calculated in previous function.
    min_lat, max_lat, min_lon, max_lon = 90.0, -90.0, 180.0, -180.0
    precision = 5  # https://xkcd.com/2170/
    for segment in segments:
        for coordinates in segment:
            lat, lon = coordinates
            # int() because type checker is an idiot
            # Switching it to int kills the whole renderer!
            if lat > max_lat:
                max_lat = round(lat, precision)
            if lat < min_lat:
                min_lat = round(lat, precision)
            if lon > max_lon:
                max_lon = round(lon, precision)
            if lon < min_lon:
                min_lon = round(lon, precision)
    for note in notes:
        lat, lon, solved = note
        # int() because type checker is an idiot
        # Switching it to int kills the whole renderer!
        if lat > max_lat:
            max_lat = round(lat, precision)
        if lat < min_lat:
            min_lat = round(lat, precision)
        if lon > max_lon:
            max_lon = round(lon, precision)
        if lon < min_lon:
            min_lon = round(lon, precision)
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
    # I think this function causes issues with incorrect rendering due to using average of boundaries, not tiles.
    print("Elements bounding box:",*list(map(lambda x: round(x, 4), queue_bounds)))
    min_lat, max_lat, min_lon, max_lon = queue_bounds
    delta_lat = max_lat - min_lat
    delta_lon = max_lon - min_lon
    zoom_x = int(math.log2((360 / delta_lon) * (config["rendering"]["tiles_x"] - 2 * config["rendering"]["tile_margin_x"])))
    center_lon = delta_lon / 2 + min_lon
    zoom_y = config["rendering"]["max_zoom"] + 1  # Zoom level is determined by trying to fit x/y bounds into 5 tiles.
    while (utils.deg2tile(min_lat, 0, zoom_y)[1] - utils.deg2tile(max_lat, 0, zoom_y)[1] + 1) > config["rendering"]["tiles_y"] - 2 * config["rendering"]["tile_margin_y"]:
        zoom_y -= 1  # Bit slow and dumb approach
    zoom = min(zoom_x, zoom_y, config["rendering"]["max_zoom"])
    tile_y_min = utils.deg2tile_float(max_lat, 0, zoom)[1]
    tile_y_max = utils.deg2tile_float(min_lat, 0, zoom)[1]
    print(zoom, center_lon)
    if zoom < 10:
        # At low zoom levels and high latitudes, mercator's distortion must be accounted
        center_lat = round(utils.tile2deg(zoom, 0, (tile_y_max + tile_y_min) / 2)[0], 5)
    else:
        center_lat = (max_lat - min_lat) / 2 + min_lat
    print(center_lat, min_lat, max_lat)
    return (zoom, center_lat, center_lon)


def get_image_tile_range(lat_deg: float, lon_deg: float, zoom: int) -> tuple[int, int, int, int, tuple[float, float]]:
    # Following line is duplicataed at calc_preview_area()
    center_x, center_y = utils.deg2tile_float(lat_deg, lon_deg, zoom)
    xmin, xmax = int(center_x - config["rendering"]["tiles_x"] / 2), int(center_x + config["rendering"]["tiles_x"] / 2)
    n = 2 ** zoom  # N is number of tiles in one direction on zoom level
    if config["rendering"]["tiles_x"] % 2 == 0:
        xmax -= 1
    ymin, ymax = int(center_y - config["rendering"]["tiles_y"] / 2), int(center_y + config["rendering"]["tiles_y"] / 2)
    if config["rendering"]["tiles_y"] % 2 == 0:
        ymax -= 1
    ymin = max(ymin, 0)  # Sets vertical limits to area.
    ymax = min(ymax, n)
    # tile_offset - By how many tiles should tile grid shifted somewhere (up left?).
    print("Tile offset calculation")
    print(center_x, config["rendering"]["tiles_x"], config["rendering"]["tiles_x"] % 2, (config["rendering"]["tiles_x"] % 2) / 2, (center_x + (config["rendering"]["tiles_x"] % 2) / 2))
    tile_offset = ((center_x + (config["rendering"]["tiles_x"] % 2) / 2) % 1, (center_y + (config["rendering"]["tiles_x"] % 2) / 2) % 1)
    # tile_offset = 0,0
    print("Offset:", tile_offset)
    return xmin, xmax - 1, ymin, ymax - 1, tile_offset


async def _get_image_cluster__get_image(
    session: aiohttp.ClientSession,
    cluster: Image,
    zoom: int,
    tile_url: str,
    xtile: int,
    ytile: int,
    xtile_corrected: int,
    tile_range: tuple,
) -> None | tuple[str, str, Exception]:
    url = tile_url.format(zoom=zoom, x=xtile_corrected, y=ytile)
    # print(f"Requesting: {url}")
    try:
        res = await session.get(url, headers=config["rendering"]["HEADERS"])
        data = await res.content.read()
        cluster.paste(
            Image.open(BytesIO(data)),
            utils.tile2pixel((xtile, ytile), zoom, tile_range),
        )
        return None
    except Exception as e:
        print(e)
        return ("map tile", url, e)


async def get_image_cluster(
    lat_deg: float, lon_deg: float, zoom: int, tile_url: str = config["tile_url"]
) -> tuple[Any, str, list[tuple[str, str, Exception]]]:
    # Rewrite of https://github.com/ForgottenHero/mr-maps
    # Following line is duplicataed at calc_preview_area()
    n: int = 2 ** zoom  # N is number of tiles in one direction on zoom level

    # tile_offset - By how many tiles should tile grid shifted somewhere.
    # xmin, xmax, ymin, ymax, tile_offset
    tile_range = get_image_tile_range(lat_deg, lon_deg, zoom)
    xmin, xmax, ymin, ymax, tile_offset = tile_range

    errorlog = []
    cluster = Image.new("RGB", (config["rendering"]["tiles_x"] * config["rendering"]["tile_w"] - 1, config["rendering"]["tiles_y"] * config["rendering"]["tile_h"] - 1))

    t = time.time()
    async with aiohttp.ClientSession() as session:
        tasks = []
        for xtile in range(xmin - 1, xmax + 2):
            # print(xtile, xtile % n)
            xtile_corrected = xtile % n  # Repeats tiles across -180/180 meridian.
            # Xtile is preserved, because it's used for plotting it on map
            for ytile in range(ymin, min([ymax + 2, n])):
                tasks.append(
                    _get_image_cluster__get_image(
                        session,
                        cluster,
                        zoom,
                        tile_url,
                        xtile,
                        ytile,
                        xtile_corrected,
                        tile_range,
                    )
                )
        errors = await asyncio.gather(*tasks, return_exceptions=True)

        for err in errors:
            if err is not None:
                errorlog.append(err)

    print(f"Download + paste: {round(time.time()-t, 1)}s")
    filename: str = config["map_save_file"].format(t=time.time())
    cluster.save(filename)
    return cluster, filename, errorlog


def draw_line(segment: list[tuple[float, float]], draw, colour="red") -> None:
    # https://stackoverflow.com/questions/59060887
    # This is polyline of all coordinates on array.
    draw.line(segment, fill=colour, width=4)


def draw_node(coord: tuple[float, float], draw, colour="red") -> None:
    # https://stackoverflow.com/questions/2980366
    r = 5
    x, y = coord
    leftUpPoint = (x - r, y - r)
    rightDownPoint = (x + r, y + r)
    twoPointList = [leftUpPoint, rightDownPoint]
    draw.ellipse(twoPointList, fill=colour)


def render_notes_on_cluster(Cluster, notes: list[tuple[float, float, bool]], frag: tuple[int, float, float], filename):
    # tile_offset - By how many tiles should tile grid shifted somewhere.
    tile_range = get_image_tile_range(frag[1], frag[2], frag[0])
    errorlog = []
    for note in notes:
        # TODO: Unify coordinate conversion functions.
        coord = utils.wgs2pixel(note, tile_range, frag)
        # print(coord)
        if note[2]:  # If note is closed
            note_icon = closed_note_icon
            icon_pos = (int(coord[0] - closed_note_icon_size[0] / 2), int(coord[1] - closed_note_icon_size[1]))
        else:
            note_icon = open_note_icon
            icon_pos = (int(coord[0] - open_note_icon_size[0] / 2), int(coord[1] - open_note_icon_size[1]))
        # https://stackoverflow.com/questions/5324647
        # print(icon_pos)
        Cluster.paste(note_icon, icon_pos, note_icon)
        del note_icon
    Cluster.save(filename)
    return Cluster, filename


def render_elms_on_cluster(Cluster, render_queue: list[list[tuple[float, float]]], frag: tuple[int, float, float]):
    # Inputs:   Cluster - PIL image
    #           render_queue - [[(lat, lon), ...], ...]
    #           frag  - zoom, lat, lon used  for cluster rendering input.
    # Renderer requires epsg 3587 crs converter. Implemented in utils.deg2tile_float.
    # Use solution similar to get_image_cluster, but use deg2tile_float function to get xtile/ytile.
    # I think tile calculation should be separate from get_image_cluster.
    # tile_offset - By how many tiles should tile grid shifted somewhere.
    # tile_range = xmin, xmax, ymin, ymax, tile_offset
    tile_range = get_image_tile_range(frag[1], frag[2], frag[0])
    # Convert geographical coordinates to X-Y coordinates to be used on map.
    draw = ImageDraw.Draw(Cluster)  # Not sure what it does, just following https://stackoverflow.com/questions/59060887
    # Basic demo for colour picker.
    len_colors = len(element_colors)
    for seg_num in range(len(render_queue)):
        for i in range(len(render_queue[seg_num])):
            render_queue[seg_num][i] = utils.wgs2pixel(render_queue[seg_num][i], tile_range, frag)
        # Draw segment onto image
        color = element_colors[seg_num % len_colors]
        draw_line(render_queue[seg_num], draw, color)
        # Maybe nodes shouldn't be rendered, if way has many, let's say 80+ nodes,
        # because it would become too cluttered?  This is very indecisive function.
        draw_nodes = False
        if len(render_queue[seg_num]) < 80:
            draw_nodes = True
        if len(render_queue) > 40:
            draw_nodes = False
        if len(render_queue[seg_num]) == 1:
            draw_nodes = True
        if draw_nodes:
            draw_node(render_queue[seg_num][0], draw, color)
            if len(render_queue[seg_num]) > 1:
                for node_num in range(1, len(render_queue[seg_num])):
                    draw_node(render_queue[seg_num][node_num], draw, color)
    filename = config["map_save_file"].format(t=time.time())
    if True:
        draw_node((640.0, 640.0), draw, "#088")
        coord = utils.wgs2pixel((frag[1], frag[2]), tile_range, frag)
        print("Map alignment error: ", coord[0] - 640, coord[1] - 640)
        draw_node(coord, draw, "#bb0")
        print(640, 640, " ", *coord)
    print(f"Saved drawn image as {filename}.")
    Cluster.save(filename)
    return Cluster, filename
    # I barely know how to draw lines in PIL


element_action_row = manage_components.create_actionrow(
    manage_components.create_button(
        style=ButtonStyle.blue, emoji=INSPECT_EMOJI, label="Element info", custom_id="elm_embed"
    ),
    manage_components.create_button(
        style=ButtonStyle.blue, emoji=IMAGE_EMOJI, label="Element image", custom_id="elm_image"
    ),
    manage_components.create_button(style=ButtonStyle.blue, label="Both", custom_id="elm_both"),
    manage_components.create_button(style=ButtonStyle.red, label=CANCEL_SYMBOL, custom_id="delete"),
)


async def ask_render_confirmation(msg: Message) -> tuple[bool, bool]:
    "Message → add_image, add_embed"
    actions = element_action_row.copy()
    action_msg = await msg.reply(content="Element controls:", components=[actions])

    while True:
        try:
            btn_ctx: ComponentContext = await manage_components.wait_for_component(
                client, messages=action_msg, components=actions, timeout=15
            )
        except asyncio.TimeoutError:  # User didn't respond
            await action_msg.delete()
            return False, False
        else:  # User responded
            if btn_ctx.author != msg.author and not is_powerful(btn_ctx.author, btn_ctx.guild):
                await btn_ctx.send("Only the message author, or helpers, can control the menu.", hidden=True)
                continue

            if btn_ctx.custom_id == "delete":
                try:
                    await action_msg.delete()
                except discord.errors.NotFound:
                    pass  # The global delete callback below already caught it
                    # Note that the global callback only works for powerfuls/helpers, so this must be here.
                return False, False

            elif btn_ctx.custom_id == "elm_embed":
                await action_msg.delete()
                return False, True
            elif btn_ctx.custom_id == "elm_image":
                await action_msg.delete()
                return True, False
            elif btn_ctx.custom_id == "elm_both":
                await action_msg.delete()
                return True, True


@client.event  # type: ignore
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    # Allows you to delete a message by reacting with 🗑️ if it's a reply to you.
    if payload.emoji.name != DELETE_EMOJI:
        return
    if payload.channel_id == config["server_settings"][str(payload.guild_id)]["suggestion_channel"]:
        # Don't allow deleting suggestions
        return
    # Fetch message is rather slow operation, that's why it only takes place if user reacts with wastebasket
    msg = await client.get_channel(payload.channel_id).fetch_message(payload.message_id)
    if msg.author == client.user:  # Ensure message was created by the bot
        # Powerful users can delete anything
        if is_powerful(payload.member, client.get_guild(payload.guild_id)):
            print(f"{payload.user_id} deleted following message:\n```{msg.content}```")
            await msg.delete()

            # msg.reference.fail_if_not_exists dosen't appear to work correctly.
            # // if msg.reference and not msg.reference.fail_if_not_exists:  # If is a reply & refernced message still exists
            # if msg.reference:  # If is a reply
            #     ref_msg = (
            #         msg.reference.resolved
            #         if isinstance(msg.reference.resolved, Message)
            #         else await msg.channel.fetch_message(msg.reference.message_id)
            #     )
            #     if ref_msg.author == payload.member:
            #         print(2)
            #         await msg.delete()


@client.event  # type: ignore
async def on_message(msg: Message) -> None:
    global cached_files

    if msg.author == client.user:
        return

    #### Try my commands, those are gone ####
    if msg.content.startswith("?josmtip"):
        await msg.channel.send("Try `/josmtip` :thinking:")
    elif msg.content.startswith("?googlebad"):
        await msg.channel.send("Try `/googlebad` :wink:")
    elif msg.content.startswith("€showmap"):
        await msg.channel.send("Try `/showmap` :map:")
    msg_arrived = time.time()

    #### "use potlatch" → sirens 🚨 ####
    if regexes.POTLATCH.findall(msg.clean_content):
        await msg.add_reaction(config["emoji"]["sirens"])
        await msg.add_reaction(config["emoji"]["potlatch"])

    #### Inline linking ####
    # Find matches
    # elm[0] - element type (node/way/relation/changeset)
    # elm[1] - separator used
    # elm[2] - element ID
    elms = [
        (elm[0].lower(), tuple(regexes.INTEGER.findall(elm[2])), elm[1])
        for elm in regexes.ELM_INLINE.findall(msg.clean_content)
    ]
    changesets = [
        (elm[0].lower(), tuple(regexes.INTEGER.findall(elm[2])), elm[1])
        for elm in regexes.CHANGESET_INLINE.findall(msg.clean_content)
    ]
    notes = [
        (elm[0].lower(), tuple(regexes.INTEGER.findall(elm[2])), elm[1])
        for elm in regexes.NOTE_INLINE.findall(msg.clean_content)
    ]
    users = [thing.split("/")[1] for thing in regexes.USER_INLINE.findall(msg.clean_content)]
    map_frags = regexes.MAP_FRAGMENT_INLINE.findall(msg.clean_content)

    queried_elements_count = len(elms) + len(changesets) + len(users) + len(map_frags) + len(notes)
    author_id = msg.author.id
    check_rate_limit(author_id, -config["rate_limit"]["time_period"] - 1)  # Refresh command history
    if queried_elements_count == 0:
        return
    elif queried_elements_count > config["rate_limit"]["max_elements"] - len(command_history[author_id]):
        # If there are too many elements, just ignore.
        return

    ask_confirmation = False
    # for match in elms + changesets + notes:
    #    if match[2] != "/" or len(match[1]) > 1:  # Found case when user didn't use standard node/123 format
    #        ask_confirmation = True
    if len(elms + notes + changesets) != 0:
        ask_confirmation = True
    add_embedded = True
    wait_for_user_start = time.time()
    if ask_confirmation:
        add_image, add_embedded = await ask_render_confirmation(msg)
        print(add_image)
    wait_for_user_end = time.time()
    render_queue: list[list[tuple[float, float]]] = []
    # User quota is checked after they confirmed element lookup.
    for i in range(int(queried_elements_count ** config["rate_limit"]["element_count_exp"]) + 1):
        # Allows querying up to 10 elements at same time, delayed for up to 130 sec
        rating = check_rate_limit(author_id, round(i ** config["rate_limit"]["rate_extra_exp"], 2))
        # if not rating:
        #     return
    async with msg.channel.typing():
        # Create the messages
        status_msg = await msg.channel.send(
            f"{LOADING_EMOJI} This is status message, that will show progress of your request."
        )
        embeds: list[Embed] = []
        files: list[File] = []
        errorlog = []

        for elm_type, elm_ids, separator in elms:
            for elm_id in elm_ids:
                await status_msg.edit(content=f"{LOADING_EMOJI} Processing {elm_type}/{elm_id}.")
                try:
                    if add_embedded:
                        embeds.append(elm_embed(get_elm(elm_type, elm_id)))
                    if add_image:
                        render_queue += await elms_to_render(elm_type, elm_id, status_msg=status_msg)
                except ValueError as error_message:
                    errorlog.append((elm_type, elm_id, error_message))

        for elm_type, changeset_ids, separator in changesets:
            # changeset_ids = (<tuple: list of changesets>, <str: separator used>)
            for changeset_id in changeset_ids:
                await status_msg.edit(content=f"{LOADING_EMOJI} Processing {elm_type}/{changeset_id}.")
                try:
                    changeset = get_changeset(changeset_id)
                    if add_embedded:
                        embeds.append(changeset_embed(changeset))
                    if add_image:
                        render_queue += changeset["geometry"]
                except ValueError as error_message:
                    errorlog.append((elm_type, changeset_id, error_message))

        notes_render_queue = []
        for elm_type, note_ids, separator in notes:
            # note_ids = (<tuple: list of notes>, <str: separator used>)
            for note_id in note_ids:
                await status_msg.edit(content=f"{LOADING_EMOJI} Processing {elm_type}/{note_id}.")
                try:
                    note = get_note(note_id)
                    if add_embedded:
                        embeds.append(note_embed(note))
                    if add_image:
                        notes_render_queue.append(
                            (
                                note["geometry"]["coordinates"][1],
                                note["geometry"]["coordinates"][0],
                                note["properties"]["status"] == "closed",
                            )
                        )
                except ValueError as error_message:
                    errorlog.append((elm_type, note_id, error_message))
        time_spent = round(time.time() - msg_arrived - (wait_for_user_end - wait_for_user_start), 3)
        if time_spent > 15:
            # Most direct way to assess difficulty of user's request.
            check_rate_limit(author_id, time_spent)
        print(f"Script spent {time_spent} sec on downloading elements.")
        msg_arrived = time.time()
        if render_queue or notes_render_queue:
            # Add extra to quota for querying large relations
            check_rate_limit(author_id, extra=(len(render_queue) + len(notes_render_queue)) ** config["rate_limit"]["rendering_rate_exp"])
            # Next step is to calculate map area for render.
            await status_msg.edit(content=f"{LOADING_EMOJI} Downloading map tiles")
            bbox = get_render_queue_bounds(render_queue, notes_render_queue)
            zoom, lat, lon = calc_preview_area(bbox)
            if notes_render_queue:
                zoom = min([zoom, config["rendering"]["max_note_zoom"]])
            print(zoom, lat, lon, sep="/")
            cluster, filename, errors = await get_image_cluster(lat, lon, zoom)
            cached_files.add(filename)
            errorlog += errors

            # Start drawing elements on image.
            if render_queue:
                await status_msg.edit(content=f"{LOADING_EMOJI} Rendering elements to map.")
                cluster, filename2 = render_elms_on_cluster(cluster, render_queue, (zoom, lat, lon))
                cached_files.add(filename2)
            else:
                filename2 = filename
            if notes_render_queue:
                await status_msg.edit(content=f"{LOADING_EMOJI} Rendering notes to map.")
                for note in notes_render_queue:
                    cluster, filename2 = render_notes_on_cluster(
                        cluster, notes_render_queue, (zoom, lat, lon), filename2
                    )
                cached_files.add(filename2)
            files.append(File(filename2))

        for username in users:
            await status_msg.edit(content=f"{LOADING_EMOJI} Processing user/{username}.")
            try:
                embeds.append(user_embed(get_user(get_id_from_username(username))))
            except ValueError as error_message:
                errorlog.append(("user", username, error_message))

        for map_frag in map_frags:
            await status_msg.edit(content=f"{LOADING_EMOJI} Processing {map_frag}.")
            zoom, lat, lon = utils.frag_to_bits(map_frag)
            cluster, filename, errors = await get_image_cluster(lat, lon, zoom)
            errorlog += errors
            files.append(File(filename))
            cached_files.add(filename)
        await status_msg.edit(content=f"{LOADING_EMOJI} Starting upload")
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
        await status_msg.delete()

        if len(errorlog) > 0:
            for element_type, element_id, error_message in errorlog[:5]:
                errmsg = f"Error occurred while processing {element_type}/{element_id}.\n{error_message}".strip()
                # if element_type == "user":
                #     errmsg += "\nEither the user dosen't exist, or is too new to be detected by the bot."
                await msg.channel.send(errmsg)
            if len(errorlog) > 5:
                await msg.channel.send(f"{len(errorlog) - 5} more errors occurred.")

        time_spent = round(time.time() - msg_arrived, 3)
        # msg_arrived actually means time since start of rendering
        if time_spent > 10:
            # Most direct way to assess difficulty of user's request.
            check_rate_limit(author_id, time_spent)
        print(f"Script spent {time_spent} sec on preparing output (render, embeds, files, errors).")

    # Clean up files
    for filename in cached_files:
        os.remove(filename)
    cached_files = set()


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
            name="suggestion",
            description="Your suggestion, be sensible.",
            option_type=3,
            required=True,
        )
    ],
)  # type: ignore
async def suggest_command(ctx: SlashContext, suggestion: str) -> None:
    if not check_rate_limit(ctx.author_id):
        await ctx.send("You have hit the limiter.", hidden=True)
        return
    if not config["server_settings"][str(ctx.guild.id)]["suggestions_enabled"]:
        await ctx.send("Suggestions are not enabled on this server.", hidden=True)
        return

    await ctx.defer(hidden=True)

    suggestion_chanel = client.get_channel(config["server_settings"][str(ctx.guild.id)]["suggestion_channel"])

    suggestion = utils.sanitise(suggestion).replace("\n", "\n> ")

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
        + utils.msg_to_link(sugg_msg),
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
            name="msg_id",
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
    if not check_rate_limit(ctx.author_id):
        await ctx.send("You have hit the limiter.", hidden=True)
        return
    if not config["server_settings"][str(ctx.guild.id)]["suggestions_enabled"]:
        await ctx.send("Suggestions are not enabled on this server.", hidden=True)
        return

    if not is_powerful(ctx.author, ctx.guild):
        await ctx.send("You do not have permission to run this command.", hidden=True)
        return

    await ctx.defer(hidden=True)

    suggestion_chanel = client.get_channel(config["server_settings"][str(ctx.guild.id)]["suggestion_channel"])

    try:
        msg: Message = await suggestion_chanel.fetch_message(msg_id)
    except discord.errors.NotFound:
        await ctx.send("Message not found. Likely an incorrect ID or it is not in the suggestion channel.", hidden=True)
        return

    if msg.author.id != client.user.id:
        await ctx.send("I can't modify that message, as it was not created by me :P", hidden=True)
        return

    votes = {
        "yes": 0,
        "abstain": 0,
        "no": 0,
    }
    for reaction in msg.reactions:
        # Custon emojis are in a format like <:vote_no:845705089222049792>
        # Real emoji just give the Unicode emoji, therefore we have to do this:
        r = str(reaction)
        if ":" in r:
            r = r.split(":")[1].removeprefix("vote_")

        # Doing an if for += or = because it's possible to have custom emoji with the same name on different servers.
        if r in votes:
            # reaction.me is True if the bot added the reaction, so subting it means we don't count the bot as voting.
            votes[r] += reaction.count - reaction.me
        else:
            votes[r] = reaction.count - reaction.me

    sugg_msg = await msg.edit(
        content=msg.content.split("\n\n")[0]
        + f"\n\n__**Voting closed**__ by {utils.user_to_mention(ctx.author)}.\n"
        + f"Result: **{utils.sanitise(result)}**\n"
        + f"Voting closed with: {votes['yes']} {config['emoji']['vote_yes']}"
        + f", {votes['abstain']} {config['emoji']['vote_abstain']}"
        + f", {votes['no']} {config['emoji']['vote_no']}"
        + (f", {votes['wat']} :wat:" if "wat" in votes else "")
        + (f", {votes['🫖']} 🫖" if "🫖" in votes else "")
    )
    # Extra brackets above are to stop weird auto-formatting.

    await ctx.send(
        f"Closed suggestion with result '{result}'.\nYou can re-run this command to change the result.\n{utils.msg_to_link(msg)}",
        hidden=True,
    )


help_embeds: list[Embed] = []

# region HELP
with open("HELP.md", "r") as file:
    for page in file.read().split("\n# "):
        title, image, body = page.split("\n", 2)
        title = title.removeprefix("# ")  # split() dosen't remove it for the first one.
        embed = Embed(
            type="rich",
            title=title,
            image=image,
            description=body,
        )
        help_embeds.append(embed)
    for i in range(len(help_embeds)):
        help_embeds[i].set_footer(
            text=f"Page {i+1}/{len(help_embeds)}",
            icon_url=config["icon_url"],
        )

help_action_row = manage_components.create_actionrow(
    manage_components.create_button(style=ButtonStyle.blue, label=LEFT_SYMBOL, custom_id="help_left"),
    manage_components.create_button(style=ButtonStyle.blue, label=RIGHT_SYMBOL, custom_id="help_right"),
    manage_components.create_button(style=ButtonStyle.red, label=CANCEL_SYMBOL, custom_id="delete"),
)


@slash.slash(
    name="help",
    description="View help for the OSM Discord bot.",
    guild_ids=guild_ids,
)  # type: ignore
async def help(ctx: SlashContext) -> None:
    await ctx.defer(hidden=False)

    current_page = 0

    actions = help_action_row.copy()
    actions["components"][0]["disabled"] = True
    action_msg = await ctx.send(embed=help_embeds[0], components=[actions])

    while True:
        try:
            btn_ctx: ComponentContext = await manage_components.wait_for_component(
                client, messages=action_msg, components=actions, timeout=60
            )
            # Will auto-delete after one minuite
        except asyncio.TimeoutError:  # User didn't respond
            await action_msg.delete()
        else:  # User responded
            if btn_ctx.author != ctx.author and not utils.is_powerful(btn_ctx.author, btn_ctx.guild):
                await btn_ctx.send("Only the person that ran `/help`, or helpers, can control the menu.", hidden=True)
                continue

            if btn_ctx.custom_id == "delete":
                try:
                    await action_msg.delete()
                except discord.errors.NotFound:
                    pass  # The global delete callback below already caught it
                    # Note that the global callback only works for powerfuls/helpers, so this must be here.
                break
            elif btn_ctx.custom_id == "help_left":
                current_page -= 1
                # Disable the left button if on first page.
                actions["components"][0]["disabled"] = current_page == 0
                actions["components"][1]["disabled"] = False

                await btn_ctx.edit_origin(embed=help_embeds[current_page], components=[actions])
            elif btn_ctx.custom_id == "help_right":
                current_page += 1
                # Disable the right button if on last page.
                actions["components"][0]["disabled"] = False
                actions["components"][1]["disabled"] = current_page == len(help_embeds) - 1

                await btn_ctx.edit_origin(embed=help_embeds[current_page], components=[actions])


# endregion HELP


# When someone clicks a button with custom_id="delete"
@slash.component_callback()
async def delete(btn_ctx: ComponentContext):
    # // (btn_ctx.author != btn_ctx.origin_message.author)
    # AFAIKT there's currently no way to tell who authored the slash command,
    # so this will have to be powerful-only. Deletion by the command invoker is
    # handled inside the slash command, but that will break after re-boot.
    # This will always work, even after re-boots.
    if not utils.is_powerful(btn_ctx.author, btn_ctx.guild):
        await btn_ctx.send("Only the person that called the command or helpers can delete it.", hidden=True)
        return
    await btn_ctx.origin_message.delete()


## MAIN ##

if __name__ == "__main__":
    load_dotenv()
    import tests

    if os.getenv("TESTING") == "True":
        client.run(os.getenv("DISCORD_TESTING_TOKEN"))
    else:
        client.run(os.getenv("DISCORD_TOKEN"))

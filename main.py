from __future__ import annotations

from typing import Any, Iterable, Optional, Union

## IMPORTS ##
import os
from random import choice
import json
from time import sleep
from datetime import datetime
from urllib.parse import quote, unquote
import re

import requests
from dotenv import load_dotenv
from discord import Embed, AllowedMentions
from discord.ext import commands


## SETUP ##

ELM_TYPES_FL = {
    "n": "node",
    "w": "way",
    "r": "relation",
}
TYPES_FL = {
    "n": "node",
    "nd": "node",
    "w": "way",
    "r": "relation",
    "c": "changeset",
    "cs": "changeset",
    "u": "user",
}
NL = "\n"  # This is used as you can't put \n in an f-string expression.

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")


def load_config():
    global config
    # LINK - config.json
    with open("config.json", "r", encoding="utf8") as file:
        config = json.loads(file.read())


def save_config():
    global config
    # LINK - config.json
    with open("config.json", "w", encoding="utf8") as file:
        file.write(json.dumps(config, indent=4))


load_config()

with open(config["ohno_file"], "r", encoding="utf8") as file:
    ohnos = [entry for entry in file.read().split("\n\n") if entry != ""]

with open(config["josm_tips_file"], "r", encoding="utf8") as file:
    josm_tips = [entry for entry in file.read().split("\n\n") if entry != ""]

bot = commands.Bot(
    command_prefix=config["prefix"],
    allowed_mentions=AllowedMentions(
        # I also use checks elsewhere to prevent @ injection.
        everyone=False,
        users=True,
        roles=False,
        replied_user=False,
    ),
)


## UTILS ##


def str_to_date(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


def get_languaged_tag(
    tags: dict[str, str],
    tag: str,
    suffix: str = ":en",
    *,
    pop: bool = False,
) -> tuple[str, str] | None:
    if k := (tag + suffix) in tags:
        return k, tags[k]
    elif tag in tags:
        return tag, tags[tag]
    else:
        return None, None


def comma_every_three(text: str):
    return ",".join(re.findall("...", str(text)[::-1]))[::-1]


## BOT ##


@bot.event
async def on_ready():
    print(f"{bot.user} is connected to the following guilds:\n")
    print("\n - ".join([f"{guild.name}: {guild.id}" for guild in bot.guilds]))


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.MissingRole):
        await ctx.send("You do not have the correct role for this command.")
    else:
        raise error


# Google Bad
@bot.command(name="googlebad", help="Find your fate of using Google Maps.")
async def googlebad_command(ctx):
    response = choice(ohnos).replace("...", "Whenever you mention Google Maps,")
    await ctx.send(response)


# JOSM Tip
@bot.command(name="josmtip", help="Get a JOSM tip.")
async def josmtip_command(ctx):
    response = choice(josm_tips)
    await ctx.send(response)


### TagInfo ###
@bot.command(name="taginfo", help="Show taginfo for a tag.")
async def taginfo_command(ctx, tag: str):
    tag = tag.replace("`", "").split("=", 1)

    if len(tag) == 2:
        if tag[1] == "*" or "":
            del tag[1]

    if len(tag) == 1:
        return await ctx.reply(embed=taginfo_embed(tag[0]))
    elif len(tag) == 2:
        return await ctx.reply(embed=taginfo_embed(tag[0], tag[1]))
    else:
        done_msg = await ctx.message.reply(f"Please provide a tag.")
        sleep(config["autodelete_delay"])
        await done_msg.delete()
        await ctx.message.delete()
        return


def taginfo_embed(key: str, value: str | None = None):
    if value:
        data = requests.get(config["taginfo_url"] + f"api/4/tag/stats?key={quote(key)}&value={quote(value)}").json()
        data_wiki = requests.get(
            config["taginfo_url"] + f"api/4/tag/wiki_pages?key={quote(key)}&value={quote(value)}"
        ).json()
    else:
        data = requests.get(config["taginfo_url"] + f"api/4/key/stats?key={quote(key)}").json()
        data_wiki = requests.get(config["taginfo_url"] + f"api/4/key/wiki_pages?key={quote(key)}").json()

    data_wiki_en = [lang for lang in data_wiki["data"] if lang["lang"] == "en"][0]

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

    if data_wiki_en["image"]["image_url"]:
        embed.set_thumbnail(
            url=data_wiki_en["image"]["thumb_url_prefix"]
            + str(config["thumb_size"])
            + data_wiki_en["image"]["thumb_url_suffix"]
        )
    else:
        embed.set_thumbnail(url=config["symbols"]["tag" if value else "key"])

    # embed.timestamp = datetime.now()
    # This is the last time taginfo updated:
    embed.timestamp = str_to_date(data["data_until"])

    embed.set_author(name="taginfo", url=config["taginfo_url"] + "about")

    embed.description = data_wiki_en["description"]

    #### Fields ####
    d = data["data"][0]
    embed.add_field(
        # This gets the emoji. Removes "s" from the end if it is there to do this.
        name=config["emoji"][d["type"] if d["type"][-1] != "s" else d["type"][:-1]] + " " + d["type"],
        value=f"{comma_every_three(d['count'])} - {d['count_fraction']*100}%"
        + (f"\n{comma_every_three(d['values'])} values" if not value else ""),
        inline=False,
    )
    del data["data"][0]
    for d in data["data"]:
        embed.add_field(
            # This gets the emoji. Removes "s" from the end if it is there to do this.
            name=config["emoji"][d["type"] if d["type"][-1] != "s" else d["type"][:-1]] + " " + d["type"],
            value=f"{comma_every_three(d['count'])} - {d['count_fraction']*100}%"
            + (f"\n{comma_every_three(d['values'])} values" if not value else ""),
            inline=True,
        )

    return embed


### Elements ###
@bot.command(name="elm")
async def elm_command(ctx, elm_type: str, elm_id: str, extras: str = ""):
    extras = extras.split(",")

    elm_type = elm_type.lower()
    if elm_type[0] in ELM_TYPES_FL:
        elm_type = ELM_TYPES_FL[elm_type[0]]
    else:
        return await ctx.repy(
            "Invalid element type, please pick from `node`, `way` or `relation` (`n`,`w`,`r` for short)."
        )

    try:
        # Verify it's just a number to prevent injection or arbritrary text
        elm_id = str(int(elm_id))
    except:
        return await ctx.reply("Incorrectly formatted element id.")

    return await ctx.reply(embed=elm_embed(elm_type, elm_id, extras))


def elm_embed(elm_type: str, elm_id: str, extras: Iterable = []):
    res = requests.get(config["api_url"] + f"api/0.6/{elm_type}/{elm_id}.json")
    elm = res.json()["elements"][0]

    #### Embed ####
    embed = Embed()
    embed.type = "rich"

    embed.url = config["site_url"] + elm_type + "/" + elm_id

    embed.set_footer(
        text=config["copyright_notice"],
        icon_url=config["icon_url"],
    )

    embed.set_thumbnail(url=config["symbols"][elm_type])

    # embed.timestamp = datetime.now()
    # embed.timestamp = str_to_date(elm["timestamp"])

    # embed.set_author(name=elm["user"], url=config["site_url"] + "user/" + elm["user"])

    embed.title = elm_type.capitalize()
    key, name = get_languaged_tag(elm["tags"], "name")
    if key:
        embed.title += ": " + name

    embed.description = (
        f"[{elm['lat']}, {elm['lon']}](<geo:{elm['lat']},{elm['lon']}>)"
        "\n"
        f"[Edit](<https://www.osm.org/edit?{elm_type}={elm_id}>)"
        " • "
        f"[Level0](<http://level0.osmz.ru/?url={elm_type}/{elm_id}>)"
        "\n"
        f"[OSM History Viewer](<https://pewu.github.io/osm-history/#/{elm_type}/{elm_id}>)"
        " • "
        # Note: https://aleung.github.io/osm-visual-history is basically identical, but has some minor fixes missing.
        # i I'm using "Visual History" as the name, despite linking to deep history, as it decribes it's function better.
        f"[Visual History](<https://osmlab.github.io/osm-deep-history/#/{elm_type}/{elm_id}>)"
        " • "
        f"[Mapki/Deep Diff](<http://osm.mapki.com/history/{elm_type}.php?id={elm_id}>)"
    )

    # ? Maybe make it read `colour=` tags for some extra pop?
    # if "colour" in elm["tags"]:
    #     embed.colour = str_to_colour(elm["tags"]["colour"])

    #### Image ####
    # * This would create significant stress to the OSM servers, so I don't reccomend it.
    # ! This dosen't work due to the OSM servers having some form of token check.
    # img_url = (
    #     "https://render.openstreetmap.org/cgi-bin/export?bbox="
    #     f"{elm['lon']-0.001},{elm['lat']-0.001},{elm['lon']+0.001},{elm['lat']+0.001}"
    #     "&scale=1800&format=png"
    # )
    # embed.set_image(url=img_url)

    #### Fields ####
    if "info" in extras:
        embed.add_field(name="ID", value=elm["id"])
        embed.add_field(name="Version", value=f"#{elm['version']}")
        embed.add_field(name="Last edited", value=elm["timestamp"])
        embed.add_field(
            name="Last changeset", value=f"[{elm['changeset']}](<https://www.osm.org/changeset/{elm['changeset']}>)"
        )
        embed.add_field(name="Last editor", value=f"[{elm['user']}](<https://www.osm.org/user/{quote(elm['user'])}>)")

        if elm_type == "node":
            # Discord dosen't appear to link the geo: URI :( I've left it in though incase it gets supported at some time.
            embed.add_field(
                name="Position (lat/lon)", value=f"[{elm['lat']}, {elm['lon']}](<geo:{elm['lat']},{elm['lon']}>)"
            )

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

        # if "description" in elm["tags"]:
        #     k, v = get_languaged_tag(elm["tags"], "description")
        #     elm["tags"].pop(k)
        #     embed.add_field(name="Description", value="> " + v, inline=False)
        # if "inscription" in elm["tags"]:
        #     k, v = get_languaged_tag(elm["tags"], "inscription")
        #     elm["tags"].pop(k)
        #     embed.add_field(name="Inscription", value="> " + v, inline=False)
        if "note" in elm["tags"]:
            k, v = get_languaged_tag(elm["tags"], "note")
            elm["tags"].pop(k)
            embed.add_field(name="Note", value="> " + v, inline=False)
        if "FIXME" in elm["tags"]:
            k, v = get_languaged_tag(elm["tags"], "FIXME")
            elm["tags"].pop(k)
            embed.add_field(name="FIXME", value="> " + v, inline=False)
        elif "fixme" in elm["tags"]:
            k, v = get_languaged_tag(elm["tags"], "fixme")
            elm["tags"].pop(k)
            embed.add_field(name="FIXME", value="> " + v, inline=False)

    if "tags" in extras:
        embed.add_field(
            name="Tags",
            value="\n".join([f"{config['emoji']['tag']}`{k}`=`{v}`" for k, v in elm["tags"].items()]),
            inline=False,
        )

    return embed


# Inline element linking
ELM_INLINE_REGEX = r"(?<!\/|[^\W])(?:node|way|relation)\/\d+(?!\/|[^\W])"
CHANGESET_INLINE_REGEX = r"(?<!\/|[^\W])changeset\/[\w\-_]+(?!\/|[^\W])"
USER_INLINE_REGEX = r"(?<!\/|[^\W])user\/[\w\-_]+(?!\/|[^\W])"


@bot.listen("on_message")
async def elm_inline_listner(msg):
    if msg.author == bot.user:
        return

    # The reference code is because I only want to make the first message a reply, to make it look neat.
    ref = msg

    # Elements
    elms = [elm.split("/") for elm in re.findall(ELM_INLINE_REGEX, msg.clean_content)]

    for elm_type, elm_id in elms:
        await msg.channel.send(embed=elm_embed(elm_type, elm_id), reference=ref)
        ref = None

    # Changesets
    changesets = [thing.split("/")[1] for thing in re.findall(CHANGESET_INLINE_REGEX, msg.clean_content)]

    if len(changesets) != 0:
        links = [
            f"{config['emoji']['changeset']} <https://www.osm.org/changeset/{changeset_id}>"
            for changeset_id in changesets
        ]
        await msg.channel.send("\n".join(links), reference=ref)
        ref = None

    # Users
    users = [thing.split("/")[1] for thing in re.findall(USER_INLINE_REGEX, msg.clean_content)]

    if len(users) != 0:
        links = [f"{config['emoji']['user']} <https://www.osm.org/user/{username}>" for username in users]
        await msg.channel.send("\n".join(links), reference=ref)
        ref = None


# Suggestions
@bot.command(name="suggest", help="Set the channel that suggestions are posted in.")
async def suggest_command(ctx):
    if not config["server_settings"][str(ctx.guild.id)]["suggestions_enabled"]:
        done_msg = await ctx.message.reply(f"Suggestions are not enabled on this server.")
        sleep(config["autodelete_delay"])
        await done_msg.delete()
        await ctx.message.delete()
        return

    suggestion_chanel = bot.get_channel(config["server_settings"][str(ctx.guild.id)]["suggestion_channel"])

    sugg_content = ctx.message.clean_content.split(" ", 1)[1].replace(NL, NL + "> ").replace("@", "�")

    sugg_msg = await suggestion_chanel.send(
        f"""
__**New suggestion posted**__
By: <@!{ctx.author.id}>
> {sugg_content}

Vote with {config['emoji']['vote_yes']}, {config['emoji']['vote_abstain']} and {config['emoji']['vote_no']}.
"""
    )
    done_msg = await ctx.message.reply(
        f"Sent suggestion in <#{config['server_settings'][str(ctx.guild.id)]['suggestion_channel']}>.\nhttps://discord.com/channels/{sugg_msg.guild.id}/{sugg_msg.channel.id}/{sugg_msg.id}"
    )
    await sugg_msg.add_reaction(config["emoji"]["vote_yes"])
    await sugg_msg.add_reaction(config["emoji"]["vote_abstain"])
    await sugg_msg.add_reaction(config["emoji"]["vote_no"])
    sleep(config["autodelete_delay"])
    await done_msg.delete()
    await ctx.message.delete()


@bot.command(name="set_suggestion_channel", help="[+] Set the channel that suggestions are posted in.")
async def set_suggestion_chanel_command(ctx):
    if not config["server_settings"][str(ctx.guild.id)]["power_role"] in [role.id for role in ctx.author.roles]:
        done_msg = await ctx.message.reply(f"You do not have permission to run this command.")
        sleep(config["autodelete_delay"])
        await done_msg.delete()
        await ctx.message.delete()
        return

    config["server_settings"][str(ctx.guild.id)]["suggestion_channel"] = ctx.channel.id
    save_config()
    done_msg = await ctx.message.reply(
        f"Set suggestions channel to <#{config['server_settings'][str(ctx.guild.id)]['suggestion_channel']}>."
    )
    sleep(config["autodelete_delay"])
    await done_msg.delete()
    await ctx.message.delete()


## MAIN ##

if __name__ == "__main__":
    bot.run(TOKEN)

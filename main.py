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
async def googlebad(ctx):
    response = choice(ohnos).replace("...", "Whenever you mention Google Maps,")
    await ctx.send(response)


# JOSM Tip
@bot.command(name="josmtip", help="Get a JOSM tip.")
async def josmtip(ctx):
    response = choice(josm_tips)
    await ctx.send(response)


### Elements ###
@bot.command(name="elm")
async def elm(ctx, elm_type: str, elm_id: str, extras: Union[str, Iterable] = []):
    if isinstance(extras, str):
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

    return await ctx.send(embed=embed, reference=ctx.message)


# Inline element linking
THING_INLINE_REGEX = r"(?<!\/|[^\W])(?:node|way|relation|changeset)\/\d+(?!\/|[^\W])"
USER_INLINE_REGEX = r"(?<!\/|[^\W])(?:user)\/[\w\-_]+(?!\/|[^\W])"


@bot.listen("on_message")
async def elm_inline(msg):
    if msg.author == bot.user:
        return

    things = [thing.split("/") for thing in re.findall(THING_INLINE_REGEX, msg.clean_content)]
    users = [thing.split("/") for thing in re.findall(USER_INLINE_REGEX, msg.clean_content)]

    both = things + users

    if len(both) != 0:
        links = [f"{config['emoji'][item[0]]} <https://www.osm.org/{item[0]}/{item[1]}>" for item in both]

        return await msg.reply("\n".join(links))


# Suggestions
@bot.command(name="suggest", help="Set the channel that suggestions are posted in.")
async def suggest(ctx):
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
        f"Sent suggestion in <#{config['suggestion_channel']}>.\nhttps://discord.com/channels/{sugg_msg.guild.id}/{sugg_msg.channel.id}/{sugg_msg.id}"
    )
    await sugg_msg.add_reaction(config["emoji"]["vote_yes"])
    await sugg_msg.add_reaction(config["emoji"]["vote_abstain"])
    await sugg_msg.add_reaction(config["emoji"]["vote_no"])
    sleep(config["autodelete_delay"])
    await done_msg.delete()
    await ctx.message.delete()


@bot.command(name="set_suggestion_channel", help="Set the channel that suggestions are posted in.")
async def set_suggestion_chanel(ctx):
    if not config["server_settings"][str(ctx.guild.id)]["power_role"] in [role.id for role in ctx.author.roles]:
        done_msg = await ctx.message.reply(f"You do not have permission to run this command.")
        sleep(config["autodelete_delay"])
        await done_msg.delete()
        await ctx.message.delete()

    config["server_settings"][str(ctx.guild.id)]["suggestion_channel"] = ctx.channel.id
    save_config()
    done_msg = await ctx.message.reply(f"Set suggestions channel to <#{config['server_settings'][str(ctx.guild.id)]['suggestion_channel']}>.")
    sleep(config["autodelete_delay"])
    await done_msg.delete()
    await ctx.message.delete()


## MAIN ##

if __name__ == "__main__":
    bot.run(TOKEN)

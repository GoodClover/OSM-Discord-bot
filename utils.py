# /bin/python3
# Utility functions, such as coordinate calculations or data transformations.

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

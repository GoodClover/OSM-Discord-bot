# /bin/python3
# Functions used for communicating with network services. Mainly getting elements
# and maybe later servicing tiles and overpass queries (+caching) as well.
import requests

from configuration import config
from configuration import guild_ids


def get_elm(elm_type: str, elm_id: str | int, get_discussion: bool = False) -> dict:
    # New, unified element query function.
    suffix = ""
    if get_discussion and elm_type == "changeset":
        # Notes are always queried with discussion.
        suffix = "?include_discussion=true"
    if elm_type == "note" or elm_type == "notes":
        # Notes api is rather odd, as it has `noteS`, not `note`
        elm_type = "notes"

    res = requests.get(config["api_url"] + f"api/0.6/{elm_type}/{elm_id}.json" + suffix)
    if elm_type == "notes":
        elm_type = "note"
    code = res.status_code
    if code == 410:
        raise ValueError(f"{elm_type.capitalize()} `{elm_id}` has been deleted.")
    elif code == 404:
        raise ValueError(f"{elm_type.capitalize()} `{elm_id}` has never existed.")
    try:
        elm = res.json()
    except (json.decoder.JSONDecodeError):
        raise ValueError(f"{elm_type.capitalize()} `{elm_id}` does not exist.")
    if elm_type == "note":
        elm["geometry"] = [[tuple(elm["geometry"]["coordinates"])]]
        pass  # Notes don't need much special parsing, they are good to go.
    elif elm_type == "changeset":
        try:
            elm = elm["elements"][0]
            elm["geometry"] = [
                [
                    (elm["minlat"], elm["minlon"]),
                    (elm["minlat"], elm["maxlon"]),
                    (elm["maxlat"], elm["maxlon"]),
                    (elm["maxlat"], elm["minlon"]),
                    (elm["minlat"], elm["minlon"]),
                ]
            ]
        except (IndexError, KeyError):
            raise ValueError(f"Changeset `{elm_id}` was not found.")
    elif elm_type == "user":
        try:
            elm = elm["user"]
        except (IndexError, KeyError):
            raise ValueError(f"User `{elm_id}` was not found")
    else:
        try:
            elm = elm["elements"][0]
        except (IndexError, KeyError):
            raise ValueError(f"{elm_type.capitalize()} `{elm_id}` was not found.")
    return elm


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

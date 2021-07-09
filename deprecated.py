# /bin/python3
# Functions with "old"-suffix or prefix.
# This doesn't work correct.
# def comma_every_three(text: str) -> str:
#     return ",".join(re.findall("...", str(text)[::-1]))[::-1]


def get_id_from_username_old(username: str) -> int:
    whosthat = requests.get(config["whosthat_url"] + "whosthat.php?action=names&q=" + username).json()
    if len(whosthat) > 0:
        return whosthat[0]["id"]
    else:
        raise ValueError(f"User `{username}` not found")


async def get_image_cluster_old(
    lat_deg: float,
    lon_deg: float,
    zoom: int,
    tile_url: str = config["tile_url"],
) -> File:
    # Modified from https://github.com/ForgottenHero/mr-maps
    delta_long = 0.00421 * math.pow(2, config["rendering"]["max_zoom"] - int(zoom))
    delta_lat = 0.0012 * math.pow(2, config["rendering"]["max_zoom"] - int(zoom))
    lat_deg = float(lat_deg) - (delta_lat / 2)
    lon_deg = float(lon_deg) - (delta_long / 2)
    i = 0
    j = 0
    xmin, ymax = deg2tile(lat_deg, lon_deg, zoom)
    xmax, ymin = deg2tile(lat_deg + delta_lat, lon_deg + delta_long, zoom)
    Cluster = Image.new(
        "RGB",
        ((xmax - xmin + 1) * config["rendering"]["tile_w"] - 1, (ymax - ymin + 1) * config["rendering"]["tile_h"] - 1),
    )
    for xtile in range(xmin, xmax + 1):
        for ytile in range(ymin, ymax + 1):
            try:
                res = requests.get(tile_url.format(zoom=zoom, x=xtile, y=ytile), headers=config["rendering"]["HEADERS"])
                tile = Image.open(BytesIO(res.content))
                Cluster.paste(
                    tile,
                    box=(
                        (xtile - xmin) * config["rendering"]["tile_w"],
                        (ytile - ymin) * config["rendering"]["tile_h"],
                    ),
                )
                i = i + 1
            except Exception as e:
                print(e)
        j = j + 1
    filename = config["map_save_file"].format(t=time.time())
    Cluster.save(filename)
    # return File(filename)
    return Cluster


def get_elm_old(elm_type: str, elm_id: str | int, suffix: str = "") -> dict:
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

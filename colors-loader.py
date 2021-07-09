# Colour handling
# This module is meant to be used in future when rendering function gets support for reading colour tags.
import colorsys
import json

import requests

from configuration import config

colnames_url = config["rendering"]["colour_names_json_url"]
RAL_url = config["rendering"]["RAL_url"]
# colnames_url="https://raw.githubusercontent.com/bahamas10/css-color-names/master/css-color-names.json"
# RAL_url="https://raw.githubusercontent.com/smaddy/ral-json/main/ral_pretty.json"


def get_RAL():
    RAL = dict()
    data = requests.get(RAL_url).json()
    for code in data:
        for name in data[code]["names"]:
            col = "".join(data[code]["names"][name].lower().split())
            # if col not in RAL:
            #    RAL[col]=set()
            # RAL[col].add(data[code]["color"]["hex"].lower())
            # There is just one conflict: Spanish colour "Amarillo oliva"
            RAL[col] = data[code]["color"]["hex"].lower()
        RAL["ral" + code] = data[code]["color"]["hex"].lower()
    return RAL


colours = requests.get(colnames_url).json()
RAL = get_RAL()


custom_colours = {  # The most common color tags not covered by algorithm of try_parse_colour
    # Mostly these are foreign names of css colours.
    "grau": colours["gray"],
    "rot": colours["red"],
    "rouge": colours["red"],
    "braun": colours["brown"],
    "marfim": RAL["ivory"],
    "sand": RAL["sandyellow"],
}
colours.update(custom_colours)
# There are 365 (of 1870) named colours listed on taginfo, 100 of them are default css color codes.


def blended_colour(col_list):
    # Input list of strings representing #RRGGBB
    hues, lights, saturations = [], [], []
    for col in col_list:
        h, l, s = hex_to_hls(col)
        if s > 0:
            # Hue is 0.0 when we have monocromatic (s==0) colour. These will be exempt
            # from calculation as that may produse very red picture.
            hues.append(h)
        lights.append(l)
        saturations.append(s)
    h = sum(hues) / max([1, len(hues)])
    l = sum(lights) / len(col_list)
    s = sum(saturations) / len(col_list)
    return hls_to_hex((h, l, s))


def hex_to_hls(valid_value):
    return colorsys.rgb_to_hls(
        int(valid_value[1:3], 16) / 255, int(valid_value[3:5], 16) / 255, int(valid_value[5:7], 16) / 255
    )


def hls_to_hex(hls):
    # Convert HLS (3x float 0..1) to hexadecimal RGB
    return "#" + "".join(list(map(lambda x: "{:02x}".format(round(x * 255)), colorsys.hls_to_rgb(*hls))))


def is_hexcode(value):
    # Input: str. Output: bool
    hexx = value.strip("#").lower()
    # https://stackoverflow.com/questions/11592261
    return all(c in "0123456789abcdef" for c in hexx)


def try_parse_colour(color_value):
    # color_value is str
    # Returns string in format #RRGGBB  OR None in case resolving text to hex failed.
    color_value = color_value.strip("#").strip().lower()
    for char_to_replace in "-_/ ":
        color_value = color_value.replace(char_to_replace, "-")
    color_value = color_value.strip("-")
    key_col = color_value.replace("-", "")
    if key_col in colours:
        return colours[key_col]
    # Added support for RAL color codes as some tags use them.
    if key_col in RAL:
        return RAL[key_col]
    if is_hexcode(color_value):
        # Some crazy corner case handling
        if len(set(color_value)) == 1:  # Handles #FFFFFFF and #b
            return "#" + color_value[0] * 6
        elif len(color_value) == 2:
            return "#" + color_value * 3
        elif len(color_value) == 3:
            return "#" + color_value[0] * 2 + color_value[1] * 2 + color_value[2] * 2
        elif len(color_value) == 4:
            return "#" + color_value + 2 * color_value[-1]
        elif len(color_value) == 5:
            return "#" + color_value + color_value[-1]
        elif len(color_value) == 6:
            return "#" + color_value
        else:
            return "#" + color_value[:6]
    if is_hexcode(color_value[:6]):  # '#fffdddo'
        return "#" + color_value[:6]
    # Added support for names like light-X (light-cyan)
    if key_col.startswith("light") or key_col.startswith("dark"):
        # Try to parse colour light-X as X and then apply transformation
        if key_col.startswith("light"):
            sub_parse = try_parse_colour(color_value[5:])
            pwr = 0.5
        if key_col.startswith("dark"):
            sub_parse = try_parse_colour(color_value[4:])
            pwr = 2
        if not sub_parse:
            return
        hls = list(hex_to_hls(sub_parse))  # Luminosity values are floats 0..1
        hls[1] = pow(hls[1], pwr)  # Using powers to make them higher-lower.
        return hls_to_hex(hls)
    # Colour blending for cases like red-white-red.
    if "-" in color_value:
        cols_to_blend = list(map(try_parse_colour, color_value.split("-")))
        if not all(cols_to_blend):  # One of the colors was not resolved
            return
        return blended_colour(cols_to_blend)
    # Some colors are defined as rgb(R, G, B)
    if key_col.startswith("rgb(") and (key_col.endswith(")") or key_col.endswith(");")):
        # "rgb(90,80,75)" and "rgb(114, 200, 251);"
        rgb = json.loads(key_col.strip(";")[3:].replace("(", "[").replace(")", "]"))
        return "#" + "".join(list(map(lambda x: "{:02x}".format(round(x)), rgb)))
    # print(f"Hex lookup for {color_value} failed.")


# with open(r"..\geo\top_3000_colors.txt", "r", encoding="utf8") as f:
#    hmm=f.read().split('\n')
#    e=list(filter(lambda x: not try_parse_colour(x),hmm))

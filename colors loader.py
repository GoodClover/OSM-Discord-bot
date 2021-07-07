#Colour handling

colour_names_json_url = "https://raw.githubusercontent.com/bahamas10/css-color-names/master/css-color-names.json"
import requests
import colorsys
colours = requests.get(colour_names_json_url).json()
custom_colours = {
        None:None
    }
colours.update(custom_colours)
# There are 365 (of 1870) named colours listed on taginfo, 100 of them are default css color codes.

def hex_to_hls(valid_value):
    return colorsys.rgb_to_hls(int(valid_value[1:3],16)/255,
            int(valid_value[3:5],16)/255, int(valid_value[5:7],16)/255)

def hls_to_hex(hls):
    # Converts HLS (3x float 0..1) to hexadecimal RGB
    return '#'+''.join(list(map(lambda x:"{:02x}".format(round(x*255)), colorsys.hls_to_rgb(*hls))))

def is_hexcode(value):
    # Input: str. Output: bool
    hexx = value.strip('#').lower()
    # https://stackoverflow.com/questions/11592261
    return all(c in "0123456789abcdef" for c in hexx)

def try_parse_colour(color_value):
    # color_value is str
    color_value = color_value.strip('#').strip().lower().replace('_','-').replace('/','-')
    key_col = color_value.replace('-','')
    if key_col in colours:
        return colours[key_col]
    if is_hexcode(color_value):
        # Some crazy corner case handling
        if len(set(color_value)) == 1: # Handles #FFFFFFF and #b
            return '#'+color_value[0]*6
        elif len(color_value) == 2:
            return '#' + color_value*3
        elif len(color_value) == 3:
            return '#'+color_value[0]*2+color_value[1]*2+color_value[2]*2
        elif len(color_value) == 4:
            return '#' + color_value+2*color_value[-1]
        elif len(color_value) == 5:
            return '#' + color_value+color_value[-1]
        elif len(color_value) == 6:
            return '#' + color_value
        else:
            return '#' + color_value[:6]
    # Todo: Add support for names like light-X or red-white-red
    if key_col.startswith('light') or key_col.startswith('dark'):
        # Try to parse colour light-X as X and then apply transformation
        if key_col.startswith('light'):
            sub_parse = try_parse_colour(key_col[5:])
            pwr = 0.5
        if key_col.startswith('dark'):
            sub_parse = try_parse_colour(key_col[4:])
            pwr = 0.5
        if not sub_parse:
            return
        hls=list(hex_to_hls(sub_parse))  # Luminosity values are floats 0..1
        hls[1] = pow(hls[1], pwr)  # Using powers to make them higher-lower.
        return hls_to_hex(hls)



    

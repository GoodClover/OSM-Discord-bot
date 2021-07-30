# /bin/python3
# Rendering functions
### Rendering ###
# max_zoom - Maximum zoom level without notes.
# Max_note_zoom - Maximum zoom, when notes are present on map.
# tile_w/tile_h - Tile size used for renderer
# tiles_x/tiles_y - Dimensions of output map fragment
# tile_margin_x / tile_margin_y - How much free space is left at edges
# Colours need to be reworked for something prettier, therefore don't relocate them yet.
from io import BytesIO
from typing import Optional
from typing import Union

import requests
from discord import Message
from PIL import Image
from PIL import ImageDraw  # For drawing elements

import colors
import network
import utils
from configuration import config

# Used in render_elms_on_cluster. List of colours to be cycled.
element_colors = ["#000", "#700", "#f00", "#070", "#0f0", "#f60"]

if config["symbols"]["note_solved"].startswith("http"):
    res = requests.get(config["symbols"]["note_solved"], headers=config["rendering"]["HEADERS"])
    closed_note_icon = Image.open(BytesIO(res.content))
else:
    closed_note_icon = Image.open(open(config["symbols"]["note_solved"], "rb"))
if config["symbols"]["note_open"].startswith("http"):
    res = requests.get(config["symbols"]["note_open"], headers=config["rendering"]["HEADERS"])
    open_note_icon = Image.open(BytesIO(res.content))
else:
    # https://stackoverflow.com/a/11895901
    open_note_icon = Image.open(open(config["symbols"]["note_open"], "rb"))

open_note_icon_size = open_note_icon.size
closed_note_icon_size = closed_note_icon.size


# Rendering system may need a rewrite which focuses on object-oriented approach.
# New class should enable easy all-in-one solution, where script can append elements waiting to be rendered.
# Ideally there would be parallel process, that performs network requests, but that's far future.
# What main.py sees, are RenderQueue.add_element, remove_element and render_image. Maybe download_queue.
# Render segment is currently just list of coordinates, but in the future i want it to support for simplifying the output and tag-processing (reading colour tags with colors module).

# I think these elements' classes should be split up into separate file for element processing methods,
# Covering element instance lifecycle from download to uploading to chat.


class BaseElement:
    def __init__(self, elm_type, id, **kwargs):
        self.id = str(id)
        self.type = elem_type
        # Has this element been optimized into renderable form.
        self.resolved = False
        # Geomentry will be different from original. List of RenderSegment-s
        self.geometry = None
        # Rendertype tells if we are dealing with either:
        # * single coordinate pair (node)
        # * single coordinate pair /w image (note / user)
        # * single array of coordinates (RenderSegment / way)
        # * array of RenderSegment-s (relation)
        # Actually that's pretty much self.type
        self.rendertype = None
        self.colour = None  # Use default colour palette
        self.elm = network.get_elm(elm_type, id, "dicussion" in kwargs and kwargs["dicussion"])

    def resolve(self):
        # Add code for geometry lookup.
        # What this func does: Run overpass or API query to get the element,
        # Save result as RenderSegment
        self.resolved = True
        pass


class Note(BaseElement):
    def __init__(self, id):
        super().__init__("note", id)

    def resolve(self):
        super().resolve()


class Changeset(BaseElement):
    def __init__(self, id, get_discussion: bool = False):
        super().__init__("changeset", id, dicussion=get_discussion)

    def resolve(self):
        super().resolve()


class User(BaseElement):
    def __init__(self, username):
        super().__init__("user", network.get_id_from_username(username))
        self.name = str(username)

    def resolve(self):
        super().resolve()


class Element(BaseElement):
    def __init__(self, elem_type, id):
        super().__init__(elm_type, id)

    def resolve(self):
        super().resolve()
        self.geometry = RenderSegment(self)


# The point is that it's not feasible to maintain every node-way-relation of every element, because they will grow large; therefore they need to be optimized into something simpler... I have hit multiple walls again.


class RenderQueue:
    # Think of RenderQueue like temporary collection of elements, that will be featured on single image.
    def __init__(self, *elements):
        # elements is list of tuples (elm_type: str, ID: int|str) to be processed.
        # Init does nothing but sets up variables and then starts adding elements to lists.
        # Status message that could be used while downloading elements. Not sure how that would work.
        self.status_text = ""
        # Discord message that will be optionaly passed when end user should be seeing bot activity.
        # self.status_msg
        # Notes have Lat, Lon and Bool for open/closed.
        self.notes = []
        # Changesets are currently drawn as simple rectangles,
        # but in the future they could support drawing actual contents of changeset.
        self.changesets = []
        # Futureproofing. No actual functionality. One could render users by taking their profile picture
        # and paste it at user's defined home coordinates. Sadly user home seems to be private information.
        # Anyways.. future-proofing.
        self.users = []
        # Elements. Generic catch-all for rest of them.  In future they could be stored as special objects.
        self.elements = []
        # Resolved - has element IDs been converted into tags and geoetry?
        self.resolved = False
        # Segments - array of geographic coordinates with defined or undefined colours.
        # Ready to be plotted on map. If all elements are converted to segments,
        self.add(*elements)
        return self

    def add(self, *elements):
        self.resolved = False
        # First if handles cases like add("note", 1)
        if len(elements) == 2 and type(elements[0]) == str and (type(elements[1]) == int or type(elements[1]) == str):
            elements = [elements]
        # Normal input should be add(("note", 1), ("way", 2))
        for element in elements:
            if element[0].lower() == "note" or element[0].lower() == "notes":
                self.notes.append(Note(element[1]))
            elif element[0].lower() == "changeset":
                self.changesets.append(Changeset(element[1]))
            elif element[0].lower() == "user":
                self.users.append(User(element[1]))
            else:
                self.elements.append(Element(element[0], element[1]))

    def resolve(self):
        # Queries elements to resolve geometry.
        # Resolve is term from overpass query processing for relations,
        # where initial query has only metadata and you need separate command
        # to download actual geometry information.
        if self.resolved:
            return
        for elements in [self.elements, self.changesets, self.notes]:
            for element in elements:
                if not element.resolved:
                    element.resolve()
        self.resolved = True

    def get_bounds(self, segments=True, notes=True) -> tuple[float, float, float, float]:
        # Finds bounding box of rendering queue (segments)
        # Rendering queue is bunch of coordinates that was calculated in previous function.
        if self.resolved:
            raise ValueError(
                "Unresolved element. Element ID was given for rendering, but it was never converted into geographical coordinates."
            )
        min_lat, max_lat, min_lon, max_lon = 90.0, -90.0, 180.0, -180.0
        precision = 5  # https://xkcd.com/2170/
        for segment in self.segments:
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
        for note in self.notes:
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

    def calc_preview_area(self) -> tuple[int, float, float]:
        # queue_bounds: tuple[float, float, float, float]

        # Input: tuple (min_lat, max_lat, min_lon, max_lon)
        # Output: tuple (int(zoom), float(lat), float(lon))
        # Based on old showmap function and https://wiki.openstreetmap.org/wiki/Zoom_levels
        # Finds map area, that should contain all elements.
        # I think this function causes issues with incorrect rendering due to using average of boundaries, not tiles.
        print("Elements bounding box:", *list(map(lambda x: round(x, 4), self.queue_bounds)))
        min_lat, max_lat, min_lon, max_lon = self.queue_bounds
        delta_lat = max_lat - min_lat
        delta_lon = max_lon - min_lon
        zoom_x = int(
            math.log2((360 / delta_lon) * (config["rendering"]["tiles_x"] - 2 * config["rendering"]["tile_margin_x"]))
        )
        center_lon = delta_lon / 2 + min_lon
        # Zoom level is determined by trying to fit x/y bounds into 5 tiles.
        zoom_y = config["rendering"]["max_zoom"] + 1
        while (utils.deg2tile(min_lat, 0, zoom_y)[1] - utils.deg2tile(max_lat, 0, zoom_y)[1] + 1) > config["rendering"][
            "tiles_y"
        ] - 2 * config["rendering"]["tile_margin_y"]:
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
        self.preview_area = (zoom, center_lat, center_lon)
        return (zoom, center_lat, center_lon)

    def set_status(self, text):
        # In more advanced future this function will update actual status message in chat.
        self.status_text = text


class RenderSegment:
    # Render segment is essentialy everything that can have coordinates (and tags).
    # Top level RenderSegment is member of RenderQueue and acts as single OSM element.
    # RenderSegment's primary function is to act as generator for drawing elements
    # onto map. Think of abstractation where you init RenderSegment by saying "I want
    # changeset/1" and it's up to RenderSegment internals to choose if you are getting mere
    # bounding box of the first changeset or you get some complex drawing like osmCha does.
    # Object is structured in a way similar to OSM data model, where coordinates are
    # only stored at individual nodes...

    # Q: But why do we need separate class then? Just use osmapi module?
    # A: OsmApi module is still wrapper of OSM API meaning that single query of a way
    # returns that way only without geographical coordinates data and we would need
    # extra queries to get coordinates and tags of all nodes involved.

    # NB! This class is generated in X.resolve() command, meaning that slow operations are expected.
    def __init__(self, parent_elm, parent_queue, parent_segment=None, recursion_depth=0):
        # parent_queue: RenderQueue
        # parent_elm: BaseElement
        # parent_segment: Union[RenderSegment, None]
        self.parent_elm = parent_elm
        self.parent_segment = parent_segment
        # If this element is a relation and it has subrelations, then other relations are stored into subsegments and RenderSegments
        self.subsegments = []
        # This is used for ways of the element. Infividual elements are single-node segments.
        self.segments = []
        if parent_elm.type == "relation":
            output_type = "body"  # Original version
            if 1 < recursion_depth:
                output_type = "center"  # Alternative: "bb"
            Q = "[out:json][timeout:45];relation(id:" + str(elem_id) + ");(._;>;);out " + output_type + ";"
        if parent_elm.type == "way":
            Q = "[out:json][timeout:45];" + elem_type + "(id:" + str(elem_id) + ");(._;>;);out body;"
        parent_queue.set_status(f"{LOADING_EMOJI} Querying `" + Q + "`")
        # Above line may introduce error when running it from /element, not on_message.
        result = overpass_api.query(Q)
        self.tags = result.something.tags

    def reduce(self):
        # See  def reduce_segment_nodes(segments
        pass

    def __add__(self, other_segment):
        # See  def merge_segments_segments
        pass

    def calc_limit(no_of_nodes):
        # Excel equivalent is =IF(A1<50;A1;SQRT(A1-50)+50)
        # Limiter_offset - Minimum number of nodes.
        # Reduction_factor - n-th root by which array length is reduced.
        if no_of_nodes < config["rendering"]["limiter_offset"]:
            return no_of_nodes
        else:
            return int(
                (no_of_nodes - config["rendering"]["limiter_offset"]) ** (1 / config["rendering"]["reduction_factor"])
                + config["rendering"]["limiter_offset"]
            )

    def render(self):
        for x in y:
            yield x

    @property
    def colour(self):
        """Return colour of the object."""
        for col_tag in sorted(filter(lambda x: "colo" in x, self.tags)):
            hexcode = colors.try_parse_colour(self.tags[col_tag])
            if hexcode is not None:
                print(f"{self}'s tag {col_tag}={self.tags[col_tag]} is parsed as {hexcode}.")
                return hexcode
        if self.parent_segment:
            print(f"{self}'s colour is undefined, using parent segment.")
            return self.parent_segment.colour
        else:
            print(f"{self}'s colour is undefined, using parent element.")
            return self.parent_elm.colour
        print(f"{self}'s and all it's parent objects colours are undefined. Resort to deafault colour schema.")
        return None


# Actual slash commands for all elements could be standardized.
# It's the get_embed that's different.
# Standard part for getting map:
"""
    files = []
    if "map" in extras_list:
        await ctx.defer()
        render_queue = changeset["geometry"]
        utils.check_rate_limit(ctx.author_id)
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
"""


def reduce_segment_nodes(segments: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    # Relative simple way to reduce nodes by just picking every n-th node.
    # Ignores ways with less than 50 nodes.
    for seg_num in range(len(segments)):
        segment = segments[seg_num]  # For each segment
        seg_len = len(segment)
        limit = RenderSegment.calc_limit(seg_len)  # Get number of nodes allowed
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


def get_image_tile_range(lat_deg: float, lon_deg: float, zoom: int) -> tuple[int, int, int, int, tuple[float, float]]:
    # Following line is duplicataed at calc_preview_area()
    center_x, center_y = utils.deg2tile_float(lat_deg, lon_deg, zoom)
    utils.print("Center X/Y:", center_x, center_y, lvl=3)
    xmin, xmax = int(center_x - config["rendering"]["tiles_x"] / 2), int(center_x + config["rendering"]["tiles_x"] / 2)
    utils.print("X min/max:", xmin, xmax, lvl=3)
    n = 2 ** zoom  # N is number of tiles in one direction on zoom level
    if config["rendering"]["tiles_x"] % 2 == 0:
        xmax -= 1
    ymin, ymax = int(center_y - config["rendering"]["tiles_y"] / 2), int(center_y + config["rendering"]["tiles_y"] / 2)
    if config["rendering"]["tiles_y"] % 2 == 0:
        ymax -= 1
    # Sets vertical limits to area.
    # This part has been commented out because if actual Y-tile range is smaller
    # than constant defined in config, tiles will be drawn at too high location.
    # ymin = max(ymin, 0)
    # ymax = min(ymax, n)
    # tile_offset - By how many tiles should tile grid shifted somewhere (up left?).
    # Constant offset: if map is odd number of tiles wide,
    #  offset will be increased by half of a tile.
    utils.print("Tile offset calculation", lvl=4)
    utils.print(
        "center_x:",
        center_x,
        "\nConstant X offset:",
        config["rendering"]["tiles_x"],
        "\nConstant Y offset:",
        ((config["rendering"]["tiles_y"] % 2) / 2) % 1,
        config["rendering"]["tiles_x"] % 2,
        (config["rendering"]["tiles_x"] % 2) / 2,
        "\nCenter_X + constant offset:",
        (center_x + (config["rendering"]["tiles_x"] % 2) / 2),
        lvl=4,
    )
    tile_offset = (
        (center_x + (config["rendering"]["tiles_x"] % 2) / 2) % 1,
        (center_y + (config["rendering"]["tiles_y"] % 2) / 2) % 1,
    )
    # tile_offset = 0,0
    utils.print("Offset (X/Y, Lon/Lat):", tile_offset, lvl=2)
    utils.print(
        f"get_image_tile_range{(lat_deg, lon_deg, zoom)} -> {(xmin, xmax - 1, ymin, ymax - 1, tile_offset)}", lvl=3
    )
    return xmin, xmax - 1, ymin, ymax - 1, tile_offset


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
        utils.print(coord, lvl=5)
        if note[2]:  # If note is closed
            note_icon = closed_note_icon
            icon_pos = (int(coord[0] - closed_note_icon_size[0] / 2), int(coord[1] - closed_note_icon_size[1]))
        else:
            note_icon = open_note_icon
            icon_pos = (int(coord[0] - open_note_icon_size[0] / 2), int(coord[1] - open_note_icon_size[1]))
        # https://stackoverflow.com/questions/5324647
        utils.print(icon_pos, lvl=5)
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


async def elms_to_render(
    elem_type,
    elem_id,
    no_reduction=False,
    get_bbox=False,
    recursion_depth=0,
    status_msg: Optional[Message] = None,
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

# /bin/python3
# Rendering functions

res = requests.get(config["symbols"]["note_solved"], headers=config["rendering"]["HEADERS"])
closed_note_icon = Image.open(BytesIO(res.content))
res = requests.get(config["symbols"]["note_open"], headers=config["rendering"]["HEADERS"])
open_note_icon = Image.open(BytesIO(res.content))
open_note_icon_size = open_note_icon.size
closed_note_icon_size = closed_note_icon.size

# Rendering system may need a rewrite, that focuses on object-oriented approach.
# New class should enable easy all-in-one solution, where script can append elements waiting to be rendered.
# Ideally there would be parallel process, that performs network requests, but that's far future.
# What main.py sees, are RenderQueue.add_element, remove_element and render_image. Maybe download_queue.
# Render segment is currently just list of coordinates, but in the future i want it to support for simplifying the output and tag-processing (reading colour tags with colours-loader).


# class RenderQueue:

# class RenderSegment:


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
    print("Elements bounding box:", *list(map(lambda x: round(x, 4), queue_bounds)))
    min_lat, max_lat, min_lon, max_lon = queue_bounds
    delta_lat = max_lat - min_lat
    delta_lon = max_lon - min_lon
    zoom_x = int(
        math.log2((360 / delta_lon) * (config["rendering"]["tiles_x"] - 2 * config["rendering"]["tile_margin_x"]))
    )
    center_lon = delta_lon / 2 + min_lon
    zoom_y = config["rendering"]["max_zoom"] + 1  # Zoom level is determined by trying to fit x/y bounds into 5 tiles.
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
    print(
        center_x,
        config["rendering"]["tiles_x"],
        config["rendering"]["tiles_x"] % 2,
        (config["rendering"]["tiles_x"] % 2) / 2,
        (center_x + (config["rendering"]["tiles_x"] % 2) / 2),
    )
    tile_offset = (
        (center_x + (config["rendering"]["tiles_x"] % 2) / 2) % 1,
        (center_y + (config["rendering"]["tiles_x"] % 2) / 2) % 1,
    )
    # tile_offset = 0,0
    print("Offset:", tile_offset)
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

# /bin/python3
# Rendering functions

res = requests.get(config["symbols"]["note_solved"], headers=config["rendering"]["HEADERS"])
closed_note_icon = Image.open(BytesIO(res.content))
res = requests.get(config["symbols"]["note_open"], headers=config["rendering"]["HEADERS"])
open_note_icon = Image.open(BytesIO(res.content))
open_note_icon_size = open_note_icon.size
closed_note_icon_size = closed_note_icon.size
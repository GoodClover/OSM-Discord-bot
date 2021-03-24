`Preferences → OSM Data → Draw inactive layers in other color`
Checked by default, this will grey out map objects on inactive layers.
Unchecking will let you see these objects on the active layer.
Example use - download osm task manager grid as background layer.

Click on a node to select it, `Shift` + click to add to selection, `Ctrl` + click to toggle it in selection, `Ctrl-Shift` to rotate selection, `Ctrl-Alt` to scale selection.

The continuous download plugin automatically downloads the area when you pan to a new area.

Drawing a way with buildingtools (`B`) while holding `Alt` will create a perfectly rectangular way without any tags.

When dragging a node, hold `Ctrl` to automatically merge it with nearby nodes.

`[` in the todo plugin will skip the current item but leave it in the todo list and go to the next.

`Alt-1/2/…` will toggle if an imagery layer is visibile, with 1 being the bottom layer.

When merging or deleting nodes/wyas you can use `Ctrl-Alt-D` to download the referrers before making the changes.
That will solve issues with other elements that are connected to these nodes/ways.

Selecting multiple POIs and pressing `L` will line them all in a row.

The `TAB` key will hide/show the docked window panels, but not the undocked panels.

The tilde (`~`) key will reorder the imagery layers.

The `]` key will Mark an item in the todo list plugin and zoom to the next item.

Searching for `node:connection < way[building]` (using MapCSS selector syntax) will find buildings that are connected.

Clicking on an item in the selection dialog and pressing `Ctrl-C` will copy its type and id - eg. `way 12345678`.
The reverse works too! Copying `way 12345678` and pressing paste in JOSM will paste a copy of the way if you have it downloaded in your current data.

In the Map Paint Styles Dialog - right click on a style - some have style settings for extra effects.

In Draw mode, holding the `Alt` key while clicking the mouse will start a new way from the last node.

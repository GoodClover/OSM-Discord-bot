# Commands

Most of this is documented via Discord's slash command hints when your using them.

## View elements, changesets, notes and users

### View elements
`/elm <type> <ID> <extras>`

View info about an OSM element. (In OSM, element is node, way or relation).
Gives basic info such as the name and links to a bunch of sites where you can see more about the element.

`<extras>` is a comma seperated list of:

- `info`: view extra info about the element.
- `tags`: show the element's tags.
- `members`: show the members of a relation.

Note: Due to Discord API limits, listing tags and members may not be possible if there are too many.

### View changesets
`/changeset <ID> <extras>`

View info about an OSM changeset.
Gives basic info such as the name and links to a bunch of sites where you can see more about it.

`<extras>` is a comma seperated list of:

- `info`: view extra info about the element.
- `tags`: show the changesets's tags.

### View notes
`/note <ID>`

View info about an OSM note. 
Gives basic info such as the it's text.

`<extras>` is a comma seperated list of:

- `info`: view extra info about the note, such as date created and closed.
- `discussion`: view all note discussion comments.

### View users
`/user <ID>`

View info about an OSM user.
Gives basic info such as the name and links to a few sites where you can see more about it.

`<extras>` is a comma seperated list of:

- `info`: view extra info about the user.

### Inline commands

Querying any of the previous items or map sections is also possible via inline commands. 
Just mention any of them in normal message and bot will wake up. 
There are multiple ways to trigger inline commands.

- Paste ending of an OSM web link (`node/1`). 
- Mention element casually in the text such as:
  - node 1
  - ways 1 and 2
  - relations 1 and 2 or 3, 4 and 5
  - changeset 1 or 2
  - note 55 44
- Paste map fragment (`#map=3/0.0/0.0`)


## Show a section of the map

`/showmap <URL>`

Will fetch an image of the map from the given URL.

The URL must end in a fragment in the form `#map=1/2/3` where `1` is the zoom level and `2/3` are the latitude and longitude.
You may just use a fragment by itself.

## View tag**info**

`/taginfo <tag>`

View the tag**info** stats of a tag or key.

## Random messsages

`/googlebad` and `/josmtip`

View a random message from the [ohno-OSM](https://github.com/GoodClover/ohno-OSM) repo.

## Suggestions

`/suggest <suggestion>`

Allows people to post suggestions and vote with reactions in a set channel.

`/close_suggestion <message-ID> <reason>` (Power people only)

Allows suggestions to get accepted/rejected with a freeform reason.


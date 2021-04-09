# Commands

Most of this is documented via Discord's slash command hints when your using them.

## View elements, changesets and users

`/elm <type> <ID> <extras>`

View info about an OSM element.
Gives basic info such as the name and links to a bunch of sites where you can see more about the element.

`<extras>` is a comma seperated list of:

- `info`: view extra info about the element.
- `tags`: show the element's tags.
- `members`: show the members of a relation.

Note: Due to Discord API limits, listing tags and members may not be possible if there are too many.

`/changeset <ID> <extras>`

View info about an OSM changeset.
Gives basic info such as the name and links to a bunch of sites where you can see more about it.

`<extras>` is a comma seperated list of:

- `info`: view extra info about the element.
- `tags`: show the changesets's tags.

`/user <ID>`

View info about an OSM changeset.
Gives basic info such as the name and links to a bunch of sites where you can see more about it.

`<extras>` is a comma seperated list of:

- `info`: view extra info about the user.

## View tag**info**

`/taginfo <tag>`

View the tag**info** stats of a tag or key.

## Show a section of the map

`/showmap <URL>`

Will fetch an image of the map from the given URL.

The URL must end in a fragment in the form `#map=1/2/3` where `1` is the zoom level and `2/3` are the latitude and longitude.
You may just use a fragment by itself.

## Random messsages

`/googlebad` and `/josmtip`

View a random message from the [ohno-OSM](/GoodClover/ohno-OSM) repo.

## Suggestions

`/suggest <suggestion>`

Allows people to post suggestions and vote with reactions in a set channel.

`/close_suggestion <message-ID> <reason>` (Power people only)

Allows suggestions to get accepted/rejected with a freeform reason.

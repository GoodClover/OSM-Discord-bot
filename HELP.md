# Main page

Welcome the OSM Discord bot help :)

The arrows below can be used to navigate, and the `✘` to delete this message.

This is help only for the Discord bot, for more general OSM help there is a list of resources [here](<https://www.openstreetmap.org/help>), and most info about mapping in OSM is on the [wiki](<https://wiki.openstreetmap.org/>).
If you can't find info about it there, or have any questions, feel free to ask! :)

You can help to improve the bot, and these docs, on the [GitHub page](<https://github.com/GoodClover/OSM-Discord-bot>).
Report bugs and suggest things in the [issues tab](<https://github.com/GoodClover/OSM-Discord-bot/issues>), for bot or Discord suggestions please use `/suggest`.


# Basic controls

Helpers can react to a message with 🗑 to delete it.

Just typing `/` will show a list of all available commands from all bots.

__Elements__
If a message contains something such as `node/240095754`, `user TomH` or `note 834`, then the bot will add reactions that you can click:
🔎 — Embed showing info and map image.
🖼 — Map image. (not on users)
🛏 — Embed showing info.
❌ — Remove reactions and do nothing.

More info about this on the next page…


# Elements, changesets, users and notes

```
/elm <type> <id> [extras]
/changeset <id>
/user <name>
/note <id>
```
As said on the previous page, you can view elements by mentioning them in a message

By default, only basic info about the thing is shown.

__Extended info__
If you press `TAB` an extra time after completing the arguments, you will have the ability to ask for extra info. You should provide a comma separated list of:
• `info` — Show more info about the element, such as its version, the last user to edit it and more.
• `tags` — Show all the tags of an element or changeset.
• `map` — Show an image of the map where this element is.
• `members` — List the members of a relation.
• `discussion` — Show the discussion of a changeset or note.

Discord will say which of the above can use for each command.


# tag**info**

```
/taginfo <tag>
```
Get details about a tag from [tag**info**](<https://taginfo.openstreetmap.org/>).
Accepts tag in the form `highway=*`, `building=house` or `water` (as key).

Statistics about tag usage will be shown, along with a short description of the tag, and it's image off the wiki.


# Suggestions

```
/suggest <suggestion>
```
If you have a suggestion for this Discord server, such as a new emoji 😉, use `/suggest` to post it. Suggestions appear in #suggestion-box.

Once you've posted a suggestion people will be able to vote on it, and eventually voting will be closed. (Hopefully with the words "accepted"!)


# Show a map image

```
/showmap <where>
```
Shown an image of the given map region. (OSM-Carto map style)

`<where>` should be a map fragment in the format `#map=zoom/lat/lon`.

The easiest way to get this is from the end of the URL on the [OSM website's slippy-map](<https://openstreetmap.org>), for example as [`#map=19/-7.15323/109.13150`](<https://www.openstreetmap.org/#map=19/-7.15323/109.13150>).

This may also be done inline, but just pasting the `#map=` map fragment in your message. The bot will then automatically post the image.


# JOSM tips and Google-Bad

```
/josmtip
/googlebad
```
View a tip for [JOSM](<https://wiki.openstreetmap.org/wiki/JOSM>), or see your fate of mentioning Google.

All responses are from the [ohno-OSM](<https://github.com/GoodClover/ohno-OSM>) GitHub repo, feel free to contribute more!

A more interactive way to view the JOSM tips is planned…


# End
https://raw.githubusercontent.com/GoodClover/OSM-Discord-bot/main/res/img/edit_me.png
__TODO:__
• Docs for the wiki bot?
• `/quota` and rate limiting (or maybe that should be omitted?)

You can help to improve these docs by editing [`HELP.md`](<https://github.com/GoodClover/OSM-Discord-bot/blob/main/HELP.md>) on GitHub.
Please see the [README](<https://github.com/GoodClover/OSM-Discord-bot/blob/main/README.md#helpmd>) for info on formatting.

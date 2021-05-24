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
- `map`: show the element on a map.
- `members`: show the members of a relation.

Note: Due to Discord API limits, listing tags and members may not be possible if there are too many.

### View changesets
`/changeset <ID> <extras>`

View info about an OSM changeset.
Gives basic info such as the name and links to a bunch of sites where you can see more about it.

`<extras>` is a comma seperated list of:

- `info`: view extra info about the element.
- `discussion`: show the changesets's discussion.
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

Using inline command will usually make bot to react to your message with 4 emojis and you need to click on any of first 3 to see any results

- 🔎 (`:mag_right:`) - Full results to include both embeddeds and rendered map of elements
- 🖼️ (`:frame_photo:`) - Shows single map screenshot with all elements and notes
- 🛏️ (`:bed:`) - Shows every element's individual embedded.
- ❌ (`:x:`) - Cancel request, all emojis will be removed and bot posts nothing. Default action triggered if no input is detected in 15 seconds.

No emojis will be added, if user has exceeded their quota or would definitely exceed while procesing the request (see below).

## Show a section of the map

`/showmap <URL>`

Will fetch an image of the map from the given URL.

The URL must end in a fragment in the form `#map=1/2/3` where `1` is the zoom level and `2/3` are the latitude and longitude.
You may just use a fragment by itself.
Output size is fixed as 5x5 tiles image with dimensions of 1280x1280 px.

## View tag**info**

`/taginfo <tag>`

View the tag**info** stats of a tag or key.

## Random messsages

`/googlebad` and `/josmtip`

View a random message from the [ohno-OSM](https://github.com/GoodClover/ohno-OSM) repo. `/googlebad` the only command that is excempt from 1 message per 3 sec rate limit.

## Suggestions

`/suggest <suggestion>`

Allows people to post suggestions and vote with reactions in a set channel.

`/close_suggestion <message-ID> <reason>` (Power people only)

Allows suggestions to get accepted/rejected with a freeform reason.

## Quota

`/quota`

All commands in are rate-limited and the personal limit is same for all commands (except `/googlebad` where going over limit triggers easter egg). As of May 2021, limit is 10 function calls per 30 seconds. If you have passed the threshold, bot will reply with hidden message about crossing the line. You can use `/quota` to see how many interactions are left. Output is private and it's formatted similarly to Overpass quota page.

### Special treatment of inline-commands

Normally, no slash command have more than 30 sec cooldown. However, since inline-commands support multiple request per single message and they can be **very** resource-intesive, one command message will be counted as muliple actions, based on different metrics somewhat comparable to Overpass-API. As mentioned before, any request asking for more than maximum amount of allowed items will be ignored.

- Per every requested feature, additional cooldown time is increased exponentially, up to 130 sec for 10th element. Since these counters are ran before actual element processing, most of them usually count down to zero before bot completes.
- If querying elements from Overpass took more than 15 seconds, single cooldown linearly correlated to time spent is applied
- If element rendering is enabled, single cooldown related to amount of way segments is added.
- If processing outputs (render images and sending mesages) took more than 10 seconds, single cooldown linearly correlated to time spent is applied.


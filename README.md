# OSM Word Discord Bot

Plans can be seen in [PLANS.md](PLANS.md).

## Features

### View elements `/elm`

`/elm <type> <id> <extras>`

View info about an OSM element.
Gives basic info such as the name and links to a bunch of sites where you can see more about the element.

`<extras>` is a comma seperated list of:

- `info`: view extra info about the element.
- `tags`: show the element's tags.
- `members`: show the members of a relation.

Note: Due to Discord API limits, listing tags and members may not be possible if there are too many.

### View tag**info** `/taginfo`

`/taginfo <tag>`

View the tag**info** stats of a tag.

### `/googlebad` and `/josmtip`

View a random message from the [ohno-OSM](/GoodClover/ohno-OSM) repo.

### Suggestions `/suggest`

`/suggest <suggestion>`

⚠️ This is unfinished and not really tested, will only develop more if needed.

Allows people to post suggestions and react with an emoji in a set channel.

## Configuration

### `config.json`

Most of the config lives here.
I can't be bothered to list it, so just look at the [sameple config](sample_config.json) for now.

### `.env` file

Make a `.env` (nothing before the dot) containing:

```env
DISCORD_TOKEN=<bot-token>
```

## License

[Could One Credit a Koala Public License](<https://github.com/GoodClover/COCK-Public-License/blob/main/LICENSE.md>)

(Look, I doubt anyone other than myself will ever use/host this code.
If you really don't like the license then message me for explicit permisson or something, I'll likely do it.)

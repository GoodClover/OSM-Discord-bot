# OSM Discord Bot

## Features

For a full list of commands see [COMMANDS.md](COMMANDS.md).
These are slash commands so Discord will also tell you what the commands do and how to use them.

If they are enabled, the bot can show suggestions in a specific channel.

The bot also updates a member count upon someone joining/leaving the server.

Embedding of elmenents, map fragments, notes, users and changesets also works by putting the following somewhere in your message in addition to using the command, using the command enabled getting extra info though if it's wanted:

- `node/<ID>` (`way` and `relation` work too)
- `note/<ID>`
- `user/<username>`
- `changeset/<ID>`
- `map=#<Zoom>/<Lat>/<Lon>`


## Configuration

### `config.json`

Most of the config lives here.
I can't be bothered to list it, so just look at the [sample config](sample_config.json) for now.

### `.env` file

Make a `.env` (nothing before the dot) containing:

```env
DISCORD_TOKEN=<bot-token>
TESTING=<False> or <True>
DISCORD_TESTING_TOKEN=<optional-testing-bot-token>
```

## License

[DBAD Public License](https://github.com/philsturgeon/dbad/blob/master/LICENSE.md)

(Look, I doubt anyone other than myself will ever use/host this code.
If you really don't like the license then message me for explicit permisson or something, I'll likely do it.)

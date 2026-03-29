## EMF Label printing script

Prints labels from Snipe-IT to Zebra label printers.

You'll need [uv](https://docs.astral.sh/uv/getting-started/installation/) installed.

First configure a `.env` file:

```
ASSET_PREFIX=EMF
SNIPEIT_URL=https://assets.orga.emfcamp.org
SNIPEIT_TOKEN=<token>
```

Make sure the Zebra printer is connected and shows up as a printer in the OS.

Then run `uv run python -m emf_labelprint.labelprint`.

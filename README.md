## EMF Label printing script

Prints labels from Snipe-IT to Zebra label printers.

First configure a `.env` file:

```
ASSET_PREFIX=EMF
SNIPEIT_URL=https://assets.orga.emfcamp.org
SNIPEIT_TOKEN=<token>
```

Make sure the Zebra printer is connected and shows up as a printer in the OS.

Then run `poetry install`, `poetry run python -m emf_labelprint.labelprint`.
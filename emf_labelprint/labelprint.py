from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Iterator
from pathlib import Path
import os
import click
import html
from dotenv import dotenv_values
from rich.console import Console
from rich.table import Table

from .printing import get_supported_printers, send_zpl, send_zpl_templated
from .snipeit import SnipeIt

config = {**dotenv_values(".env"), **os.environ}
ASSET_PREFIX: str = config.get("ASSET_PREFIX", "") or ""

LABEL_STOCK = {"asset": "50.8x25.4mm", "box": "76.2x50.8mm"}

ALL_ASSETS = None


@dataclass
class AssetDetails:
    tag: str
    name: str
    id: int
    contents: Optional[str]


def load_templates(printer: str):
    templates_dir = Path(__file__).parent / "templates"
    for template_file in templates_dir.glob("*.zpl"):
        with template_file.open() as template:
            send_zpl(printer, template.read())


def tag2id(tag: str) -> int:
    if tag.startswith(ASSET_PREFIX):
        return int(tag[len(ASSET_PREFIX) :])
    return int(tag)


def id2tag(asset_id: int) -> str:
    return f"{ASSET_PREFIX}{asset_id:05}"


def parse_asset_ids(asset_ids: str) -> Iterator[int]:
    for part in asset_ids.split(","):
        if "-" in part:
            start, end = part.split("-")
            yield from range(tag2id(start), tag2id(end) + 1)
        else:
            yield tag2id(part)


def asset_url(asset_id: int) -> str:
    if config.get("SNIPEIT_URL") is None:
        raise ValueError("No SNIPEIT_URL configured")
    return config["SNIPEIT_URL"] + f"/hardware/{asset_id}"


def format_textbox(text: Optional[str], max_lines: int) -> str:
    if text is None:
        return ""
    lines = map(lambda l: l.strip(), text.split("\n"))
    lines = list(filter(lambda l: l != "", lines))
    return r"\&".join(lines[:max_lines])


def print_asset_labels(
    assets: list[AssetDetails], printer: str, template: str, copies: int = 1
):
    batch = []
    for asset in assets:
        batch += [
            {
                1: asset.name,
                2: asset.tag,
                3: f"QA,{asset_url(asset.id)}",
                4: format_textbox(asset.contents, 8),
            }
        ] * copies
    send_zpl_templated(printer, f"{template.upper()}.ZPL", batch)


@lru_cache
def get_model_description(si: SnipeIt, model_id: int):
    model = si.fetch(f"models/{model_id}")
    return model["manufacturer"]["name"] + " " + model["name"]


def get_contents(si: SnipeIt, asset: dict):
    global ALL_ASSETS

    # No way to search for assets which are checked out to this asset, so just get them all.

    if ALL_ASSETS is None:
        ALL_ASSETS = si.fetch("hardware")["rows"]

    child_assets = [
        child_asset
        for child_asset in ALL_ASSETS
        if child_asset["assigned_to"] is not None
        and child_asset["assigned_to"]["id"] == asset["id"]
    ]

    grouped_child_assets: dict[str, list[dict]] = defaultdict(list)
    for child_asset in child_assets:
        grouped_child_assets[child_asset["model"]["id"]].append(child_asset)

    contents = [
        f"{len(assets)} x {get_model_description(si, model)}"
        for model, assets in grouped_child_assets.items()
    ]

    if asset.get("custom_fields"):
        for field, value in asset["custom_fields"].items():
            if (
                field == "Contents"
                and value["value"] != ""
                and value["value"] is not None
            ):
                # For some reason this JSON contains HTML-encoded text
                contents += html.unescape(value["value"]).split("\n")
    return "\n".join(contents)


def do_print(printer: str, si: SnipeIt, console: Console, template: str):
    asset_ids = console.input("Enter asset IDs or tags: ")
    assets = [
        si.get_asset_by_tag(id2tag(asset_id)) for asset_id in parse_asset_ids(asset_ids)
    ]
    click.secho("Will print labels for:", fg="blue")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Tag")
    table.add_column("Name")
    table.add_column("Model")
    if template == "box":
        table.add_column("Contents")

    asset_details = []

    for asset in assets:
        contents = None
        if template == "box":
            contents = get_contents(si, asset)
            table.add_row(
                asset["asset_tag"], asset["name"], asset["model"]["name"], contents
            )
        else:
            table.add_row(asset["asset_tag"], asset["name"], asset["model"]["name"])

        details = AssetDetails(
            tag=asset["asset_tag"],
            name=asset["name"],
            id=asset["id"],
            contents=contents,
        )
        asset_details.append(details)

    console.print(table)
    confirm = console.input("Print these assets (y/n)? ")
    if confirm.lower() == "y":
        copies = int(console.input("How many copies? "))
        if not copies:
            copies = 1

        click.secho(f"Printing labels for {len(assets)} assets...", fg="blue")
        print_asset_labels(asset_details, printer, template, copies)


@click.option("--printer", "-p", help="Printer to use")
@click.option(
    "--template",
    "-t",
    help="Template to use",
    default="asset",
    show_default=True,
    type=click.Choice(["asset", "box"]),
)
@click.command()
def labelprint(printer: Optional[str], template: str):
    """EMF label printing tool"""

    if not printer:
        printers = get_supported_printers()
        if len(printers) > 1:
            raise click.ClickException(
                f"Multiple supported printers found: {', '.join(printers)}"
            )
        printer = printers[0]

    for key in ("SNIPEIT_URL", "SNIPEIT_TOKEN", "ASSET_PREFIX"):
        if key not in config:
            raise click.ClickException(f"{key} not set in environment")

    console = Console()
    si = SnipeIt(config.get("SNIPEIT_URL"), config.get("SNIPEIT_TOKEN"))
    click.secho(f"Initialising printer {printer}...", fg="blue")
    load_templates(printer)

    click.secho(
        f"You are printing {template} labels - "
        f"ensure you have {LABEL_STOCK[template]} label stock loaded.",
        fg="red",
    )

    while True:
        do_print(printer, si, console, template)


if __name__ == "__main__":
    labelprint()  # pylint: disable=no-value-for-parameter

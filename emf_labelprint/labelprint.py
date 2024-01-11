from typing import Optional, Iterator
from pathlib import Path
import os
import click
from dotenv import dotenv_values
from rich.console import Console
from rich.table import Table

from .printing import get_supported_printers, send_zpl, send_zpl_templated
from .snipeit import SnipeIt

config = {**dotenv_values(".env"), **os.environ}
ASSET_PREFIX: str = config.get("ASSET_PREFIX", "") or ""


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
    return config["SNIPEIT_URL"] or "" + f"/hardware/{asset_id}"


def print_asset_labels(assets: list[dict], printer: str):
    batch = []
    for asset in assets:
        batch.append(
            {
                1: asset["name"],
                2: asset["asset_tag"],
                3: f"QA,{asset_url(asset['id'])}",
            }
        )
    send_zpl_templated(printer, "ASSET.ZPL", batch)


def do_print(printer: str, si: SnipeIt, console: Console):
    asset_ids = console.input("Enter asset IDs or tags: ")
    assets = [
        si.get_asset_by_tag(id2tag(asset_id)) for asset_id in parse_asset_ids(asset_ids)
    ]
    click.secho("Will print labels for:", fg="blue")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Tag")
    table.add_column("Name")
    table.add_column("Model")
    for asset in assets:
        table.add_row(asset["asset_tag"], asset["name"], asset["model"]["name"])
    console.print(table)
    confirm = console.input("Print these assets (y/n)? ")
    if confirm.lower() == "y":
        click.secho(f"Printing labels for {len(assets)} assets...", fg="blue")
        print_asset_labels(assets, printer)


@click.option("--printer", "-p", help="Printer to use")
@click.command()
def labelprint(printer: Optional[str]):
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

    while True:
        do_print(printer, si, console)


if __name__ == "__main__":
    labelprint()  # pylint: disable=no-value-for-parameter

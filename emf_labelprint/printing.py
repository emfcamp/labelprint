import subprocess


def get_printers() -> list[str]:
    lines = subprocess.check_output(["lpstat", "-p"]).decode("utf-8").split("\n")
    return [line.split(" ")[1] for line in lines if line.startswith("printer")]


def is_zebra_printer(printer_name: str) -> bool:
    return printer_name.lower().startswith("zebra_technologies")


def get_supported_printers() -> list[str]:
    return [printer for printer in get_printers() if is_zebra_printer(printer)]


def send_zpl(printer: str, zpl: str):
    subprocess.run(
        ["lp", "-d", printer, "-o", "raw", "-s", "-"],
        input=zpl.encode("utf-8"),
        check=True,
    ).check_returncode()


def send_zpl_templated(printer: str, template: str, values: list[dict]):
    zpl = ""
    for item in values:
        zpl += "^XA\n"
        zpl += f"^XFE:{template}^FS\n"
        for key, value in item.items():
            zpl += f"^FN{key}^FD{value}^FS\n"
        zpl += "^PQ1\n"
        zpl += "^XZ\n"
    send_zpl(printer, zpl)

import qrcode
import qrcode.image.svg
import xml.etree.ElementTree as ET
import cairosvg
import textwrap
import io
import time
import logging
from brother_ql.brother_ql_create import create_label
from brother_ql.raster import BrotherQLRaster
from brother_ql.backends import backend_factory
from brother_ql.reader import interpret_response
from PIL import Image

logger = logging.getLogger()


def get_qr_code(url):
    """ Generate a QR code SVG fragment from a URL.
        Return the result as an elementtree. """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=1,
    )
    qr.add_data(url)
    qr.make()
    img = qr.make_image(image_factory=qrcode.image.svg.SvgFragmentImage)
    bio = io.BytesIO()
    img.save(bio)
    return ET.fromstring(bio.getvalue())


class FormattingError(Exception):
    pass


def prepare_data(box_id, box_name, url, contents):
    if len(str(box_id)) > 6:
        raise FormattingError("Box ID too long")
    if len(box_name) > 10:
        raise FormattingError("Box name too long")
    if len(url) > 30:
        raise FormattingError("URL too long")

    contents = textwrap.wrap(contents, 65)
    data = {
        "boxid": "Box %s" % box_id,
        "boxname": box_name,
        "qrcode": url
    }
    for i in range(0, 4):
        if len(contents) > i:
            data["contents%s" % (i + 1)] = contents[i]
        else:
            data["contents%s" % (i + 1)] = ""

    if len(contents) > 4:
        print("Contents truncated!")
    return data


def svg_from_template(path, fields):
    nsmap = {
        'svg': 'http://www.w3.org/2000/svg'
    }

    with open(path, "rb") as f:
        svg = ET.fromstring(f.read())

    for key, value in fields.items():
        element = svg.find('.//svg:tspan[@id="%s"]' % key, namespaces=nsmap)
        if element is None:
            continue
        element.text = value

    qrg = svg.find('.//svg:g[@id="qrcode"]', namespaces=nsmap)
    qr_svg = get_qr_code(fields['qrcode'])
    for el in qr_svg:
        qrg.append(el)

    return svg


def render_svg(svg, out_height=696):
    width = float(svg.get("width"))
    height = float(svg.get("height"))

    # Set the SVG document height to the correct pixel size
    # for the label printer. We're using continuous-width
    # labels so scale the width.

    # The SVG's internal coordinate system is maintained by
    # the viewBox attribute, so we don't need to scale every
    # coordinate in it, just the document size.
    out_width = width / height * out_height
    svg.set("width", "%spx" % out_width)
    svg.set("height", "%spx" % out_height)

    return cairosvg.svg2png(bytestring=ET.tostring(svg))


def print_label(qlr):
    be = backend_factory('pyusb')
    list_available_devices = be['list_available_devices']
    BrotherQLBackend = be['backend_class']
    ad = list_available_devices()
    if len(ad) == 0:
        logger.error("No printer found")
        return
    string_descr = ad[0]['identifier']

    printer = BrotherQLBackend(string_descr)

    start = time.time()
    printer.write(qlr.data)
    printing_completed = False
    waiting_to_receive = False
    while time.time() - start < 10:
        data = printer.read()
        if not data:
            time.sleep(0.005)
            continue
        try:
            result = interpret_response(data)
        except ValueError:
            logger.error("TIME %.3f - Couln't understand response: %s", time.time() - start, data)
            continue
        logger.debug('TIME %.3f - result: %s', time.time() - start, result)
        if result['errors']:
            logger.error('Errors occured: %s', result['errors'])
        if result['status_type'] == 'Printing completed':
            printing_completed = True
        if result['status_type'] == 'Phase change' and result['phase_type'] == 'Waiting to receive':
            waiting_to_receive = True
        if printing_completed and waiting_to_receive:
            break
    if not (printing_completed and waiting_to_receive):
        logger.warning('Printing potentially not successful?')


def prepare_label(img):
    imgio = io.BytesIO(img)
    img = Image.open(imgio)
    qlr = BrotherQLRaster("QL-800")
    qlr.exception_on_warning = True
    create_label(qlr, img, '62', rotate='90')
    return qlr

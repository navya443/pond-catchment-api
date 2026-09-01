from lxml import etree
import re


KML_NAMESPACE = "http://www.opengis.net/kml/2.2"
NS = {"kml": KML_NAMESPACE}


def parse_coordinates(text):
    """
    Convert KML coordinate text into a list of
    (longitude, latitude) tuples.
    """

    coordinates = []

    if not text:
        return coordinates

    for item in text.strip().split():
        parts = item.split(",")

        if len(parts) >= 2:
            try:
                longitude = float(parts[0])
                latitude = float(parts[1])

                coordinates.append((longitude, latitude))

            except ValueError:
                continue

    return coordinates


def extract_elevation(name):
    """
    Extract numeric elevation from the Placemark name.
    Example:
        '277.0' -> 277.0
        'Contour 277.0' -> 277.0
    """

    if not name:
        return None

    match = re.search(r"-?\d+(?:\.\d+)?", name)

    if match:
        try:
            return float(match.group())
        except ValueError:
            return None

    return None


def parse_kml(file_path):
    """
    Parse a KML file and return contour information.

    Only Placemarks containing a LineString and a
    numeric elevation are treated as contours.
    """

    tree = etree.parse(file_path)

    contours = []

    placemarks = tree.xpath(
        "//kml:Placemark",
        namespaces=NS
    )

    for placemark in placemarks:

        # Find the name
        name_element = placemark.find(
            "kml:name",
            namespaces=NS
        )

        if name_element is None:
            continue

        name = name_element.text

        # Extract elevation
        elevation = extract_elevation(name)

        if elevation is None:
            continue

        # Find LineString
        line_string = placemark.find(
            ".//kml:LineString",
            namespaces=NS
        )

        if line_string is None:
            continue

        # Find coordinates
        coordinates_element = line_string.find(
            "kml:coordinates",
            namespaces=NS
        )

        if coordinates_element is None:
            continue

        coordinates = parse_coordinates(
            coordinates_element.text
        )

        if len(coordinates) < 2:
            continue

        contours.append({
            "elevation": elevation,
            "coordinates": coordinates
        })

    return contours

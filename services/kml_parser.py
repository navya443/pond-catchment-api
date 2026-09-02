from lxml import etree
import re
import zipfile
import os
import tempfile


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
    Parse a KML or KMZ file and return contour information.

    KMZ files are ZIP archives containing a KML file.
    Only Placemarks containing a LineString and a
    numeric elevation are treated as contours.
    """

    actual_kml_path = file_path
    temp_dir = None

    # ---------------------------------------
    # KMZ SUPPORT
    # ---------------------------------------

    if file_path.lower().endswith(".kmz"):

        if not zipfile.is_zipfile(file_path):
            raise ValueError("Invalid KMZ file")

        temp_dir = tempfile.mkdtemp()

        with zipfile.ZipFile(file_path, "r") as kmz:

            kml_files = [
                name
                for name in kmz.namelist()
                if name.lower().endswith(".kml")
            ]

            if not kml_files:
                raise ValueError(
                    "No KML file found inside KMZ"
                )

            # Prefer doc.kml if available
            kml_name = next(
                (
                    name
                    for name in kml_files
                    if os.path.basename(name).lower() == "doc.kml"
                ),
                kml_files[0]
            )

            actual_kml_path = kmz.extract(
                kml_name,
                temp_dir
            )

    try:

        tree = etree.parse(actual_kml_path)

        contours = []

        placemarks = tree.xpath(
            "//kml:Placemark",
            namespaces=NS
        )

        for placemark in placemarks:

            # ---------------------------------------
            # Find name
            # ---------------------------------------

            name_element = placemark.find(
                "kml:name",
                namespaces=NS
            )

            if name_element is None:
                continue

            name = name_element.text

            # ---------------------------------------
            # Extract elevation
            # ---------------------------------------

            elevation = extract_elevation(name)

            if elevation is None:
                continue

            # ---------------------------------------
            # Find LineString
            # ---------------------------------------

            line_string = placemark.find(
                ".//kml:LineString",
                namespaces=NS
            )

            if line_string is None:
                continue

            # ---------------------------------------
            # Find coordinates
            # ---------------------------------------

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

    finally:

        # ---------------------------------------
        # Cleanup temporary KMZ files
        # ---------------------------------------

        if temp_dir and os.path.exists(temp_dir):

            import shutil

            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

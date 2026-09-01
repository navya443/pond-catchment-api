from flask import Flask, request, jsonify, send_file, render_template
import os
import uuid

from services.kml_parser import parse_kml

from services.terrain import (
    create_elevation_grid,
    calculate_slope,
    find_best_pond_candidate,
    calculate_catchment_area,
    create_catchment_geojson,
    grid_cell_to_latlon
)


app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "results"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/web", methods=["GET"])
def web_interface():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():

    # ---------------------------------------
    # Check uploaded file
    # ---------------------------------------

    if "file" not in request.files:

        return jsonify({
            "status": "error",
            "message": "No KML file uploaded"
        }), 400

    file = request.files["file"]

    if file.filename == "":

        return jsonify({
            "status": "error",
            "message": "No file selected"
        }), 400

    # ---------------------------------------
    # Check extension
    # ---------------------------------------

    filename = file.filename.lower()

    if not (
        filename.endswith(".kml")
        or filename.endswith(".kmz")
    ):

        return jsonify({
            "status": "error",
            "message": "Please upload a KML or KMZ file"
        }), 400

    # ---------------------------------------
    # Save uploaded file
    # ---------------------------------------

    unique_name = (
        str(uuid.uuid4())
        + "_"
        + file.filename
    )

    input_path = os.path.join(
        UPLOAD_FOLDER,
        unique_name
    )

    file.save(input_path)

    try:

        # ---------------------------------------
        # STEP 1: Parse KML
        # ---------------------------------------

        contours = parse_kml(
            input_path
        )

        if not contours:

            return jsonify({
                "status": "error",
                "message": "No contour data found"
            }), 400

        elevations = [
            contour["elevation"]
            for contour in contours
        ]

        # ---------------------------------------
        # STEP 2: Terrain
        # ---------------------------------------

        terrain = create_elevation_grid(
            contours,
            grid_size=150
        )

        # ---------------------------------------
        # STEP 3: Slope
        # ---------------------------------------

        slope = calculate_slope(
            terrain
        )

        # ---------------------------------------
        # STEP 4: Best pond
        # ---------------------------------------

        best = find_best_pond_candidate(
            terrain
        )

        # ---------------------------------------
        # STEP 5: Pond coordinates
        # ---------------------------------------

        latitude, longitude = grid_cell_to_latlon(
            terrain,
            best["row"],
            best["col"]
        )

        # ---------------------------------------
        # STEP 6: Catchment
        # ---------------------------------------

        catchment_result = calculate_catchment_area(
            terrain,
            best["row"],
            best["col"]
        )

        # ---------------------------------------
        # STEP 7: GeoJSON
        # ---------------------------------------

        output_name = (
            str(uuid.uuid4())
            + "_catchment.geojson"
        )

        output_path = os.path.join(
            RESULT_FOLDER,
            output_name
        )

        create_catchment_geojson(
            terrain,
            catchment_result["catchment"],
            best["row"],
            best["col"],
            output_path
        )

        # ---------------------------------------
        # Final response
        # ---------------------------------------

        return jsonify({

            "status": "success",

            "input": {
                "filename": file.filename,
                "total_contours": len(contours),
                "minimum_elevation_m": min(elevations),
                "maximum_elevation_m": max(elevations)
            },

            "terrain": {
                "epsg": terrain["epsg"],
                "width_m": round(
                    terrain["width_m"],
                    2
                ),
                "height_m": round(
                    terrain["height_m"],
                    2
                ),
                "grid_size": list(
                    terrain["elevation"].shape
                )
            },

            "slope": {
                "minimum_degrees": round(
                    float(slope.min()),
                    2
                ),
                "maximum_degrees": round(
                    float(slope.max()),
                    2
                ),
                "average_degrees": round(
                    float(slope.mean()),
                    2
                )
            },

            "pond": {
                "latitude": latitude,
                "longitude": longitude,
                "elevation_m": best["elevation"],
                "slope_degrees": best["slope"],
                "flow_accumulation_cells":
                    best["flow_accumulation"],
                "suitability_score":
                    best["suitability_score"]
            },

            "catchment": {
                "cells":
                    catchment_result[
                        "catchment_cells"
                    ],
                "area_m2":
                    round(
                        catchment_result[
                            "area_m2"
                        ],
                        2
                    ),
                "area_hectares":
                    round(
                        catchment_result[
                            "area_hectares"
                        ],
                        2
                    )
            },

            "output": {
                "geojson": output_path
            }
        })

    except Exception as error:

        return jsonify({
            "status": "error",
            "message": str(error)
        }), 500

@app.route("/geojson/<filename>", methods=["GET"])
def geojson(filename):

    file_path = os.path.join(
        RESULT_FOLDER,
        filename
    )

    if not os.path.exists(file_path):
        return jsonify({
            "status": "error",
            "message": "GeoJSON file not found"
        }), 404

    return send_file(
        file_path,
        mimetype="application/geo+json"
    )

@app.route(
    "/download/<filename>",
    methods=["GET"]
)
def download(filename):

    file_path = os.path.join(
        RESULT_FOLDER,
        filename
    )

    if not os.path.exists(file_path):

        return jsonify({
            "status": "error",
            "message": "File not found"
        }), 404

    return send_file(
        file_path,
        as_attachment=True
    )


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )

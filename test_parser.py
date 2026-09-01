import numpy as np

from services.kml_parser import parse_kml

from services.terrain import (
    create_elevation_grid,
    calculate_slope,
    find_pond_candidates,
    calculate_flow_accumulation,
    find_best_pond_candidate,
    grid_cell_to_latlon,
calculate_catchment_area,
create_catchment_geojson
)


file_path = "uploads/contours_1m.kml"


# ---------------------------------------
# STEP 1: Parse KML
# ---------------------------------------

contours = parse_kml(file_path)

print("========== KML ANALYSIS ==========")
print("Total contours:", len(contours))

elevations = [
    contour["elevation"]
    for contour in contours
]

print(
    "Minimum contour elevation:",
    min(elevations)
)

print(
    "Maximum contour elevation:",
    max(elevations)
)


# ---------------------------------------
# STEP 2: Create terrain model
# ---------------------------------------

print("\n========== TERRAIN MODEL ==========")

terrain = create_elevation_grid(
    contours,
    grid_size=150
)

print(
    "Coordinate system EPSG:",
    terrain["epsg"]
)

print(
    "Terrain width:",
    round(terrain["width_m"], 2),
    "meters"
)

print(
    "Terrain height:",
    round(terrain["height_m"], 2),
    "meters"
)

print(
    "Grid size:",
    terrain["elevation"].shape
)

print(
    "Grid minimum elevation:",
    round(terrain["min_elevation"], 2)
)

print(
    "Grid maximum elevation:",
    round(terrain["max_elevation"], 2)
)


# ---------------------------------------
# STEP 3: Calculate slope
# ---------------------------------------

print("\n========== SLOPE ANALYSIS ==========")

slope = calculate_slope(terrain)

print(
    "Minimum slope:",
    round(float(np.min(slope)), 2),
    "degrees"
)

print(
    "Maximum slope:",
    round(float(np.max(slope)), 2),
    "degrees"
)

print(
    "Average slope:",
    round(float(np.mean(slope)), 2),
    "degrees"
)


# ---------------------------------------
# STEP 4: Find pond candidates
# ---------------------------------------

print("\n========== POND CANDIDATES ==========")

candidates = find_pond_candidates(terrain)

print(
    "Candidate cells found:",
    len(candidates)
)

if candidates:

    candidates.sort(
        key=lambda item: item["elevation"]
    )

    print("\nBest 10 candidate cells:")

    for candidate in candidates[:10]:

        print(
            "Row:",
            candidate["row"],
            "Column:",
            candidate["col"],
            "Elevation:",
            round(candidate["elevation"], 2),
            "Slope:",
            round(candidate["slope"], 2),
            "degrees"
        )


# ---------------------------------------
# STEP 5: Flow accumulation
# ---------------------------------------

print("\n========== FLOW ANALYSIS ==========")

flow_accumulation = calculate_flow_accumulation(
    terrain["elevation"]
)

print(
    "Maximum flow accumulation:",
    round(
        float(np.max(flow_accumulation)),
        2
    )
)

print(
    "Average flow accumulation:",
    round(
        float(np.mean(flow_accumulation)),
        2
    )
)


# ---------------------------------------
# STEP 6: Best pond candidate
# ---------------------------------------

print("\n========== BEST POND LOCATION ==========")

best = find_best_pond_candidate(terrain)

print(
    "Grid row:",
    best["row"]
)

print(
    "Grid column:",
    best["col"]
)

print(
    "Elevation:",
    round(best["elevation"], 2),
    "m"
)

print(
    "Slope:",
    round(best["slope"], 2),
    "degrees"
)

print(
    "Flow accumulation:",
    round(best["flow_accumulation"], 2)
)

print(
    "Suitability score:",
    round(best["suitability_score"], 4)
)


# ---------------------------------------
# STEP 7: Convert grid cell to coordinates
# ---------------------------------------

latitude, longitude = grid_cell_to_latlon(
    terrain,
    best["row"],
    best["col"]
)

print("\n========== POND COORDINATES ==========")

print(
    "Latitude:",
    latitude
)

print(
    "Longitude:",
    longitude
)

# ---------------------------------------
# STEP 8: Catchment area
# ---------------------------------------

print("\n========== CATCHMENT ANALYSIS ==========")

catchment_result = calculate_catchment_area(
    terrain,
    best["row"],
    best["col"]
)

print(
    "Catchment cells:",
    catchment_result["catchment_cells"]
)

print(
    "Cell width:",
    round(
        catchment_result["cell_width_m"],
        2
    ),
    "meters"
)

print(
    "Cell height:",
    round(
        catchment_result["cell_height_m"],
        2
    ),
    "meters"
)

print(
    "Area of one cell:",
    round(
        catchment_result["cell_area_m2"],
        2
    ),
    "m²"
)

print(
    "Catchment area:",
    round(
        catchment_result["area_m2"],
        2
    ),
    "m²"
)

print(
    "Catchment area:",
    round(
        catchment_result["area_hectares"],
        2
    ),
    "hectares"
)

# ---------------------------------------
# STEP 9: Create GeoJSON
# ---------------------------------------

print("\n========== GEOJSON OUTPUT ==========")

output_file = "results/catchment.geojson"

create_catchment_geojson(
    terrain,
    catchment_result["catchment"],
    best["row"],
    best["col"],
    output_file
)

print(
    "GeoJSON created:",
    output_file
)

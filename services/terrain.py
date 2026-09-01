import math

import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from scipy.interpolate import griddata


def choose_utm_zone(longitude):
    """
    Automatically determine the UTM zone from longitude.
    """
    return int((longitude + 180) / 6) + 1


def project_contours(contours):
    """
    Convert longitude/latitude coordinates to a local
    metric CRS (UTM) automatically.
    """

    points = []
    elevations = []

    for contour in contours:
        elevation = contour["elevation"]

        for longitude, latitude in contour["coordinates"]:
            points.append(Point(longitude, latitude))
            elevations.append(elevation)

    if not points:
        raise ValueError("No contour points found.")

    # Find the approximate center of the input data
    mean_longitude = np.mean([point.x for point in points])
    mean_latitude = np.mean([point.y for point in points])

    zone = choose_utm_zone(mean_longitude)

    if mean_latitude >= 0:
        epsg = 32600 + zone
    else:
        epsg = 32700 + zone

    gdf = gpd.GeoDataFrame(
        {
            "elevation": elevations
        },
        geometry=points,
        crs="EPSG:4326"
    )

    projected = gdf.to_crs(epsg=epsg)

    x = projected.geometry.x.to_numpy()
    y = projected.geometry.y.to_numpy()
    z = projected["elevation"].to_numpy()

    return x, y, z, epsg


def create_elevation_grid(
    contours,
    grid_size=150
):
    """
    Interpolate contour elevations onto a regular terrain grid.
    """

    x, y, z, epsg = project_contours(contours)

    # Remove duplicate points
    points = np.column_stack((x, y))

    unique_points, indices = np.unique(
        points,
        axis=0,
        return_index=True
    )

    x = unique_points[:, 0]
    y = unique_points[:, 1]
    z = z[indices]

    min_x = np.min(x)
    max_x = np.max(x)
    min_y = np.min(y)
    max_y = np.max(y)

    grid_x = np.linspace(
        min_x,
        max_x,
        grid_size
    )

    grid_y = np.linspace(
        min_y,
        max_y,
        grid_size
    )

    mesh_x, mesh_y = np.meshgrid(
        grid_x,
        grid_y
    )

    # Linear interpolation from contour elevations
    grid_z = griddata(
        (x, y),
        z,
        (mesh_x, mesh_y),
        method="linear"
    )

    # Fill areas outside the convex hull using nearest neighbour
    missing = np.isnan(grid_z)

    if np.any(missing):
        nearest = griddata(
            (x, y),
            z,
            (mesh_x[missing], mesh_y[missing]),
            method="nearest"
        )

        grid_z[missing] = nearest

    return {
        "x": mesh_x,
        "y": mesh_y,
        "elevation": grid_z,
        "epsg": epsg,
        "min_elevation": float(np.min(grid_z)),
        "max_elevation": float(np.max(grid_z)),
        "width_m": float(max_x - min_x),
        "height_m": float(max_y - min_y)
    }

def calculate_slope(terrain):
    """
    Calculate terrain slope in degrees from the elevation grid.
    """

    elevation = terrain["elevation"]
    x = terrain["x"]
    y = terrain["y"]

    # Grid spacing in meters
    dx = float(np.mean(np.diff(x[0, :])))
    dy = float(np.mean(np.diff(y[:, 0])))

    # Calculate elevation gradients
    dz_dy, dz_dx = np.gradient(
        elevation,
        dy,
        dx
    )

    # Gradient magnitude
    gradient = np.sqrt(
        dz_dx ** 2 +
        dz_dy ** 2
    )

    # Convert to degrees
    slope_degrees = np.degrees(
        np.arctan(gradient)
    )

    return slope_degrees

def find_pond_candidates(terrain):
    """
    Identify potential pond locations using:
    - lower elevation
    - relatively gentle slope
    """

    elevation = terrain["elevation"]

    slope = calculate_slope(terrain)

    # Use the lower 30% of terrain elevations
    elevation_threshold = np.percentile(
        elevation,
        30
    )

    # Prefer gentle slopes below 10 degrees
    slope_threshold = 10.0

    candidate_mask = (
        (elevation <= elevation_threshold)
        &
        (slope <= slope_threshold)
    )

    candidate_indices = np.argwhere(
        candidate_mask
    )

    candidates = []

    for row, col in candidate_indices:

        candidates.append({
            "row": int(row),
            "col": int(col),
            "elevation": float(
                elevation[row, col]
            ),
            "slope": float(
                slope[row, col]
            )
        })

    return candidates

def calculate_flow_direction(elevation):
    """
    Calculate D8 flow direction.

    Each cell flows toward its lowest neighboring
    cell if that neighbor is lower.
    """

    rows, cols = elevation.shape

    flow_to = np.full(
        (rows, cols, 2),
        -1,
        dtype=int
    )

    # 8 neighboring cells
    neighbors = [
        (-1, -1),
        (-1,  0),
        (-1,  1),
        ( 0, -1),
        ( 0,  1),
        ( 1, -1),
        ( 1,  0),
        ( 1,  1)
    ]

    for row in range(rows):

        for col in range(cols):

            current = elevation[row, col]

            best_elevation = current
            best_row = -1
            best_col = -1

            for dr, dc in neighbors:

                nr = row + dr
                nc = col + dc

                if (
                    nr < 0
                    or nr >= rows
                    or nc < 0
                    or nc >= cols
                ):
                    continue

                neighbor_elevation = elevation[nr, nc]

                if neighbor_elevation < best_elevation:

                    best_elevation = neighbor_elevation
                    best_row = nr
                    best_col = nc

            flow_to[row, col] = (
                best_row,
                best_col
            )

    return flow_to


def calculate_flow_accumulation(elevation):
    """
    Calculate the number of upstream grid cells
    contributing flow to each cell.
    """

    rows, cols = elevation.shape

    flow_to = calculate_flow_direction(
        elevation
    )

    accumulation = np.ones(
        (rows, cols),
        dtype=float
    )

    # Process cells from high to low elevation
    cells = [
        (row, col)
        for row in range(rows)
        for col in range(cols)
    ]

    cells.sort(
        key=lambda cell: elevation[
            cell[0],
            cell[1]
        ],
        reverse=True
    )

    for row, col in cells:

        target_row = flow_to[
            row,
            col,
            0
        ]

        target_col = flow_to[
            row,
            col,
            1
        ]

        if (
            target_row >= 0
            and target_col >= 0
        ):

            accumulation[
                target_row,
                target_col
            ] += accumulation[
                row,
                col
            ]

    return accumulation


def find_best_pond_candidate(terrain):
    """
    Find a pond candidate using elevation, slope,
    and flow accumulation.

    The score favors:
    - lower elevation
    - gentle slope
    - high flow accumulation
    """

    elevation = terrain["elevation"]

    slope = calculate_slope(
        terrain
    )

    accumulation = calculate_flow_accumulation(
        elevation
    )

    # Normalize elevation
    elevation_range = (
        np.max(elevation)
        - np.min(elevation)
    )

    if elevation_range == 0:
        elevation_score = np.ones_like(
            elevation
        )
    else:
        elevation_score = (
            np.max(elevation)
            - elevation
        ) / elevation_range

    # Prefer gentle slopes
    slope_score = 1 / (
        1 + slope
    )

    # Log transform flow accumulation
    flow_score = np.log1p(
        accumulation
    )

    flow_score = (
        flow_score
        / np.max(flow_score)
    )

    # Combined suitability score
    score = (
        0.30 * elevation_score
        + 0.30 * slope_score
        + 0.40 * flow_score
    )

    # Avoid extreme slopes
    score[slope > 15] = -1

    # Best cell
    best_index = np.unravel_index(
        np.argmax(score),
        score.shape
    )

    row, col = best_index

    return {
        "row": int(row),
        "col": int(col),
        "elevation": float(
            elevation[row, col]
        ),
        "slope": float(
            slope[row, col]
        ),
        "flow_accumulation": float(
            accumulation[row, col]
        ),
        "suitability_score": float(
            score[row, col]
        ),
        "flow_accumulation_grid": accumulation
    }

def grid_cell_to_latlon(terrain, row, col):
    """
    Convert a terrain grid cell from projected coordinates
    back to latitude/longitude.
    """

    x = float(terrain["x"][row, col])
    y = float(terrain["y"][row, col])

    point = gpd.GeoDataFrame(
        geometry=[Point(x, y)],
        crs=f"EPSG:{terrain['epsg']}"
    )

    geographic = point.to_crs("EPSG:4326")

    longitude = float(geographic.geometry.iloc[0].x)
    latitude = float(geographic.geometry.iloc[0].y)

    return latitude, longitude

def find_catchment_cells(elevation, pond_row, pond_col):
    """
    Find all cells whose drainage path eventually reaches
    the selected pond cell.
    """

    rows, cols = elevation.shape

    flow_to = calculate_flow_direction(elevation)

    catchment = np.zeros(
        (rows, cols),
        dtype=bool
    )

    # The pond itself belongs to the catchment
    catchment[pond_row, pond_col] = True

    # Check every cell
    for row in range(rows):

        for col in range(cols):

            current_row = row
            current_col = col

            visited = set()

            while True:

                # Avoid infinite loops
                if (current_row, current_col) in visited:
                    break

                visited.add(
                    (current_row, current_col)
                )

                # Reached the pond
                if (
                    current_row == pond_row
                    and current_col == pond_col
                ):
                    catchment[row, col] = True
                    break

                next_row = flow_to[
                    current_row,
                    current_col,
                    0
                ]

                next_col = flow_to[
                    current_row,
                    current_col,
                    1
                ]

                # No lower neighbor / outlet
                if (
                    next_row < 0
                    or next_col < 0
                ):
                    break

                current_row = int(next_row)
                current_col = int(next_col)

    return catchment


def calculate_catchment_area(
    terrain,
    pond_row,
    pond_col
):
    """
    Calculate catchment area contributing to the pond.
    """

    elevation = terrain["elevation"]

    catchment = find_catchment_cells(
        elevation,
        pond_row,
        pond_col
    )

    # Terrain dimensions
    width_m = terrain["width_m"]
    height_m = terrain["height_m"]

    rows, cols = elevation.shape

    # Approximate area represented by each grid cell
    cell_width = width_m / (cols - 1)
    cell_height = height_m / (rows - 1)

    cell_area_m2 = (
        cell_width * cell_height
    )

    catchment_cells = int(
        np.sum(catchment)
    )

    area_m2 = (
        catchment_cells
        * cell_area_m2
    )

    area_hectares = (
        area_m2 / 10000.0
    )

    return {
        "catchment": catchment,
        "catchment_cells": catchment_cells,
        "cell_width_m": cell_width,
        "cell_height_m": cell_height,
        "cell_area_m2": cell_area_m2,
        "area_m2": area_m2,
        "area_hectares": area_hectares
    }

def create_catchment_geojson(
    terrain,
    catchment,
    pond_row,
    pond_col,
    output_file
):
    """
    Create a GeoJSON file containing:
    - catchment boundary
    - pond location
    """

    from shapely.geometry import Polygon, Point, mapping
    import json

    rows, cols = catchment.shape

    # Find catchment cells
    cell_positions = []

    for row in range(rows):
        for col in range(cols):
            if catchment[row, col]:
                cell_positions.append((row, col))

    if not cell_positions:
        raise ValueError("No catchment cells found.")

    # Grid coordinates
    x_grid = terrain["x"]
    y_grid = terrain["y"]

    # Create polygons for catchment cells
    polygons = []

    dx = terrain["width_m"] / (cols - 1)
    dy = terrain["height_m"] / (rows - 1)

    for row, col in cell_positions:

        x = x_grid[row, col]
        y = y_grid[row, col]

        polygon = Polygon([
            (x - dx / 2, y - dy / 2),
            (x + dx / 2, y - dy / 2),
            (x + dx / 2, y + dy / 2),
            (x - dx / 2, y + dy / 2),
            (x - dx / 2, y - dy / 2)
        ])

        polygons.append(polygon)

    # Merge cells into one geometry
    from shapely.ops import unary_union

    catchment_polygon = unary_union(polygons)

    # Pond point
    pond_x = x_grid[pond_row, pond_col]
    pond_y = y_grid[pond_row, pond_col]

    pond_point = Point(
        pond_x,
        pond_y
    )

    # Convert projected coordinates to WGS84
    pond_gdf = gpd.GeoDataFrame(
        geometry=[pond_point],
        crs=f"EPSG:{terrain['epsg']}"
    )

    catchment_gdf = gpd.GeoDataFrame(
        geometry=[catchment_polygon],
        crs=f"EPSG:{terrain['epsg']}"
    )

    pond_gdf = pond_gdf.to_crs("EPSG:4326")
    catchment_gdf = catchment_gdf.to_crs("EPSG:4326")

    pond_geometry = mapping(
        pond_gdf.geometry.iloc[0]
    )

    catchment_geometry = mapping(
        catchment_gdf.geometry.iloc[0]
    )

    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "type": "pond",
                    "elevation_m": float(
                        terrain["elevation"][
                            pond_row,
                            pond_col
                        ]
                    )
                },
                "geometry": pond_geometry
            },
            {
                "type": "Feature",
                "properties": {
                    "type": "catchment"
                },
                "geometry": catchment_geometry
            }
        ]
    }

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            geojson,
            file,
            indent=2
        )

    return output_file

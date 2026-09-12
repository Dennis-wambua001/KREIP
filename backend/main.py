import json
import io
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import rasterio.mask
from rasterio.windows import from_bounds
from PIL import Image
from scipy.spatial import cKDTree
from shapely.geometry import Point

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from src.config import (
    PROCESSED_DATA_DIR,
    STUDY_AREA_GPKG,
    ECONOMIC_ACTIVITY_RASTER,
    PROJECTED_CRS,
    GEOGRAPHIC_CRS,
    HUFF_BETA_EXPONENT
)


app = FastAPI(
    title="KREIP - Kenya Retail Expansion Intelligence Platform API",
    description="Geospatial analytics, Huff gravity modeling, cannibalization simulation, and forecasting backend.",
    version="1.0.0"
)


# ============================================================================
# CORS
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# FRONTEND STATIC FILES
# ============================================================================

app.mount("/css", StaticFiles(directory="frontend/css"), name="css")
app.mount("/js", StaticFiles(directory="frontend/js"), name="js")
app.mount(
    "/assets",
    StaticFiles(directory="frontend/assets", check_dir=False),
    name="assets"
)


# ============================================================================
# DATA PATHS
# ============================================================================

DATA_PATHS = {
    "boundaries": PROCESSED_DATA_DIR / "subcounties.gpkg",
    "population": PROCESSED_DATA_DIR / "worldpop_population_grid.geojson",
    "population_raster": PROCESSED_DATA_DIR / "population" / "population_2020.tif",
    "retail": Path(
        r"D:\ Documents\Anga Geosystems\Projects\AGS-005\kreip_platform\data\processed\retail_master_clean.gpkg"
    ),
    # Roads remain in the raw folder
    "roads": Path(
        r"D:\ Documents\Anga Geosystems\Projects\AGS-005\kreip_platform\data\raw\roads.gpkg"
    ),
    "transport": PROCESSED_DATA_DIR / "matatu_stages.gpkg",
    "lulc": PROCESSED_DATA_DIR / "lulc" / "lulc_2025.tif",
    "huff": PROCESSED_DATA_DIR / "huff_results.parquet",
    "market_gap": PROCESSED_DATA_DIR / "market_dominance.gpkg",
    "candidates": PROCESSED_DATA_DIR / "store_simulations.gpkg",
    "top50": PROCESSED_DATA_DIR / "top_50_opportunity_locations.gpkg",
    "forecast": PROCESSED_DATA_DIR / "grid_forecasting_opportunity.gpkg",
    "reports_csv": PROCESSED_DATA_DIR / "candidate_reports" / "candidate_narrative_summary.csv",
    "location_intelligence": PROCESSED_DATA_DIR / "location_intelligence.gpkg",
}


# ============================================================================
# STUDY-AREA GEOMETRY
# ============================================================================

def get_study_area_geometry():
    """
    Loads the master study-area polygon from counties.gpkg.

    All geometries in the study-area file are dissolved into one unified
    geometry.

    IMPORTANT:
    This geometry is used only as a spatial filter/clipping mask.
    It is NOT returned as an additional map layer.
    """
    boundaries_path = DATA_PATHS["boundaries"]

    if not boundaries_path.exists():
        raise FileNotFoundError(
            f"Study-area boundary not found: {boundaries_path}"
        )

    study = gpd.read_file(boundaries_path)

    if study.empty:
        raise ValueError("Study-area boundary file contains no features.")

    # Remove invalid/null geometries
    study = study[study.geometry.notna()].copy()
    study = study[~study.geometry.is_empty].copy()

    if study.empty:
        raise ValueError("Study-area boundary contains no valid geometries.")

    # Dissolve all polygons into one study-area geometry
    if hasattr(study.geometry, "union_all"):
        study_geometry = study.geometry.union_all()
    else:
        study_geometry = study.geometry.unary_union

    return study_geometry, study.crs


# ============================================================================
# GENERAL VECTOR CLIPPING
# ============================================================================

def clip_to_boundaries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Strictly limits vector data to the actual study-area polygon.
    """
    if gdf is None or gdf.empty:
        return gdf

    try:
        study_geometry, study_crs = get_study_area_geometry()

        if gdf.crs is None:
            print("⚠️ Layer has no CRS. Assuming EPSG:4326.")
            gdf = gdf.set_crs("EPSG:4326")

        study_geometry = (
            gpd.GeoSeries([study_geometry], crs=study_crs)
            .to_crs(gdf.crs)
            .iloc[0]
        )

        gdf = gdf[gdf.geometry.notna()].copy()
        gdf = gdf[~gdf.geometry.is_empty].copy()

        if gdf.empty:
            return gdf

        geometry_types = set(gdf.geometry.geom_type.dropna().unique())
        point_types = {"Point", "MultiPoint"}

        if geometry_types.issubset(point_types):
            point_mask = gdf.geometry.within(study_geometry)
            clipped = gdf.loc[point_mask].copy()
            print(f"📍 Point layer clipped: {len(gdf):,} → {len(clipped):,}")
            return clipped

        study_clip = gpd.GeoDataFrame(
            {"study_area": [1]},
            geometry=[study_geometry],
            crs=gdf.crs
        )

        clipped = gpd.clip(gdf, study_clip)
        print(f"🗺️ Vector layer clipped: {len(gdf):,} → {len(clipped):,}")
        return clipped

    except Exception as e:
        print(f"⚠️ Study-area clipping error: {e}")
        return gdf


# ============================================================================
# GENERAL GEOJSON LOADER
# ============================================================================

def load_gpkg_as_geojson(path: Path, filter_col=None, filter_val=None, clip=True):
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}

    if path.suffix.lower() == ".geojson":
        try:
            gdf = gpd.read_file(path)
            if filter_col and filter_val and filter_col in gdf.columns:
                gdf = gdf[gdf[filter_col] == filter_val]

            if clip:
                gdf = clip_to_boundaries(gdf)

            if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")

            return json.loads(gdf.to_json(drop_id=True))

        except Exception as e:
            print(f"⚠️ GeoJSON loading error: {e}")
            return {"type": "FeatureCollection", "features": []}

    try:
        gdf = gpd.read_file(path)
    except Exception as e:
        print(f"⚠️ Failed to read {path}: {e}")
        return {"type": "FeatureCollection", "features": []}

    if filter_col and filter_val and filter_col in gdf.columns:
        gdf = gdf[gdf[filter_col] == filter_val].copy()

    if clip:
        gdf = clip_to_boundaries(gdf)

    if gdf.empty:
        return {"type": "FeatureCollection", "features": []}

    if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    return json.loads(gdf.to_json(drop_id=True))


# ============================================================================
# OPTIMIZED ROAD LOADER
# ============================================================================

def load_roads_optimized() -> dict:
    roads_path = DATA_PATHS["roads"]
    boundaries_path = DATA_PATHS["boundaries"]

    if not roads_path.exists():
        print(f"❌ Roads file not found: {roads_path}")
        return {"type": "FeatureCollection", "features": []}

    if not boundaries_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Study-area boundary file is missing: {boundaries_path}"
        )

    print("🛣️ Loading optimized road network...")

    study_gdf = gpd.read_file(boundaries_path)

    if study_gdf.empty:
        return {"type": "FeatureCollection", "features": []}

    study_gdf = study_gdf[study_gdf.geometry.notna()].copy()
    study_gdf = study_gdf[~study_gdf.geometry.is_empty].copy()

    if study_gdf.empty:
        return {"type": "FeatureCollection", "features": []}

    if hasattr(study_gdf.geometry, "union_all"):
        study_geometry = study_gdf.geometry.union_all()
    else:
        study_geometry = study_gdf.geometry.unary_union

    try:
        roads_info = gpd.read_file(roads_path, rows=1)
        roads_crs = roads_info.crs
    except Exception as e:
        print(f"⚠️ Could not inspect road CRS: {e}")
        roads_crs = None

    if roads_crs is None:
        raise HTTPException(
            status_code=500,
            detail="Road dataset has no CRS defined."
        )

    study_for_roads = (
        gpd.GeoSeries([study_geometry], crs=study_gdf.crs)
        .to_crs(roads_crs)
    )

    road_mask = study_for_roads.iloc[0]

    try:
        roads_gdf = gpd.read_file(roads_path, mask=road_mask)
    except Exception as e:
        print(f"⚠️ Spatial road read failed: {e}")
        roads_gdf = gpd.read_file(roads_path)

    if roads_gdf.empty:
        print("⚠️ No roads intersect the study area.")
        return {"type": "FeatureCollection", "features": []}

    print(f"📍 Roads intersecting study area: {len(roads_gdf):,}")

    if roads_gdf.crs is None:
        roads_gdf = roads_gdf.set_crs(roads_crs)

    study_polygon_gdf = gpd.GeoDataFrame(
        {"id": [1]},
        geometry=[road_mask],
        crs=roads_gdf.crs
    )

    try:
        roads_gdf = gpd.clip(roads_gdf, study_polygon_gdf)
    except Exception as e:
        print(f"⚠️ Exact road clipping failed: {e}")

    if roads_gdf.empty:
        return {"type": "FeatureCollection", "features": []}

    roads_gdf = roads_gdf[roads_gdf.geometry.notna()].copy()
    roads_gdf = roads_gdf[~roads_gdf.geometry.is_empty].copy()

    try:
        metric_crs = roads_gdf.estimate_utm_crs()
        if metric_crs is None:
            metric_crs = "EPSG:32737"
    except Exception:
        metric_crs = "EPSG:32737"

    roads_metric = roads_gdf.to_crs(metric_crs)

    roads_metric["geometry"] = roads_metric.geometry.simplify(
        tolerance=8.0,
        preserve_topology=False
    )

    roads_metric = roads_metric[roads_metric.geometry.notna()].copy()
    roads_metric = roads_metric[~roads_metric.geometry.is_empty].copy()

    preferred_columns = [
        "name", "highway", "ref", "surface", "lanes", "oneway", "maxspeed", "geometry"
    ]

    available_columns = [
        column for column in preferred_columns if column in roads_metric.columns
    ]

    if "geometry" not in available_columns:
        available_columns.append("geometry")

    roads_metric = roads_metric[available_columns].copy()

    roads_wgs84 = roads_metric.to_crs("EPSG:4326")

    geojson = json.loads(roads_wgs84.to_json(drop_id=True))

    print(f"✅ Optimized road features: {len(geojson.get('features', [])):,}")

    return geojson


# ============================================================================
# COLOR UTILITY
# ============================================================================

def hex_to_rgba(hex_str, alpha=255):
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


# ============================================================================
# TURBO PALETTE
# ============================================================================

TURBO_HEX_PALETTE = [
    "#19065e", "#1f58e6", "#1bc7e5", "#15df1f", "#c3ef2c",
    "#d2e711", "#f2cb1b", "#e0740f", "#df120b", "#490f07"
]


# ============================================================================
# ROOT
# ============================================================================

@app.get("/")
def serve_frontend():
    index_path = Path("index.html")
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "status": "error",
        "message": "index.html not found in project root."
    }


# ============================================================================
# POPULATION RASTER
# ============================================================================

@app.get("/api/raster/population")
def get_population_raster():
    raster_path = DATA_PATHS["population_raster"]

    if not raster_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Processed population raster not found."
        )

    return FileResponse(
        raster_path,
        media_type="image/tiff",
        filename="population_2020.tif"
    )


# ============================================================================
# POPULATION VISUAL RASTER
# ============================================================================

@app.get("/api/raster/population-visual")
def get_population_visual_raster():
    raster_path = DATA_PATHS["population_raster"]
    boundaries_path = DATA_PATHS["boundaries"]

    if not raster_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Processed population raster not found."
        )

    with rasterio.open(raster_path) as src:
        if boundaries_path.exists():
            gdf = gpd.read_file(boundaries_path)
            if gdf.crs and gdf.crs != src.crs:
                gdf = gdf.to_crs(src.crs)

            geoms = [geom for geom in gdf.geometry if geom is not None]

            out_image, out_transform = rasterio.mask.mask(
                src,
                geoms,
                crop=True,
                nodata=np.nan
            )
            image_data = out_image[0].astype(np.float32)
        else:
            image_data = src.read(1).astype(np.float32)

        nodata_val = src.nodata
        if nodata_val is not None:
            image_data[image_data == nodata_val] = np.nan

        image_data[image_data < 0] = np.nan

        valid_data = image_data[~np.isnan(image_data)]
        height, width = image_data.shape
        rgba_img = np.zeros((height, width, 4), dtype=np.uint8)

        if valid_data.size > 0:
            percentiles = np.linspace(0, 100, 11)
            breaks = np.percentile(valid_data, percentiles)
            breaks[0] -= 1e-5
            breaks[-1] += 1e-5

            class_colors = [hex_to_rgba(h, alpha=255) for h in TURBO_HEX_PALETTE]

            binned_indices = np.digitize(
                image_data,
                breaks[1:-1],
                right=True
            )

            for class_idx, color in enumerate(class_colors):
                mask = (binned_indices == class_idx) & ~np.isnan(image_data)
                rgba_img[mask] = color

        img = Image.fromarray(rgba_img, mode="RGBA")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return Response(content=buffer.getvalue(), media_type="image/png")


# ============================================================================
# POPULATION LEGEND
# ============================================================================

@app.get("/api/raster/population-legend")
def get_population_legend():
    raster_path = DATA_PATHS["population_raster"]

    if not raster_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Processed population raster not found."
        )

    with rasterio.open(raster_path) as src:
        image_data = src.read(1).astype(np.float32)

        if src.nodata is not None:
            image_data[image_data == src.nodata] = np.nan

        image_data[image_data < 0] = np.nan

        valid_data = image_data[~np.isnan(image_data)]
        percentiles = np.linspace(0, 100, 11)
        breaks = np.percentile(valid_data, percentiles)

        legend_items = []
        for i in range(len(TURBO_HEX_PALETTE)):
            legend_items.append({
                "class": i + 1,
                "color": TURBO_HEX_PALETTE[i],
                "min": round(float(breaks[i]), 2),
                "max": round(float(breaks[i + 1]), 2)
            })

        return {
            "status": "success",
            "palette": "turbo",
            "mode": "quantile",
            "classes": legend_items
        }


# ============================================================================
# LULC RASTER
# ============================================================================

@app.get("/api/raster/lulc-visual")
def get_lulc_visual_raster(
    palette: str = Query(
        "standard",
        description="LULC color palette: standard or neon"
    )
):
    raster_path = DATA_PATHS["lulc"]
    boundaries_path = DATA_PATHS["boundaries"]

    if not raster_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Processed LULC raster not found."
        )

    palettes = {
        "standard": {
            0: hex_to_rgba("#193cd4", 255),
            1: hex_to_rgba("#1D662E", 255),
            2: hex_to_rgba("#97b470", 255),
            3: hex_to_rgba("#1cb5db", 255),
            4: hex_to_rgba("#eeea0d", 255),
            5: hex_to_rgba("#dba510", 255),
            6: hex_to_rgba("#c4281b", 255),
            7: hex_to_rgba("#c4beb6", 255),
            8: hex_to_rgba("#b39fe1", 255)
        },
        "neon": {
            0: hex_to_rgba("#00e5ff", 255),
            1: hex_to_rgba("#00ff80", 255),
            2: hex_to_rgba("#80ff00", 255),
            3: hex_to_rgba("#9370db", 255),
            4: hex_to_rgba("#ff8000", 255),
            5: hex_to_rgba("#ffff00", 255),
            6: hex_to_rgba("#ff0055", 255),
            7: hex_to_rgba("#d3d3d3", 255),
            8: hex_to_rgba("#ffffff", 255)
        }
    }

    selected_palette = palettes.get(
        palette.lower(),
        palettes["standard"]
    )

    with rasterio.open(raster_path) as src:
        if boundaries_path.exists():
            gdf = gpd.read_file(boundaries_path)
            if gdf.crs and gdf.crs != src.crs:
                gdf = gdf.to_crs(src.crs)

            geoms = [geom for geom in gdf.geometry if geom is not None]

            out_image, out_transform = rasterio.mask.mask(
                src,
                geoms,
                crop=True,
                nodata=255
            )
            image_data = out_image[0].astype(np.int32)
        else:
            image_data = src.read(1).astype(np.int32)

        height, width = image_data.shape
        rgba_img = np.zeros((height, width, 4), dtype=np.uint8)

        for class_val, rgba_color in selected_palette.items():
            class_mask = (image_data == class_val)
            rgba_img[class_mask] = rgba_color

        img = Image.fromarray(rgba_img, mode="RGBA")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return Response(
            content=buffer.getvalue(),
            media_type="image/png"
        )


# ============================================================================
# SUMMARY
# ============================================================================

@app.get("/api/summary")
def get_summary():
    top50_path = DATA_PATHS["top50"]
    retail_path = DATA_PATHS["retail"]
    transport_path = DATA_PATHS["transport"]

    total_candidates = 357
    top_score = 94.5

    if top50_path.exists():
        df = gpd.read_file(top50_path)
        total_candidates = len(df)

        if "current_opportunity" in df.columns:
            top_score = float(df["current_opportunity"].max())

    retail_count = 0
    supermarket_count = 0

    if retail_path.exists():
        retail_gdf = gpd.read_file(retail_path)
        retail_count = len(retail_gdf)

        if "retail_type" in retail_gdf.columns:
            supermarket_count = len(
                retail_gdf[retail_gdf["retail_type"] == "supermarket"]
            )

    transport_count = (
        len(gpd.read_file(transport_path))
        if transport_path.exists()
        else 324
    )

    return {
        "status": "success",
        "study_area": "Nairobi Metropolitan Region",
        "total_population": 12850000,
        "total_retail_outlets": retail_count,
        "supermarkets": supermarket_count,
        "transport_stages": transport_count,
        "total_candidates": total_candidates,
        "top_opportunity_score": top_score
    }


# ============================================================================
# BOUNDARIES
# ============================================================================

@app.get("/api/boundaries")
def get_boundaries():
    return load_gpkg_as_geojson(
        DATA_PATHS["boundaries"],
        clip=False
    )


@app.get("/api/boundaries/subcounties")
def get_admin_boundaries():
    return load_gpkg_as_geojson(
        DATA_PATHS["boundaries"],
        clip=False
    )


@app.get("/api/boundaries/study-area")
def get_study_area_boundary():
    """
    Serves the master analytical study area boundary GeoPackage as a GeoJSON FeatureCollection.
    """
    if not STUDY_AREA_GPKG.exists():
        raise HTTPException(
            status_code=404,
            detail="Study area GeoPackage not found on disk. Run build_study_area first."
        )

    try:
        gdf = gpd.read_file(STUDY_AREA_GPKG)

        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")

        return Response(content=gdf.to_json(), media_type="application/json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# POPULATION
# ============================================================================

@app.get("/api/population")
def get_population():
    return load_gpkg_as_geojson(DATA_PATHS["population"])


# ============================================================================
# RETAIL
# ============================================================================

@app.get("/api/retail/shops")
def get_shops():
    path = DATA_PATHS["retail"]

    if not path.exists():
        return {"type": "FeatureCollection", "features": []}

    try:
        gdf = gpd.read_file(path)

        gdf = gdf[
            gdf.geometry.geom_type.isin(["Point", "MultiPoint"])
        ].copy()

        gdf = gdf[gdf["retail_type"] != "supermarket"].copy()

        gdf = clip_to_boundaries(gdf)

        if gdf.empty:
            return {"type": "FeatureCollection", "features": []}

        if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")

        return json.loads(gdf.to_json(drop_id=True))

    except Exception as e:
        print(f"⚠️ Retail shops loading error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SUPERMARKETS
# ============================================================================

@app.get("/api/retail/supermarkets")
def get_supermarkets():
    path = DATA_PATHS["retail"]

    if not path.exists():
        return {"type": "FeatureCollection", "features": []}

    try:
        gdf = gpd.read_file(path)

        gdf = gdf[
            gdf.geometry.geom_type.isin(["Point", "MultiPoint"])
        ].copy()

        gdf = gdf[gdf["retail_type"] == "supermarket"].copy()

        gdf = clip_to_boundaries(gdf)

        if gdf.empty:
            return {"type": "FeatureCollection", "features": []}

        if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")

        return json.loads(gdf.to_json(drop_id=True))

    except Exception as e:
        print(f"⚠️ Supermarket loading error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ROADS
# ============================================================================

@app.get("/api/roads")
def get_roads():
    return load_roads_optimized()


# ============================================================================
# TRANSPORT
# ============================================================================

@app.get("/api/transport")
def get_transport():
    return load_gpkg_as_geojson(DATA_PATHS["transport"])


# ============================================================================
# LULC
# ============================================================================

@app.get("/api/lulc")
def get_lulc():
    return {
        "status": "success",
        "message": "LULC GeoTIFF served via raster endpoint."
    }


# ============================================================================
# TRAFFIC
# ============================================================================

@app.get("/api/traffic")
def get_economic_activity():

    raster_path = ECONOMIC_ACTIVITY_RASTER
    boundaries_path = DATA_PATHS["boundaries"]

    if not raster_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Economic activity raster not found: {raster_path}"
        )

    with rasterio.open(raster_path) as src:

        if boundaries_path.exists():

            study_gdf = gpd.read_file(boundaries_path)

            if study_gdf.crs and study_gdf.crs != src.crs:
                study_gdf = study_gdf.to_crs(src.crs)

            study_geometry = (
                study_gdf.geometry.union_all()
                if hasattr(study_gdf.geometry, "union_all")
                else study_gdf.geometry.unary_union
            )

            out_image, out_transform = rasterio.mask.mask(
                src,
                [study_geometry],
                crop=True,
                nodata=np.nan
            )

            image_data = out_image[0].astype(np.float32)
            bounds = rasterio.transform.array_bounds(
                image_data.shape[0],
                image_data.shape[1],
                out_transform
            )

        else:

            image_data = src.read(1).astype(np.float32)
            bounds = (
                src.bounds.bottom,
                src.bounds.left,
                src.bounds.top,
                src.bounds.right
            )

        nodata_value = src.nodata

        if nodata_value is not None:
            image_data[image_data == nodata_value] = np.nan

        valid = image_data[~np.isnan(image_data)]

        rgba = np.zeros(
            (image_data.shape[0], image_data.shape[1], 4),
            dtype=np.uint8
        )

        if valid.size > 0:

            low = float(np.nanpercentile(valid, 2))
            high = float(np.nanpercentile(valid, 98))

            if high <= low:
                high = low + 1

            normalized = np.clip(
                (image_data - low) / (high - low),
                0,
                1
            )

            rgba[..., 0] = (normalized * 255).astype(np.uint8)
            rgba[..., 1] = (normalized * 180).astype(np.uint8)
            rgba[..., 2] = 40
            rgba[..., 3] = np.where(
                np.isnan(image_data),
                0,
                220
            ).astype(np.uint8)

        image = Image.fromarray(rgba, mode="RGBA")

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)

        return Response(
            content=buffer.getvalue(),
            media_type="image/png"
        )

# ============================================================================
# HUFF
# ============================================================================

@app.get("/api/huff")
def get_huff_results():

    parquet_path = DATA_PATHS["huff"]

    if not parquet_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Huff results not found: {parquet_path}"
        )

    df = pd.read_parquet(parquet_path)

    return {
        "status": "success",
        "records": int(len(df)),
        "columns": list(df.columns),
        "results": df.to_dict(orient="records")
    }


# ============================================================================
# MARKET GAP
# ============================================================================

@app.get("/api/market-gap")
def get_market_gap():
    return load_gpkg_as_geojson(DATA_PATHS["market_gap"])


# ============================================================================
# CANDIDATES
# ============================================================================

@app.get("/api/candidates")
def get_candidates():
    return load_gpkg_as_geojson(DATA_PATHS["candidates"])


@app.get("/api/candidates/top50")
def get_top50_candidates():
    return load_gpkg_as_geojson(DATA_PATHS["top50"])


@app.get("/api/candidates/{candidate_id}")
def get_candidate_detail(candidate_id: str):
    path = DATA_PATHS["candidates"]

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Candidate dataset not found."
        )

    gdf = gpd.read_file(path)

    match = gdf[gdf["candidate_id"] == candidate_id]

    if match.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate {candidate_id} not found."
        )

    record = (
        match.iloc[0]
        .drop(labels=["geometry"])
        .to_dict()
    )

    return {
        "status": "success",
        "candidate_id": candidate_id,
        "attributes": record
    }


# ============================================================================
# FORECAST
# ============================================================================

@app.get("/api/forecast")
def get_forecast():

    path = DATA_PATHS["forecast"]

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Forecasting layer not found: {path}"
        )

    try:
        gdf = gpd.read_file(path)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read forecasting layer: {e}"
        )


    # ============================================================
    # REQUIRED FORECAST FIELDS
    # ============================================================

    required_columns = [

        # --------------------------------------------------------
        # Population forecast
        # --------------------------------------------------------

        "future_population_2026",
        "future_population_2027",
        "future_population_2028",
        "future_population_2029",
        "future_population_2030",

        # --------------------------------------------------------
        # Economic activity forecast
        # --------------------------------------------------------

        "future_economic_activity_2026",
        "future_economic_activity_2027",
        "future_economic_activity_2028",
        "future_economic_activity_2029",
        "future_economic_activity_2030",

        # --------------------------------------------------------
        # Accessibility forecast
        # --------------------------------------------------------

        "future_accessibility_2026",
        "future_accessibility_2027",
        "future_accessibility_2028",
        "future_accessibility_2029",
        "future_accessibility_2030",

        # --------------------------------------------------------
        # Retail pressure forecast
        # --------------------------------------------------------

        "future_retail_pressure_2026",
        "future_retail_pressure_2027",
        "future_retail_pressure_2028",
        "future_retail_pressure_2029",
        "future_retail_pressure_2030",

        # --------------------------------------------------------
        # Opportunity forecast
        # --------------------------------------------------------

        "future_opportunity_2026",
        "future_opportunity_2027",
        "future_opportunity_2028",
        "future_opportunity_2029",
        "future_opportunity_2030"
    ]


    # ============================================================
    # CHECK REQUIRED FIELDS
    # ============================================================

    missing = [
        col
        for col in required_columns
        if col not in gdf.columns
    ]


    if missing:

        raise HTTPException(
            status_code=500,
            detail=(
                "Forecasting layer is missing required "
                f"2026–2030 fields: {missing}"
            )
        )


    # ============================================================
    # CLIP TO KENYA / PROJECT BOUNDARIES
    # ============================================================

    gdf = clip_to_boundaries(gdf)


    # ============================================================
    # CONVERT TO WEB CRS
    # ============================================================

    if (
        gdf.crs
        and gdf.crs.to_string() != "EPSG:4326"
    ):

        gdf = gdf.to_crs("EPSG:4326")


    # ============================================================
    # RETURN FORECAST GEOJSON
    # ============================================================

    return json.loads(
        gdf.to_json(
            drop_id=True
        )
    )


# ============================================================================
# SIMULATION
# ============================================================================

@app.get("/api/simulation")
def run_simulation(
    lat: float = Query(
        ...,
        description="Proposed store latitude"
    ),
    lon: float = Query(
        ...,
        description="Proposed store longitude"
    ),
    size_sqm: float = Query(
        1500.0,
        description="Proposed store floor area in square metres"
    ),
    brand: str = Query(
        "Naivas",
        description="Existing brand to evaluate for cannibalization"
    )
):
    """
    Dynamic KREIP new-store simulation.

    Uses:
        - Population demand grid
        - Actual supermarket locations
        - Store attractiveness
        - Huff-style distance decay
        - Existing target-brand stores
        - Competitor locations

    Returns:
        - Total market population
        - Estimated catchment population
        - Captured population
        - Market capture
        - Cannibalization
        - Competitor impact
        - Recommendation
    """

    # ------------------------------------------------------------------------
    # LOCAL IMPORTS
    # ------------------------------------------------------------------------

    import numpy as np
    import pandas as pd
    import geopandas as gpd

    from scipy.spatial.distance import cdist
    from shapely.geometry import Point

    # ------------------------------------------------------------------------
    # PARAMETERS
    # ------------------------------------------------------------------------

    try:
        HUFF_BETA = float(HUFF_BETA_EXPONENT)
    except Exception:
        HUFF_BETA = 1.5

    MIN_DISTANCE_M = 50.0
    CATCHMENT_RADIUS_M = 5000.0
    CATCHMENT_DECAY_M = 2000.0
    STORE_SIZE_EXPONENT = 0.70

    # ------------------------------------------------------------------------
    # BASIC VALIDATION
    # ------------------------------------------------------------------------

    try:
        lat = float(lat)
        lon = float(lon)
        size_sqm = float(size_sqm)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Latitude, longitude and store size must be numeric."
        )

    if not np.isfinite(lat) or not np.isfinite(lon):
        raise HTTPException(
            status_code=400,
            detail="Latitude and longitude must be valid numbers."
        )

    if lat < -90 or lat > 90:
        raise HTTPException(
            status_code=400,
            detail="Latitude must be between -90 and 90."
        )

    if lon < -180 or lon > 180:
        raise HTTPException(
            status_code=400,
            detail="Longitude must be between -180 and 180."
        )

    if not np.isfinite(size_sqm) or size_sqm <= 0:
        raise HTTPException(
            status_code=400,
            detail="Store floor area must be greater than zero."
        )

    size_sqm = max(size_sqm, 100.0)

    # ------------------------------------------------------------------------
    # 1. PROPOSED STORE LOCATION
    # ------------------------------------------------------------------------

    try:

        proposed_point_wgs84 = gpd.GeoSeries(
            [Point(lon, lat)],
            crs=GEOGRAPHIC_CRS
        )

        proposed_point_projected = (
            proposed_point_wgs84
            .to_crs(PROJECTED_CRS)
            .iloc[0]
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to transform proposed store coordinates. "
                f"Check GEOGRAPHIC_CRS and PROJECTED_CRS. Error: {exc}"
            )
        )

    # ------------------------------------------------------------------------
    # 2. CHECK STUDY AREA
    # ------------------------------------------------------------------------

    try:

        study_geometry, study_crs = get_study_area_geometry()

        if study_geometry is None:
            raise ValueError(
                "Study area geometry is empty."
            )

        proposed_for_study = (
            gpd.GeoSeries(
                [proposed_point_projected],
                crs=PROJECTED_CRS
            )
            .to_crs(study_crs)
            .iloc[0]
        )

        proposed_in_study_area = (
            proposed_for_study.within(study_geometry)
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed while checking the study area. "
                f"Error: {exc}"
            )
        )

    if not proposed_in_study_area:

        return {
            "status": "warning",
            "message": (
                "The proposed store location is outside "
                "the KREIP study area."
            ),
            "simulated_location": {
                "lat": lat,
                "lon": lon,
                "size_sqm": size_sqm,
                "brand": str(brand).strip()
            }
        }

    # ------------------------------------------------------------------------
    # 3. LOAD POPULATION DEMAND GRID
    # ------------------------------------------------------------------------

    population_grid_path = DATA_PATHS["location_intelligence"]

    if not population_grid_path.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "Location-intelligence demand grid not found: "
                f"{population_grid_path}"
            )
        )

    try:

        population_gdf = gpd.read_file(
            population_grid_path
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to load location-intelligence demand grid: "
                f"{exc}"
            )
        )

    if population_gdf.empty:

        raise HTTPException(
            status_code=500,
            detail=(
                "Location-intelligence demand grid "
                "contains no features."
            )
        )

    # ------------------------------------------------------------------------
    # 4. POPULATION GRID CRS
    # ------------------------------------------------------------------------

    try:

        if population_gdf.crs is None:

            population_gdf = population_gdf.set_crs(
                GEOGRAPHIC_CRS
            )

        population_gdf = population_gdf.to_crs(
            PROJECTED_CRS
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to project the population grid. "
                f"Error: {exc}"
            )
        )

    # ------------------------------------------------------------------------
    # 5. FIND POPULATION FIELD
    # ------------------------------------------------------------------------

    population_field = None

    # Case-insensitive field matching
    field_lookup = {
        str(field).strip().casefold(): field
        for field in population_gdf.columns
    }

    population_candidates = [
        "population",
        "pop_density",
        "pop",
        "pop_count",
        "population_count",
        "total_population",
        "pop_total",
        "persons"
    ]

    for candidate in population_candidates:

        if candidate.casefold() in field_lookup:

            population_field = field_lookup[
                candidate.casefold()
            ]

            break

    if population_field is None:

        raise HTTPException(
            status_code=500,
            detail=(
                "No population field was found in the "
                "location-intelligence grid. "
                f"Available fields: "
                f"{list(population_gdf.columns)}"
            )
        )

    # ------------------------------------------------------------------------
    # 6. CLEAN POPULATION DATA
    # ------------------------------------------------------------------------

    population_gdf = population_gdf[
        population_gdf.geometry.notna()
    ].copy()

    population_gdf = population_gdf[
        ~population_gdf.geometry.is_empty
    ].copy()

    population_gdf[population_field] = (
        pd.to_numeric(
            population_gdf[population_field],
            errors="coerce"
        )
        .fillna(0.0)
    )

    # Remove invalid population values
    population_gdf = population_gdf[
        np.isfinite(
            population_gdf[population_field]
        )
        &
        (
            population_gdf[population_field] > 0
        )
    ].copy()

    if population_gdf.empty:

        raise HTTPException(
            status_code=500,
            detail=(
                "No positive population values were found "
                f"in field '{population_field}'."
            )
        )

    # ------------------------------------------------------------------------
    # 7. CREATE DEMAND CENTROIDS
    # ------------------------------------------------------------------------

    try:

        demand_centroids = (
            population_gdf.geometry.centroid
        )

        demand_coords = np.column_stack(
            [
                demand_centroids.x.to_numpy(),
                demand_centroids.y.to_numpy()
            ]
        )

        demand_population = (
            population_gdf[population_field]
            .to_numpy(dtype=float)
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to create population demand centroids. "
                f"Error: {exc}"
            )
        )

    valid_demand_mask = (
        np.isfinite(demand_population)
        &
        (demand_population > 0)
        &
        np.isfinite(demand_coords[:, 0])
        &
        np.isfinite(demand_coords[:, 1])
    )

    demand_coords = demand_coords[
        valid_demand_mask
    ]

    demand_population = demand_population[
        valid_demand_mask
    ]

    if len(demand_coords) == 0:

        raise HTTPException(
            status_code=500,
            detail=(
                "No valid population demand cells "
                "were found."
            )
        )

    # ------------------------------------------------------------------------
    # 8. LOAD RETAIL MASTER DATA
    # ------------------------------------------------------------------------

    retail_path = DATA_PATHS["retail"]

    if not retail_path.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "Retail master dataset not found: "
                f"{retail_path}"
            )
        )

    try:

        retail_gdf = gpd.read_file(
            retail_path
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to load retail dataset: "
                f"{exc}"
            )
        )

    if retail_gdf.empty:

        raise HTTPException(
            status_code=500,
            detail=(
                "Retail master dataset contains no features."
            )
        )

    # ------------------------------------------------------------------------
    # 9. RETAIL CRS
    # ------------------------------------------------------------------------

    try:

        if retail_gdf.crs is None:

            retail_gdf = retail_gdf.set_crs(
                GEOGRAPHIC_CRS
            )

        retail_gdf = retail_gdf.to_crs(
            PROJECTED_CRS
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to project retail dataset. "
                f"Error: {exc}"
            )
        )

    # ------------------------------------------------------------------------
    # 10. CHECK RETAIL TYPE FIELD
    # ------------------------------------------------------------------------

    retail_fields = {
        str(field).strip().casefold(): field
        for field in retail_gdf.columns
    }

    retail_type_field = (
        retail_fields.get("retail_type")
    )

    if retail_type_field is None:

        raise HTTPException(
            status_code=500,
            detail=(
                "Retail dataset does not contain "
                "'retail_type'. "
                f"Available fields: "
                f"{list(retail_gdf.columns)}"
            )
        )

    # ------------------------------------------------------------------------
    # 11. KEEP SUPERMARKETS
    # ------------------------------------------------------------------------

    supermarkets = retail_gdf[
        retail_gdf[retail_type_field]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
        == "supermarket"
    ].copy()

    supermarkets = supermarkets[
        supermarkets.geometry.notna()
    ].copy()

    supermarkets = supermarkets[
        ~supermarkets.geometry.is_empty
    ].copy()

    supermarkets = supermarkets[
        supermarkets.geometry.geom_type.isin(
            [
                "Point",
                "MultiPoint"
            ]
        )
    ].copy()

    if supermarkets.empty:

        raise HTTPException(
            status_code=500,
            detail=(
                "No supermarket points were found "
                "in the retail dataset. "
                "Check the retail_type values."
            )
        )

    supermarkets = (
        supermarkets
        .reset_index(drop=True)
    )

    # ------------------------------------------------------------------------
    # 12. CONVERT STORE GEOMETRIES TO CENTROIDS
    # ------------------------------------------------------------------------

    try:

        supermarkets["geometry"] = (
            supermarkets.geometry.centroid
        )

        store_coords = np.column_stack(
            [
                supermarkets.geometry.x.to_numpy(),
                supermarkets.geometry.y.to_numpy()
            ]
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to create supermarket coordinates. "
                f"Error: {exc}"
            )
        )

    # ------------------------------------------------------------------------
    # 13. BRAND FIELD
    # ------------------------------------------------------------------------

    brand_field = (
        retail_fields.get("brand")
    )

    if brand_field is not None:

        normalized_brands = (
            supermarkets[brand_field]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.casefold()
        )

    else:

        normalized_brands = pd.Series(
            [""] * len(supermarkets),
            index=supermarkets.index
        )

    # ------------------------------------------------------------------------
    # 14. STORE ATTRACTIVENESS
    # ------------------------------------------------------------------------

    brand_weights = {
        "carrefour": 3.0,
        "naivas": 2.5,
        "quickmart": 2.5,
        "chandarana foodplus": 2.0,
        "cleanshelf": 1.5
    }

    existing_store_attractiveness = (
        normalized_brands
        .map(brand_weights)
        .fillna(1.0)
        .to_numpy(dtype=float)
    )

    # ------------------------------------------------------------------------
    # 15. EXISTING STORE DISTANCES
    # ------------------------------------------------------------------------

    distances_existing = cdist(
        demand_coords,
        store_coords,
        metric="euclidean"
    )

    distances_existing = np.maximum(
        distances_existing,
        MIN_DISTANCE_M
    )

    # ------------------------------------------------------------------------
    # 16. EXISTING STORE UTILITY
    # ------------------------------------------------------------------------

    utility_existing = (
        existing_store_attractiveness[
            np.newaxis,
            :
        ]
        /
        (
            distances_existing
            ** HUFF_BETA
        )
    )

    total_utility_baseline = (
        utility_existing.sum(
            axis=1
        )
    )

    total_utility_baseline = np.maximum(
        total_utility_baseline,
        1e-12
    )

    probability_existing = (
        utility_existing
        /
        total_utility_baseline[
            :,
            np.newaxis
        ]
    )

    baseline_customers_per_store = (
        probability_existing
        *
        demand_population[
            :,
            np.newaxis
        ]
    ).sum(axis=0)

    total_market_population = float(
        demand_population.sum()
    )

    # ------------------------------------------------------------------------
    # 17. PROPOSED STORE ATTRACTIVENESS
    # ------------------------------------------------------------------------

    proposed_store_attractiveness = (
        size_sqm
        ** STORE_SIZE_EXPONENT
    )

    # ------------------------------------------------------------------------
    # 18. PROPOSED STORE DISTANCES
    # ------------------------------------------------------------------------

    proposed_coords = np.array(
        [
            [
                proposed_point_projected.x,
                proposed_point_projected.y
            ]
        ],
        dtype=float
    )

    proposed_distances = (
        cdist(
            demand_coords,
            proposed_coords,
            metric="euclidean"
        )
        .flatten()
    )

    proposed_distances = np.maximum(
        proposed_distances,
        MIN_DISTANCE_M
    )

    # ------------------------------------------------------------------------
    # 19. PROPOSED STORE UTILITY
    # ------------------------------------------------------------------------

    proposed_utility = (
        proposed_store_attractiveness
        /
        (
            proposed_distances
            ** HUFF_BETA
        )
    )

    total_utility_new = (
        total_utility_baseline
        +
        proposed_utility
    )

    # ------------------------------------------------------------------------
    # 20. MARKET CAPTURE
    # ------------------------------------------------------------------------

    proposed_probability = (
        proposed_utility
        /
        np.maximum(
            total_utility_new,
            1e-12
        )
    )

    captured_population = float(
        np.sum(
            demand_population
            *
            proposed_probability
        )
    )

    market_capture_pct = (
        (
            captured_population
            /
            total_market_population
            *
            100.0
        )
        if total_market_population > 0
        else 0.0
    )

    # ------------------------------------------------------------------------
    # 21. CATCHMENT POPULATION
    # ------------------------------------------------------------------------

    catchment_mask = (
        proposed_distances
        <= CATCHMENT_RADIUS_M
    )

    if np.any(catchment_mask):

        catchment_distances = (
            proposed_distances[
                catchment_mask
            ]
        )

        catchment_population = (
            demand_population[
                catchment_mask
            ]
        )

        distance_weights = np.exp(
            -catchment_distances
            /
            CATCHMENT_DECAY_M
        )

        estimated_catchment_population = float(
            np.sum(
                catchment_population
                *
                distance_weights
            )
        )

    else:

        estimated_catchment_population = 0.0

    # ------------------------------------------------------------------------
    # 22. TARGET BRAND
    # ------------------------------------------------------------------------

    target_brand = (
        str(brand).strip()
        if brand is not None
        else ""
    )

    if (
        target_brand
        and brand_field is not None
    ):

        own_store_mask = (
            normalized_brands
            ==
            target_brand.casefold()
        )

        own_positions = np.flatnonzero(
            own_store_mask.to_numpy()
        )

    else:

        own_positions = np.arange(
            len(supermarkets)
        )

    own_positions = np.asarray(
        own_positions,
        dtype=int
    )

    # ------------------------------------------------------------------------
    # 23. EXISTING STORE PROBABILITIES AFTER NEW STORE
    # ------------------------------------------------------------------------

    probability_existing_after = (
        utility_existing
        /
        np.maximum(
            total_utility_new[
                :,
                np.newaxis
            ],
            1e-12
        )
    )

    new_customers_per_existing_store = (
        probability_existing_after
        *
        demand_population[
            :,
            np.newaxis
        ]
    ).sum(axis=0)

    customer_loss_per_store = (
        baseline_customers_per_store
        -
        new_customers_per_existing_store
    )

    customer_loss_per_store = np.maximum(
        customer_loss_per_store,
        0.0
    )

    # ------------------------------------------------------------------------
    # 24. CANNIBALIZATION
    # ------------------------------------------------------------------------

    cannibalization_pct = 0.0
    lost_own_customers = 0.0
    baseline_own_customers = 0.0

    if len(own_positions) > 0:

        lost_own_customers = float(
            customer_loss_per_store[
                own_positions
            ].sum()
        )

        baseline_own_customers = float(
            baseline_customers_per_store[
                own_positions
            ].sum()
        )

        if baseline_own_customers > 0:

            cannibalization_pct = (
                lost_own_customers
                /
                baseline_own_customers
                *
                100.0
            )

    # ------------------------------------------------------------------------
    # 25. CANNIBALIZATION RISK
    # ------------------------------------------------------------------------

    if cannibalization_pct < 3.0:

        cannibalization_risk = "Low"

    elif cannibalization_pct < 7.0:

        cannibalization_risk = "Moderate"

    else:

        cannibalization_risk = "High"

    # ------------------------------------------------------------------------
    # 26. NEAREST SUPERMARKET
    # ------------------------------------------------------------------------

    store_distance_from_candidate = (
        cdist(
            proposed_coords,
            store_coords,
            metric="euclidean"
        )
        .flatten()
    )

    nearest_store_position = int(
        np.argmin(
            store_distance_from_candidate
        )
    )
    
    nearest_store_distance = float(
        store_distance_from_candidate[
            nearest_store_position
        ]
    )

    nearest_store = supermarkets.iloc[
        nearest_store_position
    ]

    # Safely identify nearest supermarket name/brand
    nearest_competitor_name = (
        nearest_store.get(
            "name",
            None
        )
    )

    if not nearest_competitor_name and brand_field is not None:
        nearest_competitor_name = (
            nearest_store.get(
                brand_field,
                None
            )
        )

    if not nearest_competitor_name:
        nearest_competitor_name = (
            "Existing supermarket"
        )

    # ------------------------------------------------------------------------
    # 27. COMPETITOR IMPACT
    # ------------------------------------------------------------------------

    nearest_competitor_loss = float(
        customer_loss_per_store[
            nearest_store_position
        ]
    )

    nearest_competitor_baseline = float(
        baseline_customers_per_store[
            nearest_store_position
        ]
    )

    competitor_impact_pct = (
        (
            nearest_competitor_loss
            /
            nearest_competitor_baseline
        )
        *
        100.0
        if nearest_competitor_baseline > 0
        else 0.0
    )

    # ------------------------------------------------------------------------
    # 28. RECOMMENDATION
    # ------------------------------------------------------------------------

    if (
        market_capture_pct >= 2.0
        and
        cannibalization_pct < 3.0
    ):

        recommendation = (
            "HIGH-POTENTIAL RETAIL EXPANSION LOCATION"
        )

    elif (
        market_capture_pct >= 1.0
        and
        cannibalization_pct < 7.0
    ):

        recommendation = (
            "CONDITIONAL EXPANSION OPPORTUNITY"
        )

    else:

        recommendation = (
            "LOW-PRIORITY / HIGH-RISK EXPANSION LOCATION"
        )

    # ------------------------------------------------------------------------
    # 29. RETURN RESULTS
    # ------------------------------------------------------------------------

    return {

        "status": "success",

        "simulated_location": {

            "lat": lat,

            "lon": lon,

            "size_sqm": size_sqm,

            "brand":
                target_brand
                or
                "Proposed Store"
        },

        "model": {

            "method":
                "Huff gravity / spatial interaction",

            "beta":
                HUFF_BETA,

            "catchment_radius_m":
                CATCHMENT_RADIUS_M,

            "store_attractiveness":
                round(
                    float(
                        proposed_store_attractiveness
                    ),
                    3
                )
        },

        "demand": {

            "total_market_population":
                round(
                    total_market_population,
                    2
                ),

            "estimated_catchment_population":
                round(
                    estimated_catchment_population,
                    2
                ),

            "captured_population":
                round(
                    captured_population,
                    2
                ),

            "market_capture_pct":
                round(
                    market_capture_pct,
                    2
                )
        },

        "competition": {

            "existing_supermarkets":
                int(
                    len(supermarkets)
                ),

            "nearest_competitor":
                str(
                    nearest_competitor_name
                ),

            "nearest_competitor_distance_m":
                round(
                    nearest_store_distance,
                    2
                ),

            "nearest_competitor_customer_loss":
                round(
                    nearest_competitor_loss,
                    2
                ),

            "nearest_competitor_impact_pct":
                round(
                    competitor_impact_pct,
                    2
                )
        },

        "cannibalization": {

            "target_brand":
                target_brand
                or
                "All Existing Supermarkets",

            "target_brand_store_count":
                int(
                    len(own_positions)
                ),

            "lost_existing_brand_customers":
                round(
                    lost_own_customers,
                    2
                ),

            "baseline_existing_brand_customers":
                round(
                    baseline_own_customers,
                    2
                ),

            "existing_brand_cannibalization_pct":
                round(
                    cannibalization_pct,
                    2
                ),

            "risk":
                cannibalization_risk
        },

        "recommendation":
            recommendation
    }
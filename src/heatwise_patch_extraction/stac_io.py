from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


PROCESSOR_NAME = "heatwise-patch-extraction"
PROCESSOR_VERSION = "0.1.1"


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_asset_href(item_path: Path, href: str) -> str:
    """
    Resolve a STAC asset href relative to the Item JSON file.
    """
    asset_path = Path(href)

    if asset_path.is_absolute():
        return str(asset_path)

    return str((item_path.parent / asset_path).resolve())


def inputs_from_stac(catalog_path: str | Path, city: str | None = None) -> dict:
    """
    Read Sentinel-2, HSI and optional LST/PCA inputs from a staged STAC catalog.

    The catalog must reference at least one STAC Item containing the required
    `sentinel2` and `hsi` assets. Optional assets are `lst` and `pca`.

    If `city` is supplied, an Item whose id matches the city is preferred.
    """
    catalog_path = Path(catalog_path).resolve()

    if not catalog_path.exists():
        raise FileNotFoundError(f"STAC catalog not found: {catalog_path}")

    catalog = _read_json(catalog_path)

    item_links = [
        link
        for link in catalog.get("links", [])
        if link.get("rel") == "item"
    ]

    if not item_links:
        raise ValueError(
            f"No STAC Item links found in input catalog: {catalog_path}"
        )

    candidates = []

    for link in item_links:
        href = link.get("href")
        if not href:
            continue

        item_path = Path(href)
        if not item_path.is_absolute():
            item_path = (catalog_path.parent / item_path).resolve()

        item = _read_json(item_path)
        assets = item.get("assets", {})

        if "sentinel2" not in assets or "hsi" not in assets:
            continue

        candidates.append((item_path, item))

    if not candidates:
        raise ValueError(
            "No STAC Item contains both required assets: "
            "`sentinel2` and `hsi`."
        )

    selected_path, selected_item = candidates[0]

    if city:
        city_lower = city.lower()
        for item_path, item in candidates:
            if str(item.get("id", "")).lower() == city_lower:
                selected_path, selected_item = item_path, item
                break

    assets = selected_item["assets"]

    inputs = {
        "sentinel2": _resolve_asset_href(
            selected_path, assets["sentinel2"]["href"]
        ),
        "hsi": _resolve_asset_href(
            selected_path, assets["hsi"]["href"]
        ),
    }

    if "lst" in assets:
        inputs["lst"] = _resolve_asset_href(
            selected_path, assets["lst"]["href"]
        )

    if "pca" in assets:
        inputs["pca"] = _resolve_asset_href(
            selected_path, assets["pca"]["href"]
        )

    return inputs


def write_output_catalog(
    output_h5: str | Path,
    city: str,
    geometry: str | None = None,
    bbox: list[float] | None = None,
    processor_name: str = PROCESSOR_NAME,
    processor_version: str = PROCESSOR_VERSION,
) -> Path:
    """
    Write a minimal valid STAC Catalog and Item for the generated H5 dataset.

    The catalog.json and Item JSON are written next to the H5 output.
    """
    output_h5 = Path(output_h5).resolve()
    output_dir = output_h5.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    item_id = f"{city}-patches"
    item_filename = f"{item_id}_item.json"
    item_path = output_dir / item_filename
    catalog_path = output_dir / "catalog.json"

    item = {
        "type": "Feature",
        "stac_version": "1.1.0",
        "stac_extensions": [
            "https://stac-extensions.github.io/processing/v1.2.0/schema.json"
        ],
        "id": item_id,
        "geometry": geometry,
        "bbox": bbox,
        "properties": {
            "datetime": datetime.now(timezone.utc).isoformat(),
            "processing:software": {
                processor_name: processor_version
            },
        },
        "links": [],
        "assets": {
            "patch_h5": {
                "href": output_h5.name,
                "type": "application/x-hdf5",
                "roles": ["data"],
                "title": "Geo-isolated patch dataset",
            }
        },
    }

    catalog = {
        "type": "Catalog",
        "stac_version": "1.0.0",
        "id": f"{processor_name}-output",
        "description": (
            "HEATWISE geographically isolated patch extraction output."
        ),
        "links": [
            {
                "rel": "item",
                "href": item_filename,
                "type": "application/geo+json",
            }
        ],
    }

    with item_path.open("w", encoding="utf-8") as f:
        json.dump(item, f, indent=2)

    with catalog_path.open("w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)

    return catalog_path

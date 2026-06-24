"""Spectral index computation from Sentinel-2 composites."""

from __future__ import annotations

import ee


def build_spectral_indices(s2_image: ee.Image) -> ee.Image:
    """Compute NDVI and NDWI from a Sentinel-2 composite.

    NDVI = (B8 - B4) / (B8 + B4)  — vegetation greenness
    NDWI = (B3 - B8) / (B3 + B8)  — open water (high = water)

    Returns:
        ee.Image with bands "ndvi" and "ndwi".
    """
    ndvi = s2_image.normalizedDifference(["B8", "B4"]).rename("ndvi")
    ndwi = s2_image.normalizedDifference(["B3", "B8"]).rename("ndwi")
    return ee.Image.cat([ndvi, ndwi])

"""Compute per-class land cover area statistics from signature images."""

from __future__ import annotations

import logging

import ee

from . import config

log = logging.getLogger(__name__)


def compute_land_cover_stats(
    sig_a: ee.Image, sig_b: ee.Image, aoi: ee.Geometry
) -> dict:
    """Compute per-class land cover percentages for T1 and T2, plus delta.

    Uses GEE reduceRegion with a frequencyHistogram on the signature_label
    band to count pixels per class.  Converts to percentages of total
    classified pixels, then computes T2 − T1 delta per class.

    Args:
        sig_a: Signature image for timeline 1 (must have "signature_label" band)
        sig_b: Signature image for timeline 2 (must have "signature_label" band)
        aoi: Area of interest geometry

    Returns:
        Dict with a "classes" list, each entry containing name, color,
        before (%), after (%), and delta (%) values.
    """
    scale = 10  # Dynamic World native resolution

    def _hist(image):
        return image.select("signature_label").reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=aoi,
            scale=scale,
            maxPixels=1e9,
            bestEffort=True,
        ).get("signature_label")

    hist_a = ee.Dictionary(_hist(sig_a))
    hist_b = ee.Dictionary(_hist(sig_b))

    # GEE returns histogram keys as strings — collect class codes as strings
    class_codes = sorted(config.LAND_COVER_CLASSES.keys())
    class_strs = [str(c) for c in class_codes]

    # Sum pixel counts across all classes (server-side)
    total_a = ee.Number(0)
    total_b = ee.Number(0)
    for s in class_strs:
        total_a = total_a.add(ee.Number(hist_a.get(s, 0)))
        total_b = total_b.add(ee.Number(hist_b.get(s, 0)))
    total_a = total_a.max(1)
    total_b = total_b.max(1)

    classes = []
    for code in class_codes:
        info = config.LAND_COVER_CLASSES[code]
        pct_a = ee.Number(hist_a.get(str(code), 0)).divide(total_a).multiply(100)
        pct_b = ee.Number(hist_b.get(str(code), 0)).divide(total_b).multiply(100)
        delta = pct_b.subtract(pct_a)
        classes.append({
            "name": info["name"],
            "color": info["color"],
            "before": pct_a,
            "after": pct_b,
            "delta": delta,
        })

    # Evaluate server-side — returns plain Python dict
    result = ee.List([
        ee.Dictionary({
            "name": c["name"],
            "color": c["color"],
            "before": c["before"],
            "after": c["after"],
            "delta": c["delta"],
        })
        for c in classes
    ]).getInfo()

    # Round numeric values
    return {
        "classes": [
            {
                "name": r["name"],
                "color": r["color"],
                "before": round(r["before"], 1),
                "after": round(r["after"], 1),
                "delta": round(r["delta"], 1),
            }
            for r in result
        ]
    }

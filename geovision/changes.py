"""Change detection engine — Dynamic World signatures + rule-based gates."""

from __future__ import annotations

import logging

import ee

from .spectral import build_spectral_indices
from .signature import dw_to_signature
from . import config

log = logging.getLogger(__name__)


def detect_changes(dw_a: ee.Image, dw_b: ee.Image,
                   s2_b: ee.Image = None) -> ee.Image:
    """Detect land cover changes via Dynamic World signatures + rule engine.

    Args:
        dw_a: Median composite of DW probability bands for timeline 1
        dw_b: Median composite of DW probability bands for timeline 2
        s2_a: Median Sentinel-2 composite for timeline 1 (optional, for
              spectral cross-validation)
        s2_b: Median Sentinel-2 composite for timeline 2 (optional, for
              spectral cross-validation)

    Pipeline:
      1. Map 9-band DW probability images to 5-class signature schema
      2. Get BEFORE label and AFTER label for every pixel
      3. Apply rule engine with three gates per transition:
         a. Confidence gate: both the from-class (T1) and to-class (T2)
            must have proportion ≥ MIN_CLASS_CONF
         b. Surge gate: the target class's raw DW probability must have
            increased by ≥ MIN_PROB_SURGE between T1 and T2.
         c. Spectral gate (when S2 composites provided): cross-validate
            DW labels against independent spectral indices.  Transitions
            to forest require NDVI ≥ threshold; transitions to water
            require NDWI ≥ threshold.  Rejects shadow-induced false water.
    """
    log.info("Computing DW signatures...")
    sig_a = dw_to_signature(dw_a)
    sig_b = dw_to_signature(dw_b)

    label_a = sig_a.select("signature_label")
    label_b = sig_b.select("signature_label")

    # Pre-compute spectral indices if S2 composites are available
    spec_b = None
    if s2_b is not None:
        spec_b = build_spectral_indices(s2_b)
        log.info("Spectral cross-validation enabled (NDVI/NDWI gates).")

    change = label_a.multiply(0).rename("change").toInt16()

    for code, (from_cls, to_cls, label, color) in enumerate(config.CHANGE_TRANSITIONS, start=1):
        # Gate 1: Confidence — both endpoints must be decisive
        conf_a = sig_a.select(config.CLASS_PROP_BAND[from_cls])
        conf_b = sig_b.select(config.CLASS_PROP_BAND[to_cls])

        # Gate 2: Probability surge — the target class must have actually
        # increased. Select the raw DW band for the target class from both
        # composites and compute T2 - T1.
        if to_cls in config.DW_BAND_FOR_CLASS:
            target_band = config.DW_BAND_FOR_CLASS[to_cls]
            prob_T1 = dw_a.select(target_band)
            prob_T2 = dw_b.select(target_band)
            surge = prob_T2.subtract(prob_T1)
            surge_mask = surge.gte(config.MIN_PROB_SURGE)
        else:
            # Fallback: if class not in DW_BAND_FOR_CLASS, skip surge check
            surge_mask = ee.Image(1)

        # Gate 3: Spectral cross-validation — reject DW labels that
        # are inconsistent with independent spectral indices.
        if to_cls == 1 and spec_b is not None:
            # "to forest" → T2 must have real vegetation (NDVI gate)
            spectral_mask = spec_b.select("ndvi").gte(config.MIN_NDVI_FOR_FOREST)
        elif to_cls == 0 and spec_b is not None:
            # "to water" → T2 must have real water (NDWI gate)
            spectral_mask = spec_b.select("ndwi").gte(config.MIN_NDWI_FOR_WATER)
        else:
            spectral_mask = ee.Image(1)

        mask = (
            label_a.eq(from_cls)
            .And(label_b.eq(to_cls))
            .And(conf_a.gte(config.MIN_CLASS_CONF))
            .And(conf_b.gte(config.MIN_CLASS_CONF))
            .And(surge_mask)
            .And(spectral_mask)
        )
        change = change.where(mask, code)

    change = change.updateMask(change.neq(0))

    return change


def get_change_vis_params() -> dict:
    """Visualization for the change mask (multi-transition palette)."""
    palette = ",".join(color for _, _, _, color in config.CHANGE_TRANSITIONS)
    return {"bands": ["change"], "min": 1, "max": len(config.CHANGE_TRANSITIONS), "palette": palette}

"""Map 9-band Dynamic World probabilities to a 5-class signature schema."""

from __future__ import annotations

import ee

from . import config


def dw_to_signature(dw_image: ee.Image) -> ee.Image:
    """Map 9-band DW probability image to the 5-class signature schema.

    Band mapping (raw DW probabilities, NO re-normalization):
        forest_prop = dw_image "trees"
        urban_prop  = dw_image "built"
        water_prop  = dw_image "water"
        bare_prop   = dw_image "bare"
        agri_prop   = dw_image "crops"

    We use raw probabilities because re-normalizing inflates proportions
    when dropped classes (grass, flooded_vegetation, snow_and_ice) hold
    significant mass. A pixel with trees=0.35 and grass=0.30 would become
    forest_prop=0.50 after normalization — passing the confidence gate
    on what is actually a marginal, mixed pixel. Raw probabilities are
    already well-calibrated by the DW model.

    Returns:
        ee.Image with bands: forest_prop, urban_prop, water_prop,
        bare_prop, agri_prop, signature_label
    """
    forest_prop = dw_image.select("trees").rename("forest_prop")
    urban_prop = dw_image.select("built").rename("urban_prop")
    water_prop = dw_image.select("water").rename("water_prop")
    bare_prop = dw_image.select("bare").rename("bare_prop")
    agri_prop = dw_image.select("crops").rename("agri_prop")

    # Determine dominant label from proportions.
    # A class is assigned only if it beats every other class by
    # ≥ MIN_DOMINANCE_MARGIN AND its raw proportion is ≥ MIN_CLASS_CONF.
    # Without the floor, a pixel where all props are low (e.g. trees=0.15,
    # water=0.10) can be labelled "forest" simply by being the tallest dwarf.
    # Coastal ocean pixels were getting mis-classified this way.
    margin = config.MIN_DOMINANCE_MARGIN
    floor = config.MIN_SIGNATURE_CONF

    is_water = (
        water_prop.gte(floor)
        .And(water_prop.gte(forest_prop.add(margin)))
        .And(water_prop.gte(urban_prop.add(margin)))
        .And(water_prop.gte(bare_prop.add(margin)))
        .And(water_prop.gte(agri_prop.add(margin)))
    )
    is_forest = (
        forest_prop.gte(floor)
        .And(forest_prop.gte(water_prop.add(margin)))
        .And(forest_prop.gte(urban_prop.add(margin)))
        .And(forest_prop.gte(bare_prop.add(margin)))
        .And(forest_prop.gte(agri_prop.add(margin)))
    )
    is_bare = (
        bare_prop.gte(floor)
        .And(bare_prop.gte(water_prop.add(margin)))
        .And(bare_prop.gte(forest_prop.add(margin)))
        .And(bare_prop.gte(urban_prop.add(margin)))
        .And(bare_prop.gte(agri_prop.add(margin)))
    )
    is_agri = (
        agri_prop.gte(floor)
        .And(agri_prop.gte(water_prop.add(margin)))
        .And(agri_prop.gte(forest_prop.add(margin)))
        .And(agri_prop.gte(urban_prop.add(margin)))
        .And(agri_prop.gte(bare_prop.add(margin)))
    )
    is_urban = (
        urban_prop.gte(floor)
        .And(urban_prop.gte(water_prop.add(margin)))
        .And(urban_prop.gte(forest_prop.add(margin)))
        .And(urban_prop.gte(bare_prop.add(margin)))
        .And(urban_prop.gte(agri_prop.add(margin)))
    )

    any_class = (
        is_water.Or(is_forest)
        .Or(is_bare).Or(is_agri).Or(is_urban)
    )

    label = (
        ee.Image.constant(0)
        .where(is_water, 0)
        .where(is_forest, 1)
        .where(is_bare, 3)
        .where(is_agri, 4)
        .where(is_urban, 6)
        .updateMask(any_class)
        .rename("signature_label")
    )

    return ee.Image.cat([
        forest_prop, urban_prop, water_prop,
        bare_prop, agri_prop, label,
    ])

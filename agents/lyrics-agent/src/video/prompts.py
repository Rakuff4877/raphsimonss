import random
from typing import Optional, Tuple

PROMPTS = [
    # --- DRIVING (3) ---
    (
        "A couple driving in a convertible on an empty coastal highway at golden hour, "
        "windows down, warm amber light flooding the interior, long lens compression, "
        "35mm film grain, romantic and cinematic, slow push-in"
    ),
    (
        "Wide cinematic shot of a red convertible on an open desert highway at dusk, "
        "two silhouettes visible, long shadows stretching across the road, deep orange sky, "
        "dust swirling gently, anamorphic lens flare, slow aerial pull-back"
    ),
    (
        "Slow motion close-up of a couple's intertwined hands resting on the open car window, "
        "open highway rushing past out of focus, golden bokeh, warm amber haze, "
        "35mm film grain, deeply romantic and cinematic"
    ),

    # --- NATURE & LANDSCAPE (4) ---
    (
        "Slow motion aerial shot descending through a misty forest at dawn, golden light rays "
        "piercing through tall pine trees, soft fog rolling along the ground, "
        "dreamlike and ethereal, 35mm film grain, cinematic"
    ),
    (
        "Slow motion ocean waves crashing on a deserted shore at golden hour, warm amber foam "
        "rushing over dark wet sand, viewed from just above the waterline, "
        "anamorphic lens, deeply immersive, cinematic"
    ),
    (
        "Two silhouettes walking through a blooming sunflower field at sunset, flowers swaying "
        "gently in the breeze, warm golden backlight, slow motion, soft bokeh, "
        "romantic and dreamy, 16mm film texture"
    ),
    (
        "Slow motion snowfall on a quiet city street at night, warm amber streetlights "
        "illuminating each flake, a lone figure walking away into the glow, "
        "peaceful and melancholic, cinematic shallow depth of field"
    ),

    # --- URBAN & ARCHITECTURAL (2) ---
    (
        "Two people on a rooftop at midnight, city lights stretching endlessly below, "
        "soft wind moving through hair, looking out at the skyline, "
        "warm bokeh, cinematic long lens, slow push-in, intimate and vast"
    ),
    (
        "Rain streaking down a large apartment window at night, warm interior light "
        "contrasting with the cold wet city outside, a silhouette looking out, "
        "reflections layering the scene, moody and cinematic, shallow depth of field"
    ),

    # --- INTIMATE & EDITORIAL (3) ---
    (
        "Slow motion close-up of a person's face tilted toward the sun in a golden field, "
        "eyes closed, soft smile, warm light wrapping the skin, hair catching the breeze, "
        "35mm film grain, dreamy and romantic"
    ),
    (
        "Cinematic shot of candles flickering in a dim room, soft warm light dancing on skin "
        "and tangled linen, slow zoom out revealing an intimate scene, "
        "deeply romantic, film grain, 1.85:1 aspect"
    ),
    (
        "Slow motion shot of a person standing in the rain on an empty street, arms out, "
        "head back, eyes closed, streetlights haloing through the downpour, "
        "cinematic and emotional, warm vs cold color contrast"
    ),
]


def select_prompt(seed: Optional[int] = None) -> Tuple[int, str]:
    """Return (index, prompt). Random by default; forced index with seed (0-11)."""
    if seed is not None:
        idx = seed % len(PROMPTS)
    else:
        idx = random.randint(0, len(PROMPTS) - 1)
    return idx, PROMPTS[idx]

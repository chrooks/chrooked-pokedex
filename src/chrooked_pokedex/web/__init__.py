"""The local web layer: a FastAPI app over the existing Ruleset core.

Thin Interface — every module here imports the real `chrooked_pokedex.*`
loaders, readers, and appliers rather than reimplementing their logic.
"""

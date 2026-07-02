project = "AERLIFT"
copyright = "2026, Mark Campmier"
author = "Mark Campmier, PhD"

extensions = ["myst_parser"]
source_suffix = [".rst", ".md"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"
html_title = "AERLIFT Pipeline"
html_theme_options = {
    "sidebar_hide_name": False,
}

myst_enable_extensions = ["colon_fence", "deflist"]

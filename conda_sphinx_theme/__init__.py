try:
    from ._version import version_tuple as version_info, __version__  # noqa: F401  # ty: ignore[unresolved-import]
except ImportError:  # pragma: no cover
    # Version file not generated yet (e.g., in editable install before build)
    __version__ = "0.0.0+unknown"
    version_info = (0, 0, 0)

import json
from pathlib import Path
from urllib.request import urlopen

from sphinx.util import logging

logger = logging.getLogger(__name__)

# theme.conf values arrive as strings, while html_theme_options can supply real
# booleans; these are the spellings that mean False.
FALSE_VALUES = frozenset({"false", "0", "no", "off"})

# Seconds to wait for the conda-plugins list before giving up on it
PLUGINS_TIMEOUT = 10


def project_key(name):
    """Identity of a project/plugin name, ignoring case and separators."""
    return name.lower().replace("_", "-")


def fetch_plugins(url):
    """Load the plugin list published by the conda-plugins site."""
    with urlopen(url, timeout=PLUGINS_TIMEOUT) as response:
        return json.loads(response.read())


def normalize_plugins(payload, projects):
    """Shape conda-plugins entries like project entries, newest data first.

    A plugin without its own documentation site falls back to the matching
    project's docs URL, then to its repository.
    """
    if isinstance(payload, dict):
        # conda-plugins publishes {"categories": [...], "plugins": [...]}
        payload = payload.get("plugins", [])
    if not isinstance(payload, list):
        logger.warning("conda-sphinx-theme: plugin payload is not a list of plugins")
        return []
    project_by_key = {project_key(entry["name"]): entry for entry in projects}
    plugins = []
    seen = set()
    for entry in payload:
        if not isinstance(entry, dict) or not entry.get("name"):
            continue
        name = entry["name"]
        key = project_key(name)
        project = project_by_key.get(key, {})
        github = entry.get("repo_url") or entry.get("github")
        docs = entry.get("docs") or project.get("docs") or github
        if not docs or key in seen:
            continue
        seen.add(key)
        plugins.append(
            {
                # keep curated package/channels when the plugin is also a project
                **project,
                "name": name,
                "docs": docs,
                "github": github,
                "package": project.get("package") or key,
                "category": entry.get("category"),
            }
        )
    return sorted(plugins, key=lambda entry: entry["name"].lower())


def set_config_defaults(app):
    """Inject additional default theme options and icon links."""
    try:
        theme = app.builder.theme_options
    except AttributeError:
        theme = None
    if not theme:
        theme = {}

    # Add extra icon links entries if there were shortcuts present
    # See https://github.com/pydata/pydata-sphinx-theme/blob/6b426bb133812c69b33ce88913f8bc018f1bfd02/src/pydata_sphinx_theme/__init__.py#L141-L163
    icon_links = []
    for key, default_url, icon, name in [
        ("zulip_url", "https://conda.zulipchat.com/", "fa-custom fa-zulip", "Zulip"),
    ]:
        # Skip link if URL is falsy
        if url := theme.get(key, default_url):
            icon_links.append(
                {
                    "url": url,
                    "icon": icon,
                    "name": name,
                    "type": "fontawesome",
                },
            )
    theme["icon_links"] = [*icon_links, *(theme.get("icon_links") or [])]

    # Default project list, unless the project supplied one
    projects = theme.get("projects")
    if projects is None or isinstance(projects, str):
        # theme.conf declares this as an empty string, meaning "use the default"
        projects = json.loads((Path(__file__).parent / "projects.json").read_text())
        theme["projects"] = projects
    for entry in projects:
        if (
            not isinstance(entry, dict)
            or not entry.get("name")
            or not entry.get("docs")
        ):
            raise ValueError(
                f"conda-sphinx-theme: invalid project entry {entry!r}, "
                "'name' and 'docs' are required"
            )

    # Plugin list from conda-plugins, unless the project supplied one
    plugins = theme.get("plugins")
    if plugins:
        plugins = normalize_plugins(plugins, projects)
    else:
        plugins = []
        if plugins_url := theme.get("plugins_json_url"):
            try:
                payload = fetch_plugins(plugins_url)
            except (OSError, ValueError) as exc:
                logger.warning(
                    "conda-sphinx-theme: could not read plugins from %s (%s), "
                    "continuing with projects only",
                    plugins_url,
                    exc,
                )
            else:
                plugins = normalize_plugins(payload, projects)
    theme["plugins"] = plugins

    # A plugin entry wins over a project entry with the same name
    plugin_names = {project_key(entry["name"]) for entry in plugins}
    projects = [p for p in projects if project_key(p["name"]) not in plugin_names]

    # One canonical order for the navbar and the projects page
    theme["projects"] = sorted(projects, key=lambda entry: entry["name"].lower())

    # theme.conf values arrive as strings; normalize so templates and the
    # html-collect-pages hook agree
    theme["projects_page"] = (
        str(theme.get("projects_page", "true")).lower() not in FALSE_VALUES
    )

    # Add custom Zulip icon
    app.add_js_file("js/zulip-icon.js")

    # Filter bar for the project list in the navbar
    app.add_js_file("js/projects-filter.js")

    # Add GoatCounter script
    if goatcounter_url := theme.get("goatcounter_url"):
        app.add_js_file(
            "js/count.js",
            **{"loading_method": "async", "data-goatcounter": goatcounter_url},
        )

    # Default logo
    logo = theme.get("logo", {})
    if "image_dark" not in logo:
        logo["image_dark"] = "_static/conda_logo_full.svg"
    if "image_light" not in logo:
        logo["image_light"] = "_static/conda_logo_full.svg"
    theme["logo"] = logo

    # Default favicon; relies on https://sphinx-favicon.readthedocs.io/en/stable
    favicons = theme.get("favicons", [])
    favicons.append({"href": "favicon.ico", "rel": "icon", "type": "image/svg+xml"})
    theme["favicons"] = favicons

    # Update the HTML theme config
    app.builder.theme_options = theme


def get_projects_page(app):
    """Generate a page listing every documentation site in the project list."""
    builder = app.builder
    if not builder.theme_options.get("projects_page"):
        return
    if "projects" in builder.env.found_docs:
        logger.info(
            "conda-sphinx-theme: not generating a projects page, a document "
            "named 'projects' already exists"
        )
        return
    yield (
        "projects",
        {"conda_page": "projects", "title": "Projects", "parents": []},
        "projects.html",
    )


# For more details, see:
# https://www.sphinx-doc.org/en/master/development/theming.html#distribute-your-theme-as-a-python-package
def setup(app):
    here = Path(__file__).parent.resolve()
    # Include component templates
    app.config.templates_path.append(str(here / "_templates"))
    app.add_html_theme("conda_sphinx_theme", str(here))
    app.connect("builder-inited", set_config_defaults)
    app.connect("html-collect-pages", get_projects_page)
    return {"version": __version__, "parallel_read_safe": True}

"""
Tests for the project list and the generated projects page.
"""

from __future__ import annotations

import json

import pytest


def make_app(mocker, theme_options=None):
    app = mocker.Mock()
    app.builder = mocker.Mock()
    app.builder.theme_options = {} if theme_options is None else theme_options
    return app


def make_app_with_builder(mocker, theme_options=None, found_docs=()):
    app = mocker.Mock()
    app.builder.theme_options = {} if theme_options is None else theme_options
    app.builder.env.found_docs = set(found_docs)
    return app


def test_projects_shipped_list(mocker):
    """The shipped list is valid and sorted by name."""
    from conda_sphinx_theme import set_config_defaults

    app = make_app(mocker)
    set_config_defaults(app)

    projects = app.builder.theme_options["projects"]
    assert projects
    assert all(entry.get("name") and entry.get("docs") for entry in projects)
    assert len({entry["name"] for entry in projects}) == len(projects)
    assert [entry["name"] for entry in projects] == sorted(
        entry["name"] for entry in projects
    )


def test_projects_json_is_packaged():
    """The shipped list is valid JSON and is declared as package data."""
    from pathlib import Path

    import tomllib

    import conda_sphinx_theme

    root = Path(conda_sphinx_theme.__file__).parent
    assert json.loads((root / "projects.json").read_text())

    config = tomllib.loads((root.parent / "pyproject.toml").read_text())
    package_data = config["tool"]["setuptools"]["package-data"]["conda_sphinx_theme"]
    assert "projects.json" in package_data


def test_projects_page_enabled_by_default(mocker):
    """The projects page is generated unless it is turned off."""
    from conda_sphinx_theme import set_config_defaults

    app = make_app(mocker)
    set_config_defaults(app)

    assert app.builder.theme_options["projects_page"] is True


@pytest.mark.parametrize("value", [False, "false", "0", "no", "off"])
def test_projects_page_disabled(mocker, value):
    """Any falsy spelling of projects_page disables the page."""
    from conda_sphinx_theme import set_config_defaults

    app = make_app(mocker, {"projects_page": value})
    set_config_defaults(app)

    assert app.builder.theme_options["projects_page"] is False


def test_projects_defaults_to_shipped_list(mocker):
    """An empty projects option means "use the shipped list"."""
    from conda_sphinx_theme import set_config_defaults

    app = make_app(mocker, {"projects": ""})
    set_config_defaults(app)

    assert app.builder.theme_options["projects"][0]["name"] == "conda"


def test_projects_override_replaces_default(mocker):
    """A project can supply its own list, even an empty one."""
    from conda_sphinx_theme import set_config_defaults

    custom = [{"name": "myproject", "docs": "https://example.com"}]
    app = make_app(mocker, {"projects": custom})
    set_config_defaults(app)

    assert app.builder.theme_options["projects"] == custom


def test_projects_override_is_sorted(mocker):
    """A project's own list is ordered the same way as the shipped one."""
    from conda_sphinx_theme import set_config_defaults

    custom = [
        {"name": "zebra", "docs": "https://z.example"},
        {"name": "Alpha", "docs": "https://a.example"},
    ]
    app = make_app(mocker, {"projects": custom})
    set_config_defaults(app)

    assert [entry["name"] for entry in app.builder.theme_options["projects"]] == [
        "Alpha",
        "zebra",
    ]


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param({"docs": "https://a.example"}, id="missing-name"),
        pytest.param({"name": "a"}, id="missing-docs"),
        pytest.param("not-a-dict", id="not-a-dict"),
    ],
)
def test_projects_invalid_entry_raises(mocker, entry):
    """Malformed entries fail the build with a clear message."""
    from conda_sphinx_theme import set_config_defaults

    app = make_app(mocker, {"projects": [entry]})

    with pytest.raises(ValueError, match="name"):
        set_config_defaults(app)


def test_projects_filter_script_registered(mocker):
    """The navbar filter needs its client-side script."""
    from conda_sphinx_theme import set_config_defaults

    app = make_app(mocker)
    set_config_defaults(app)

    assert (
        mocker.call(
            "js/projects-filter.js",
        )
        in app.add_js_file.call_args_list
    )


def test_get_projects_page(mocker):
    """The generated page carries the flag the templates use."""
    from conda_sphinx_theme import get_projects_page

    app = make_app_with_builder(mocker, {"projects_page": True})

    pages = list(get_projects_page(app))

    assert len(pages) == 1
    pagename, context, template = pages[0]
    assert pagename == "projects"
    assert template == "projects.html"
    assert context["conda_page"] == "projects"
    assert context["title"] == "Projects"


def test_get_projects_page_disabled(mocker):
    """No page is generated when projects_page is off."""
    from conda_sphinx_theme import get_projects_page

    app = make_app_with_builder(mocker, {"projects_page": False})

    assert list(get_projects_page(app)) == []


def test_get_projects_page_skips_existing_document(mocker):
    """An authored document named projects wins over the generated page."""
    from conda_sphinx_theme import get_projects_page

    app = make_app_with_builder(
        mocker, {"projects_page": True}, found_docs=("projects",)
    )

    assert list(get_projects_page(app)) == []


CONDA_PLUGINS_PAYLOAD = {
    "categories": ["Source code management", "Other"],
    "plugins": [
        {
            "name": "conda-build",
            "docs": "https://docs.example/build",
            "repo_url": "https://github.com/conda/conda-build",
            "category": "Build tools",
        },
        {
            "name": "conda_lock",
            "docs": None,
            "repo_url": "https://github.com/conda/conda-lock",
            "category": "Environment management",
        },
        {
            "name": "no-docs-no-project",
            "docs": None,
            "repo_url": "https://github.com/owner/no-docs",
            "category": "Other",
        },
    ],
}


def test_plugins_loaded_from_url(mocker):
    """The plugin list is fetched, normalised and sorted."""
    from conda_sphinx_theme import set_config_defaults

    response = mocker.MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(
        CONDA_PLUGINS_PAYLOAD
    ).encode()
    urlopen = mocker.patch("conda_sphinx_theme.urlopen", return_value=response)
    app = make_app(
        mocker,
        {
            "projects": [
                {"name": "conda", "docs": "https://docs.example/conda"},
                {"name": "conda-lock", "docs": "https://docs.example/lock"},
            ],
            "plugins_json_url": "https://plugins.example/plugins.json",
        },
    )
    set_config_defaults(app)

    urlopen.assert_called_once()
    plugins = app.builder.theme_options["plugins"]
    assert [entry["name"] for entry in plugins] == [
        "conda-build",
        "conda_lock",
        "no-docs-no-project",
    ]
    by_name = {entry["name"]: entry for entry in plugins}
    assert by_name["conda-build"]["docs"] == "https://docs.example/build"
    # no docs of its own: the project entry supplies one
    assert by_name["conda_lock"]["docs"] == "https://docs.example/lock"
    # neither: fall back to the repository
    assert by_name["no-docs-no-project"]["docs"] == ("https://github.com/owner/no-docs")
    assert by_name["conda-build"]["category"] == "Build tools"
    # badges look the package up under the PEP 503 form of the plugin name
    assert by_name["conda_lock"]["package"] == "conda-lock"
    # no channels key: the page falls back to its default channels
    assert "channels" not in by_name["no-docs-no-project"]


def test_plugins_inherit_project_package_and_channels(mocker):
    """A plugin that is also a project keeps that entry's package and channels."""
    from conda_sphinx_theme import set_config_defaults

    app = make_app(
        mocker,
        {
            "projects": [
                {
                    "name": "conda-build",
                    "docs": "https://docs.example/build",
                    "package": "conda-build",
                    "channels": ["conda-forge"],
                }
            ],
            "plugins": [
                {
                    "name": "conda_build",
                    "repo_url": "https://github.com/conda/conda-build",
                    "category": "Build tools",
                }
            ],
        },
    )
    set_config_defaults(app)

    plugin = app.builder.theme_options["plugins"][0]
    assert plugin["package"] == "conda-build"
    assert plugin["channels"] == ["conda-forge"]
    # and it replaces the project entry
    assert app.builder.theme_options["projects"] == []


def test_plugins_win_over_projects(mocker):
    """A plugin and a project with the same name are listed once, as a plugin."""
    from conda_sphinx_theme import set_config_defaults

    app = make_app(
        mocker,
        {
            "projects": [
                {"name": "conda", "docs": "https://docs.example/conda"},
                {"name": "conda-build", "docs": "https://docs.example/build"},
            ],
            "plugins": [
                {
                    "name": "conda-build",
                    "docs": "https://plugins.example/build",
                    "repo_url": "https://github.com/conda/conda-build",
                }
            ],
        },
    )
    set_config_defaults(app)

    assert [entry["name"] for entry in app.builder.theme_options["projects"]] == [
        "conda"
    ]
    assert [entry["name"] for entry in app.builder.theme_options["plugins"]] == [
        "conda-build"
    ]


def test_plugins_unreachable_warns_and_continues(mocker, caplog):
    """A failing plugin fetch leaves the projects intact."""
    import logging

    from conda_sphinx_theme import set_config_defaults

    mocker.patch("conda_sphinx_theme.urlopen", side_effect=OSError("no route to host"))
    app = make_app(mocker, {"plugins_json_url": "https://plugins.example/plugins.json"})

    with caplog.at_level(logging.WARNING, logger="conda_sphinx_theme"):
        set_config_defaults(app)

    assert app.builder.theme_options["plugins"] == []
    assert app.builder.theme_options["projects"]
    assert "could not read plugins" in caplog.text


def test_plugins_fetch_disabled(mocker):
    """An empty URL means no fetch and no plugins."""
    from conda_sphinx_theme import set_config_defaults

    urlopen = mocker.patch("conda_sphinx_theme.urlopen")
    app = make_app(mocker, {"plugins_json_url": ""})
    set_config_defaults(app)

    urlopen.assert_not_called()
    assert app.builder.theme_options["plugins"] == []


def test_normalize_plugins_skips_unusable_entries():
    """Bad payloads and entries without a usable link are dropped."""
    from conda_sphinx_theme import normalize_plugins

    assert normalize_plugins("not a payload", []) == []
    assert normalize_plugins({}, []) == []

    payload = [
        "not an entry",
        {"docs": "https://docs.example/no-name"},
        {"name": "no-links"},
        {"name": "ok", "repo_url": "https://github.com/owner/ok"},
    ]
    assert [entry["name"] for entry in normalize_plugins(payload, [])] == ["ok"]

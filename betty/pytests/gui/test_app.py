import json
from os import path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog

from betty import fs
from betty.app import App
from betty.config import ConfigurationError
from betty.gui.app import WelcomeWindow, _AboutBettyWindow, BettyMainWindow, ApplicationConfiguration
from betty.gui.error import ExceptionError
from betty.gui.project import ProjectWindow
from betty.gui.serve import ServeDemoWindow
from betty.project import Configuration
from betty.tests import patch_cache


class TestBettyMainWindow:
    @patch_cache
    def test_view_demo_site(self, assert_window, mocker, navigate, qtbot):
        mocker.patch('webbrowser.open_new_tab')
        mocker.patch('betty.gui.serve.ServeDemoWindow._start')

        with App() as app:
            sut = BettyMainWindow(app)
            qtbot.addWidget(sut)
            sut.show()

            navigate(sut, ['betty_menu', '_demo_action'])

            assert_window(ServeDemoWindow)

    @patch_cache
    def test_clear_caches(self, navigate, qtbot):
        with App() as app:
            sut = BettyMainWindow(app)
            qtbot.addWidget(sut)
            sut.show()

            cached_file_path = path.join(fs.CACHE_DIRECTORY_PATH, 'KeepMeAroundPlease')
            open(cached_file_path, 'w').close()
            navigate(sut, ['betty_menu', 'clear_caches_action'])

            with pytest.raises(FileNotFoundError):
                open(cached_file_path)

    def test_open_about_window(self, assert_window, navigate, qtbot) -> None:
        with App() as app:
            sut = BettyMainWindow(app)
            qtbot.addWidget(sut)
            sut.show()

            navigate(sut, ['help_menu', 'about_action'])

            assert_window(_AboutBettyWindow)


class TestWelcomeWindow:
    def test_open_project_with_invalid_file_should_error(self, assert_error, mocker, qtbot, tmpdir) -> None:
        with App() as app:
            sut = WelcomeWindow(app)
            qtbot.addWidget(sut)
            sut.show()

            configuration_file_path = tmpdir.join('betty.json')
            # Purposefully leave the file empty so it is invalid.
            configuration_file_path.write('')
            mocker.patch.object(QFileDialog, 'getOpenFileName', mocker.MagicMock(return_value=[configuration_file_path, None]))
            qtbot.mouseClick(sut.open_project_button, Qt.MouseButton.LeftButton)

            error = assert_error(ExceptionError)
            assert isinstance(error.exception, ConfigurationError)

    def test_open_project_with_valid_file_should_show_project_window(self, assert_window, mocker, qtbot) -> None:
        title = 'My First Ancestry Site'
        configuration = Configuration()
        configuration.title = title
        configuration.write()
        with App() as app:
            app.project.configuration.write()
            sut = WelcomeWindow(app)
            qtbot.addWidget(sut)
            sut.show()

            mocker.patch.object(QFileDialog, 'getOpenFileName', mocker.MagicMock(return_value=[configuration.configuration_file_path, None]))
            qtbot.mouseClick(sut.open_project_button, Qt.MouseButton.LeftButton)

            window = assert_window(ProjectWindow)
            assert window._app.project.configuration.title == title

    def test_view_demo_site(self, assert_window, mocker, qtbot) -> None:
        mocker.patch('webbrowser.open_new_tab')
        mocker.patch('betty.gui.serve.ServeDemoWindow._start')

        with App() as app:
            sut = WelcomeWindow(app)
            qtbot.addWidget(sut)
            sut.show()

            qtbot.mouseClick(sut.demo_button, Qt.MouseButton.LeftButton)

            assert_window(ServeDemoWindow)


class TestApplicationConfiguration:
    async def test_application_configuration_autowrite(self, navigate, qtbot) -> None:
        with App() as app:
            app.configuration.autowrite = True

            sut = ApplicationConfiguration(app)
            qtbot.addWidget(sut)
            sut.show()

            locale = 'nl-NL'
            app.configuration.locale = locale

        with open(app.configuration.configuration_file_path) as f:
            dumped_read_configuration = json.load(f)
        assert dumped_read_configuration == app.configuration.dump()
        assert dumped_read_configuration['locale'] == locale
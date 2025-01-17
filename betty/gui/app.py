import webbrowser
from datetime import datetime
from os import path
from typing import Sequence, Type, TYPE_CHECKING

from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import QFormLayout, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QPushButton

from betty import about, cache
from betty.app import Extension
from betty.asyncio import sync
from betty.gui import BettyWindow, get_configuration_file_filter
from betty.gui.error import catch_exceptions
from betty.gui.serve import ServeDemoWindow
from betty.gui.text import Text
from betty.gui.locale import TranslationsLocaleCollector
from betty.importlib import import_any
from betty.project import ProjectConfiguration

if TYPE_CHECKING:
    from betty.builtins import _


class BettyMainWindow(BettyWindow):
    width = 800
    height = 600

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowIcon(QIcon(path.join(path.dirname(__file__), 'assets', 'public', 'static', 'betty-512x512.png')))
        self._initialize_menu()

    @property
    def title(self) -> str:
        return 'Betty'

    def _initialize_menu(self) -> None:
        menu_bar = self.menuBar()

        self.betty_menu = menu_bar.addMenu('&Betty')

        self.betty_menu.new_project_action = QAction(self)
        self.betty_menu.new_project_action.setShortcut('Ctrl+N')
        self.betty_menu.new_project_action.triggered.connect(lambda _: self.new_project())
        self.betty_menu.addAction(self.betty_menu.new_project_action)

        self.betty_menu.open_project_action = QAction(self)
        self.betty_menu.open_project_action.setShortcut('Ctrl+O')
        self.betty_menu.open_project_action.triggered.connect(lambda _: self.open_project())
        self.betty_menu.addAction(self.betty_menu.open_project_action)

        self.betty_menu._demo_action = QAction(self)
        self.betty_menu._demo_action.triggered.connect(lambda _: self._demo())
        self.betty_menu.addAction(self.betty_menu._demo_action)

        self.betty_menu.open_application_configuration_action = QAction(self)
        self.betty_menu.open_application_configuration_action.triggered.connect(lambda _: self.open_application_configuration())
        self.betty_menu.addAction(self.betty_menu.open_application_configuration_action)

        self.betty_menu.clear_caches_action = QAction(self)
        self.betty_menu.clear_caches_action.triggered.connect(lambda _: self.clear_caches())
        self.betty_menu.addAction(self.betty_menu.clear_caches_action)

        self.betty_menu.exit_action = QAction(self)
        self.betty_menu.exit_action.setShortcut('Ctrl+Q')
        self.betty_menu.exit_action.triggered.connect(QCoreApplication.quit)
        self.betty_menu.addAction(self.betty_menu.exit_action)

        self.help_menu = menu_bar.addMenu('')

        self.help_menu.view_issues_action = QAction(self)
        self.help_menu.view_issues_action.triggered.connect(lambda _: self.view_issues())
        self.help_menu.addAction(self.help_menu.view_issues_action)

        self.help_menu.about_action = QAction(self)
        self.help_menu.about_action.triggered.connect(lambda _: self._about_betty())
        self.help_menu.addAction(self.help_menu.about_action)

    def _do_set_translatables(self) -> None:
        super()._do_set_translatables()
        self.betty_menu.new_project_action.setText(_('New project...'))
        self.betty_menu.open_project_action.setText(_('Open project...'))
        self.betty_menu._demo_action.setText(_('View demo site...'))
        self.betty_menu.open_application_configuration_action.setText(_('Settings...'))
        self.betty_menu.clear_caches_action.setText(_('Clear all caches'))
        self.betty_menu.exit_action.setText(_('Exit'))
        self.help_menu.setTitle('&' + _('Help'))
        self.help_menu.view_issues_action.setText(_('Report bugs and request new features'))
        self.help_menu.about_action.setText(_('About Betty'))

    @catch_exceptions
    def view_issues(self) -> None:
        webbrowser.open_new_tab('https://github.com/bartfeenstra/betty/issues')

    @catch_exceptions
    def _about_betty(self) -> None:
        about_window = _AboutBettyWindow(self._app, self)
        about_window.show()

    @catch_exceptions
    def open_project(self) -> None:
        from betty.gui.project import ProjectWindow

        configuration_file_path, __ = QFileDialog.getOpenFileName(
            self,
            _('Open your project from...'),
            '',
            get_configuration_file_filter(),
        )
        if not configuration_file_path:
            return
        self._app.project.configuration.read(configuration_file_path)
        project_window = ProjectWindow(self._app)
        project_window.show()
        self.close()

    @catch_exceptions
    def new_project(self) -> None:
        from betty.gui.project import ProjectWindow

        configuration_file_path, __ = QFileDialog.getSaveFileName(
            self,
            _('Save your new project to...'),
            '',
            get_configuration_file_filter(),
        )
        if not configuration_file_path:
            return
        configuration = ProjectConfiguration()
        configuration.write(configuration_file_path)
        project_window = ProjectWindow(self._app)
        project_window.show()
        self.close()

    @catch_exceptions
    def _demo(self) -> None:
        serve_window = ServeDemoWindow.get_instance(self._app, self)
        serve_window.show()

    @catch_exceptions
    @sync
    async def clear_caches(self) -> None:
        await cache.clear()

    @catch_exceptions
    def open_application_configuration(self) -> None:
        window = ApplicationConfiguration(self._app, self)
        window.show()


class _WelcomeText(Text):
    pass


class _WelcomeTitle(_WelcomeText):
    pass


class _WelcomeHeading(_WelcomeText):
    pass


class _WelcomeAction(QPushButton):
    pass


class WelcomeWindow(BettyMainWindow):
    # Allow the window to be as narrow as it can be.
    width = 1
    # This is a best guess at the minimum required height, because if we set this to 1, like the width, some of the
    # text will be clipped.
    height = 450

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        central_layout = QVBoxLayout()
        central_layout.addStretch()
        central_widget = QWidget()
        central_widget.setLayout(central_layout)
        self.setCentralWidget(central_widget)

        self._welcome = _WelcomeTitle()
        self._welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        central_layout.addWidget(self._welcome)

        self._welcome_caption = _WelcomeText()
        central_layout.addWidget(self._welcome_caption)

        self._project_instruction = _WelcomeHeading()
        self._project_instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        central_layout.addWidget(self._project_instruction)

        project_layout = QHBoxLayout()
        central_layout.addLayout(project_layout)

        self.open_project_button = _WelcomeAction(self)
        self.open_project_button.released.connect(self.open_project)
        project_layout.addWidget(self.open_project_button)

        self.new_project_button = _WelcomeAction(self)
        self.new_project_button.released.connect(self.new_project)
        project_layout.addWidget(self.new_project_button)

        self._demo_instruction = _WelcomeHeading()
        self._demo_instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        central_layout.addWidget(self._demo_instruction)

        self.demo_button = _WelcomeAction(self)
        self.demo_button.released.connect(self._demo)
        central_layout.addWidget(self.demo_button)

    def _do_set_translatables(self) -> None:
        super()._do_set_translatables()
        self._welcome.setText(_('Welcome to Betty'))
        self._welcome_caption.setText(_('Betty is a static site generator for your <a href="{gramps_url}">Gramps</a> and <a href="{gedcom_url}">GEDCOM</a> family trees.').format(gramps_url='https://gramps-project.org/', gedcom_url='https://en.wikipedia.org/wiki/GEDCOM'))
        self._project_instruction.setText(_('Work on a new or existing site of your own'))
        self.open_project_button.setText(_('Open an existing project'))
        self.new_project_button.setText(_('Create a new project'))
        self._demo_instruction.setText(_('View a demonstration of what a Betty site looks like'))
        self.demo_button.setText(_('View a demo site'))


class _AboutBettyWindow(BettyWindow):
    width = 500
    height = 100

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._label = Text()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(self._label)

    def _do_set_translatables(self) -> None:
        super()._do_set_translatables()
        self._label.setText(''.join(map(lambda x: '<p>%s</p>' % x, [
            _('Version: {version}').format(version=about.version()),
            _('Copyright 2019-{year} <a href="twitter.com/bartFeenstra">Bart Feenstra</a> & contributors. Betty is made available to you under the <a href="https://www.gnu.org/licenses/gpl-3.0.en.html">GNU General Public License, Version 3</a> (GPLv3).').format(year=datetime.now().year),
            _('Follow Betty on <a href="https://twitter.com/Betty_Project">Twitter</a> and <a href="https://github.com/bartfeenstra/betty">Github</a>.'),
        ])))

    @property
    def title(self) -> str:
        return _('About Betty')


class ApplicationConfiguration(BettyWindow):
    width = 400
    height = 150

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._form = QFormLayout()
        form_widget = QWidget()
        form_widget.setLayout(self._form)
        self.setCentralWidget(form_widget)
        locale_collector = TranslationsLocaleCollector(self._app, set(self._app.translations.locales))
        for row in locale_collector.rows:
            self._form.addRow(*row)

    @property
    def title(self) -> str:
        return _('Configuration')

    @property
    def extension_types(self) -> Sequence[Type[Extension]]:
        return [import_any(extension_name) for extension_name in self._EXTENSION_NAMES]

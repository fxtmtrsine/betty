from typing import Set, TYPE_CHECKING

from PyQt6 import QtGui
from PyQt6.QtWidgets import QComboBox, QLabel, QWidget
from babel.core import Locale
from reactives import reactive
from reactives.factory.type import ReactiveInstance

from betty.app import App
from betty.gui.text import Caption
from betty.locale import bcp_47_to_rfc_1766, getdefaultlocale, negotiate_locale

if TYPE_CHECKING:
    from betty.builtins import _


@reactive
class TranslationsLocaleCollector(ReactiveInstance):
    def __init__(self, app: App, allowed_locales: Set[str]):
        super().__init__()
        self._app = app
        self._allowed_locales = allowed_locales

        allowed_locale_names = []
        for allowed_locale in allowed_locales:
            allowed_locale_names.append((allowed_locale, Locale.parse(bcp_47_to_rfc_1766(allowed_locale)).get_display_name()))
        allowed_locale_names = sorted(allowed_locale_names, key=lambda x: x[1])
        # This is the operating system default, for which we'll set a label in self._do_set_translatables()
        allowed_locale_names.insert(0, (None, None))

        def _update_configuration_locale() -> None:
            self._app.configuration.locale = self._configuration_locale.currentData()
        self._configuration_locale = QComboBox()
        for i, (locale, locale_name) in enumerate(allowed_locale_names):
            self._configuration_locale.addItem(locale_name, locale)
            if locale == self._app.configuration.locale:
                self._configuration_locale.setCurrentIndex(i)
        self._configuration_locale.currentIndexChanged.connect(_update_configuration_locale)
        self._configuration_locale_label = QLabel()
        self._configuration_locale_caption = Caption()

        self._set_translatables()

    @property
    def locale(self) -> QComboBox:
        return self._configuration_locale

    @property
    def rows(self):
        return [
            [self._configuration_locale_label, self._configuration_locale],
            [self._configuration_locale_caption],
        ]

    @reactive(on_trigger_call=True)
    def _set_translatables(self) -> None:
        with self._app.acquire_locale():
            self._configuration_locale.setItemText(0, _('Operating system default: {locale_name}').format(
                locale_name=Locale.parse(bcp_47_to_rfc_1766(getdefaultlocale())).get_display_name(locale=bcp_47_to_rfc_1766(self._app.locale)),
            ))
            self._configuration_locale_label.setText(_('Locale'))
            locale = self.locale.currentData()
            if locale is None:
                locale = getdefaultlocale()
            translations_locale = negotiate_locale(
                locale,
                set(self._app.translations.locales),
            )
            if translations_locale is None:
                self._configuration_locale_caption.setText(_('There are no translations for {locale_name}.').format(
                    locale_name=Locale.parse(bcp_47_to_rfc_1766(locale)).get_display_name(locale=bcp_47_to_rfc_1766(self._app.locale)),
                ))
            else:
                negotiated_locale_translations_coverage = self._app.translations.coverage(translations_locale)
                if 'en-US' == translations_locale:
                    negotiated_locale_translations_coverage_percentage = 100
                else:
                    negotiated_locale_translations_coverage_percentage = 100 / (negotiated_locale_translations_coverage[1] / negotiated_locale_translations_coverage[0])
                self._configuration_locale_caption.setText(_('The translations for {locale_name} are {coverage_percentage}% complete.').format(
                    locale_name=Locale.parse(bcp_47_to_rfc_1766(translations_locale)).get_display_name(locale=bcp_47_to_rfc_1766(self._app.locale)),
                    coverage_percentage=round(negotiated_locale_translations_coverage_percentage)
                ))


@reactive
class LocalizedWidget(QWidget, ReactiveInstance):
    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super().showEvent(event)
        self._set_translatables()

    @reactive(on_trigger_call=True)
    def _set_translatables(self) -> None:
        with self._app.acquire_locale():
            self._do_set_translatables()

    def _do_set_translatables(self) -> None:
        pass

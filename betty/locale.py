from __future__ import annotations

import builtins
import calendar
import contextlib
import datetime
import glob
import locale
import operator
import shutil
import threading
from collections import defaultdict
from gettext import NullTranslations, GNUTranslations
from io import StringIO
from contextlib import suppress
from functools import total_ordering
from pathlib import Path
from typing import Optional, Tuple, Union, List, Dict, Callable, Any, Iterator, Set

import babel
from babel import dates, Locale
from babel.messages.frontend import CommandLineInterface
from polib import pofile

from betty import fs
from betty.fs import hashfile, FileSystem


def rfc_1766_to_bcp_47(locale: str) -> str:
    return locale.replace('_', '-')


def bcp_47_to_rfc_1766(locale: str) -> str:
    return locale.replace('-', '_')


def getdefaultlocale() -> str:
    return rfc_1766_to_bcp_47(locale.getdefaultlocale()[0])


class Localized:
    locale: Optional[str]

    def __init__(self, locale: Optional[str] = None):
        super().__init__()
        self.locale = locale


class IncompleteDateError(ValueError):
    pass  # pragma: no cover


@total_ordering
class Date:
    year: Optional[int]
    month: Optional[int]
    day: Optional[int]
    fuzzy: bool

    def __init__(self, year: Optional[int] = None, month: Optional[int] = None, day: Optional[int] = None, fuzzy: bool = False):
        self.year = year
        self.month = month
        self.day = day
        self.fuzzy = fuzzy

    def __repr__(self):
        return '<%s.%s(%s, %s, %s)>' % (self.__class__.__module__, self.__class__.__name__, self.year, self.month, self.day)

    @property
    def comparable(self) -> bool:
        return self.year is not None

    @property
    def complete(self) -> bool:
        return self.year is not None and self.month is not None and self.day is not None

    @property
    def parts(self) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        return self.year, self.month, self.day

    def to_range(self) -> DateRange:
        if not self.comparable:
            raise ValueError('Cannot convert non-comparable date %s to a date range.' % self)
        if self.month is None:
            month_start = 1
            month_end = 12
        else:
            month_start = month_end = self.month
        if self.day is None:
            day_start = 1
            day_end = calendar.monthrange(self.year, month_end)[1]
        else:
            day_start = day_end = self.day
        return DateRange(Date(self.year, month_start, day_start), Date(self.year, month_end, day_end))

    def _compare(self, other, comparator):
        if not isinstance(other, Date):
            return NotImplemented
        selfish = self
        if not selfish.comparable or not other.comparable:
            return NotImplemented
        if selfish.complete and other.complete:
            return comparator(selfish.parts, other.parts)
        if not other.complete:
            other = other.to_range()
        if not selfish.complete:
            selfish = selfish.to_range()
        return comparator(selfish, other)

    def __contains__(self, other):
        if isinstance(other, Date):
            return self == other
        if isinstance(other, DateRange):
            return self in other
        raise TypeError('Expected to check a %s, but a %s was given' % (type(Datey), type(other)))

    def __lt__(self, other):
        return self._compare(other, operator.lt)

    def __le__(self, other):
        return self._compare(other, operator.le)

    def __eq__(self, other):
        if not isinstance(other, Date):
            return NotImplemented
        return self.parts == other.parts

    def __ge__(self, other):
        return self._compare(other, operator.ge)

    def __gt__(self, other):
        return self._compare(other, operator.gt)


@total_ordering
class DateRange:
    start: Optional[Date]
    start_is_boundary: bool
    end: Optional[Date]
    end_is_boundary: bool

    def __init__(self, start: Optional[Date] = None, end: Optional[Date] = None, start_is_boundary: bool = False, end_is_boundary: bool = False):
        self.start = start
        self.start_is_boundary = start_is_boundary
        self.end = end
        self.end_is_boundary = end_is_boundary

    def __repr__(self):
        return '%s.%s(%s, %s, start_is_boundary=%s, end_is_boundary=%s)' % (self.__class__.__module__, self.__class__.__name__, repr(self.start), repr(self.end), repr(self.start_is_boundary), repr(self.end_is_boundary))

    @property
    def comparable(self) -> bool:
        return self.start is not None and self.start.comparable or self.end is not None and self.end.comparable

    def __contains__(self, other):
        if not self.comparable:
            return False

        if isinstance(other, Date):
            others = [other]
        elif isinstance(other, DateRange):
            if not other.comparable:
                return False
            others = []
            if other.start is not None and other.start.comparable:
                others.append(other.start)
            if other.end is not None and other.end.comparable:
                others.append(other.end)
        else:
            raise TypeError('Expected to check a %s, but a %s was given' % (type(Datey), type(other)))

        if self.start is not None and self.end is not None:
            if isinstance(other, DateRange) and (other.start is None or other.end is None):
                if other.start is None:
                    return self.start <= other.end or self.end <= other.end
                if other.end is None:
                    return self.start >= other.start or self.end >= other.start
            for another in others:
                if self.start <= another <= self.end:
                    return True
            if isinstance(other, DateRange):
                for selfdate in [self.start, self.end]:
                    if other.start <= selfdate <= other.end:
                        return True

        elif self.start is not None:
            # Two date ranges with start dates only always overlap.
            if isinstance(other, DateRange) and other.end is None:
                return True

            for other in others:
                if self.start <= other:
                    return True
        elif self.end is not None:
            # Two date ranges with end dates only always overlap.
            if isinstance(other, DateRange) and other.start is None:
                return True

            for other in others:
                if other <= self.end:
                    return True

    def __lt__(self, other):
        if not isinstance(other, (Date, DateRange)):
            return NotImplemented

        if not self.comparable or not other.comparable:
            return NotImplemented

        self_has_start = self.start is not None and self.start.comparable
        self_has_end = self.end is not None and self.end.comparable

        if isinstance(other, DateRange):
            other_has_start = other.start is not None and other.start.comparable
            other_has_end = other.end is not None and other.end.comparable

            if self_has_start and other_has_start:
                if self.start == other.start:
                    # If both end dates are missing or incomparable, we consider them equal.
                    if (self.end is None or not self.end.comparable) and (other.end is None or other.end.comparable):
                        return False
                    if self_has_end and other_has_end:
                        return self.end < other.end
                    return other.end is None
                return self.start < other.start

            if self_has_start:
                return self.start < other.end

            if other_has_start:
                return self.end <= other.start

            return self.end < other.end

        if self_has_start:
            return self.start < other
        if self_has_end:
            return self.end <= other

    def __eq__(self, other):
        if isinstance(other, Date):
            return False

        if not isinstance(other, DateRange):
            return NotImplemented
        return (self.start, self.end, self.start_is_boundary, self.end_is_boundary) == (other.start, other.end, other.start_is_boundary, other.end_is_boundary)


Datey = Union[Date, DateRange]


class TranslationsError(BaseException):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class TranslationsInstallationError(RuntimeError, TranslationsError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class Translations(NullTranslations):
    _Context = Optional[Dict[str, Callable]]

    _GETTEXT_BUILTINS = (
        '_',
        'gettext',
        'lgettext',
        'lngettext',
        'ngettext',
        'npgettext',
        'pgettext',
    )

    _stack: Dict[int, List[Translations]] = defaultdict(list)
    _thread_id: Optional[int] = None

    def __init__(self, fallback: NullTranslations):
        super().__init__()
        self._fallback = fallback
        self._previous_context: Translations._Context = None

    def __enter__(self):
        self.install()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.uninstall()

    def install(self, _=None) -> None:
        if self._previous_context is not None:
            raise TranslationsInstallationError('These translations are installed already.')

        self._previous_context = self._get_current_context()
        super().install(self._GETTEXT_BUILTINS)

        self._thread_id = threading.get_ident()
        self._stack[self._thread_id].insert(0, self)

    def uninstall(self) -> None:
        if self._previous_context is None:
            raise TranslationsInstallationError('These translations are not yet installed.')

        if self != self._stack[self._thread_id][0]:
            raise TranslationsInstallationError(f'These translations were not the last to be installed. {self._stack[self._thread_id].index(self)} other translation(s) must be uninstalled before these translations can be uninstalled as well.')
        del self._stack[self._thread_id][0]

        for key in self._GETTEXT_BUILTINS:
            # Built-ins are not owned by Betty, so allow for them to have disappeared.
            with suppress(KeyError):
                del builtins.__dict__[key]
        builtins.__dict__.update(self._previous_context)
        self._previous_context = None

    def _get_current_context(self) -> _Context:
        return {
            key: value
            for key, value
            in builtins.__dict__.items()
            if key in self._GETTEXT_BUILTINS
        }


class TranslationsRepository:
    def __init__(self, assets: FileSystem):
        self._assets = assets
        self._translations = {}

    @property
    def locales(self) -> Iterator[str]:
        yield 'en-US'
        for assets_directory_path, _ in reversed(self._assets.paths):
            for po_file_path in glob.glob(str(assets_directory_path / 'locale' / '*' / 'LC_MESSAGES' / 'betty.po')):
                yield rfc_1766_to_bcp_47(Path(po_file_path).parents[1].name)

    def __getitem__(self, locale: Any) -> Translations:
        if not isinstance(locale, str):
            raise ValueError(f'The locale to get must be a string, but {type(locale)} was given.')

        try:
            # Wrap the translations in a unique Translations instance, so we can enter a context for the same language
            # more than once.
            return Translations(self._translations[locale])
        except KeyError:
            return Translations(self._build_translations(locale))

    def _build_translations(self, locale: str) -> Translations:
        self._translations[locale] = NullTranslations()
        for assets_directory_path, _ in reversed(self._assets.paths):
            translations = self._open_translations(locale, assets_directory_path)
            if translations:
                translations.add_fallback(self._translations[locale])
                self._translations[locale] = translations
        return self._translations[locale]

    def _open_translations(self, locale: str, assets_directory_path: Path) -> Optional[GNUTranslations]:
        locale_path_name = bcp_47_to_rfc_1766(locale)
        po_file_path = assets_directory_path / 'locale' / locale_path_name / 'LC_MESSAGES' / 'betty.po'
        try:
            translation_version = hashfile(po_file_path)
        except FileNotFoundError:
            return None
        translation_cache_directory_path = fs.CACHE_DIRECTORY_PATH / 'translations' / translation_version
        cache_directory_path = translation_cache_directory_path / locale_path_name / 'LC_MESSAGES'
        mo_file_path = cache_directory_path / 'betty.mo'

        with suppress(FileNotFoundError):
            with open(mo_file_path, 'rb') as f:
                return GNUTranslations(f)

        cache_directory_path.mkdir(exist_ok=True, parents=True)
        with suppress(FileExistsError):
            shutil.copyfile(po_file_path, cache_directory_path / 'betty.po')

        with contextlib.redirect_stdout(StringIO()):
            CommandLineInterface().run(['', 'compile', '-d', translation_cache_directory_path, '-l', locale_path_name, '-D', 'betty'])
        with open(mo_file_path, 'rb') as f:
            return GNUTranslations(f)

    def coverage(self, locale: str) -> Tuple[int, int]:
        translatables = set(self._get_translatables())
        translations = set(self._get_translations(locale))
        return len(translations), len(translatables.union(translations))

    def _get_translatables(self) -> Iterator[str]:
        for assets_directory_path, _ in self._assets.paths:
            with suppress(FileNotFoundError):
                with open(assets_directory_path / 'betty.pot') as f:
                    for entry in pofile(f.read()):
                        yield entry.msgid_with_context

    def _get_translations(self, locale: str) -> Iterator[str]:
        for assets_directory_path, _ in reversed(self._assets.paths):
            with suppress(FileNotFoundError):
                with open(assets_directory_path / 'locale' / bcp_47_to_rfc_1766(locale) / 'LC_MESSAGES' / 'betty.po') as f:
                    for entry in pofile(f.read()):
                        if entry.translated():
                            yield entry.msgid_with_context


def negotiate_locale(preferred_locale: str, available_locales: Set[str]) -> Optional[str]:
    negotiated_locale = babel.negotiate_locale([preferred_locale], available_locales)
    if negotiated_locale is not None:
        return negotiated_locale
    preferred_locale = preferred_locale.split('-', 1)[0]
    for available_locale in available_locales:
        negotiated_locale = babel.negotiate_locale([preferred_locale], [available_locale.split('-', 1)[0]])
        if negotiated_locale is not None:
            return available_locale


def negotiate_localizeds(preferred_locale: str, localizeds: List[Localized]) -> Optional[Localized]:
    negotiated_locale = negotiate_locale(preferred_locale, {localized.locale for localized in localizeds if localized.locale is not None})
    if negotiated_locale is not None:
        for localized in localizeds:
            if localized.locale == negotiated_locale:
                return localized
    for localized in localizeds:
        if localized.locale is None:
            return localized
    with suppress(IndexError):
        return localizeds[0]


def format_datey(date: Datey, locale: str) -> str:
    """
    Formats a datey value into a human-readable string.

    This requires gettext translations to be installed. Use the Translations class to do this temporarily.
    """
    try:
        if isinstance(date, Date):
            return format_date(date, locale)
        return format_date_range(date, locale)
    except IncompleteDateError:
        return _('unknown date')


_FORMAT_DATE_FORMATTERS = {
    (True,): lambda: _('around %(date)s'),
    (False,): lambda: _('%(date)s'),
}


def format_date(date: Date, locale: str) -> str:
    return _FORMAT_DATE_FORMATTERS[(date.fuzzy,)]() % {
        'date': _format_date_parts(date, locale),
    }


_FORMAT_DATE_PARTS_FORMATTERS = {
    (True, True, True): lambda: _('MMMM d, y'),
    (True, True, False): lambda: _('MMMM, y'),
    (True, False, False): lambda: _('y'),
    (False, True, True): lambda: _('MMMM d'),
    (False, True, False): lambda: _('MMMM'),
}


def _format_date_parts(date: Date, locale: str) -> str:
    if date is None:
        raise IncompleteDateError('This date is None.')
    try:
        date_parts_format = _FORMAT_DATE_PARTS_FORMATTERS[tuple(map(lambda x: x is not None, date.parts))]()
    except KeyError:
        raise IncompleteDateError('This date does not have enough parts to be rendered.')
    parts = map(lambda x: 1 if x is None else x, date.parts)
    return dates.format_date(datetime.date(*parts), date_parts_format, Locale.parse(bcp_47_to_rfc_1766(locale)))


_FORMAT_DATE_RANGE_FORMATTERS = {
    (False, False, False, False): lambda: _('from %(start_date)s until %(end_date)s'),
    (False, False, False, True): lambda: _('from %(start_date)s until sometime before %(end_date)s'),
    (False, False, True, False): lambda: _('from %(start_date)s until around %(end_date)s'),
    (False, False, True, True): lambda: _('from %(start_date)s until sometime before around %(end_date)s'),
    (False, True, False, False): lambda: _('from sometime after %(start_date)s until %(end_date)s'),
    (False, True, False, True): lambda: _('sometime between %(start_date)s and %(end_date)s'),
    (False, True, True, False): lambda: _('from sometime after %(start_date)s until around %(end_date)s'),
    (False, True, True, True): lambda: _('sometime between %(start_date)s and around %(end_date)s'),
    (True, False, False, False): lambda: _('from around %(start_date)s until %(end_date)s'),
    (True, False, False, True): lambda: _('from around %(start_date)s until sometime before %(end_date)s'),
    (True, False, True, False): lambda: _('from around %(start_date)s until around %(end_date)s'),
    (True, False, True, True): lambda: _('from around %(start_date)s until sometime before around %(end_date)s'),
    (True, True, False, False): lambda: _('from sometime after around %(start_date)s until %(end_date)s'),
    (True, True, False, True): lambda: _('sometime between around %(start_date)s and %(end_date)s'),
    (True, True, True, False): lambda: _('from sometime after around %(start_date)s until around %(end_date)s'),
    (True, True, True, True): lambda: _('sometime between around %(start_date)s and around %(end_date)s'),
    (False, False, None, None): lambda: _('from %(start_date)s'),
    (False, True, None, None): lambda: _('sometime after %(start_date)s'),
    (True, False, None, None): lambda: _('from around %(start_date)s'),
    (True, True, None, None): lambda: _('sometime after around %(start_date)s'),
    (None, None, False, False): lambda: _('until %(end_date)s'),
    (None, None, False, True): lambda: _('sometime before %(end_date)s'),
    (None, None, True, False): lambda: _('until around %(end_date)s'),
    (None, None, True, True): lambda: _('sometime before around %(end_date)s'),
}


def format_date_range(date_range: DateRange, locale: str) -> str:
    formatter_configuration = ()
    formatter_arguments = {}

    try:
        formatter_arguments['start_date'] = _format_date_parts(date_range.start, locale)
        formatter_configuration += (date_range.start.fuzzy, date_range.start_is_boundary)
    except IncompleteDateError:
        formatter_configuration += (None, None)

    try:
        formatter_arguments['end_date'] = _format_date_parts(date_range.end, locale)
        formatter_configuration += (date_range.end.fuzzy, date_range.end_is_boundary)
    except IncompleteDateError:
        formatter_configuration += (None, None)

    if not formatter_arguments:
        raise IncompleteDateError('This date range does not have enough parts to be rendered.')

    return _FORMAT_DATE_RANGE_FORMATTERS[formatter_configuration]() % formatter_arguments

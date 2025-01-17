import os
import unittest
from json import dump
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Dict
from unittest.mock import patch

import click
from click.testing import CliRunner

from betty import fs
from betty.error import UserFacingError
from betty.os import ChDir
from betty.project import ProjectConfiguration
from betty.serve import Server
from betty.tests import patch_cache, TestCase

try:
    from unittest.mock import AsyncMock
except ImportError:
    from mock.mock import AsyncMock

from betty.cli import main, CommandProvider, global_command, catch_exceptions
from betty.app import App, Extension


class TestCommandError(BaseException):
    pass


class TestExtension(Extension, CommandProvider):
    @property
    def commands(self) -> Dict[str, Callable]:
        return {
            'test': self._test_command,
        }

    @click.command(name='test')
    @global_command
    async def _test_command(self):
        raise TestCommandError


@patch('sys.stderr')
@patch('sys.stdout')
class MainTest(TestCase):
    def test_without_arguments(self, _, __):
        runner = CliRunner()
        result = runner.invoke(main, catch_exceptions=False)
        self.assertEqual(0, result.exit_code)

    def test_help_without_configuration(self, _, __):
        runner = CliRunner()
        result = runner.invoke(main, ('--help',), catch_exceptions=False)
        self.assertEqual(0, result.exit_code)

    def test_configuration_without_help(self, _, __):
        with TemporaryDirectory() as working_directory_path:
            configuration_file_path = Path(working_directory_path) / 'betty.json'
            url = 'https://example.com'
            config_dict = {
                'base_url': url,
            }
            with open(configuration_file_path, 'w') as f:
                dump(config_dict, f)

            runner = CliRunner()
            result = runner.invoke(main, ('-c', configuration_file_path), catch_exceptions=False)
            self.assertEqual(2, result.exit_code)

    def test_help_with_configuration(self, _, __):
        with TemporaryDirectory() as working_directory_path:
            configuration_file_path = Path(working_directory_path) / 'betty.json'
            url = 'https://example.com'
            config_dict = {
                'base_url': url,
                'extensions': {
                    TestExtension.name(): {},
                },
            }
            with open(configuration_file_path, 'w') as f:
                dump(config_dict, f)

            runner = CliRunner()
            result = runner.invoke(main, ('-c', configuration_file_path, '--help',), catch_exceptions=False)
            self.assertEqual(0, result.exit_code)

    def test_help_with_invalid_configuration_file_path(self, _, __):
        with TemporaryDirectory() as working_directory_path:
            configuration_file_path = Path(working_directory_path) / 'non-existent-betty.json'

            runner = CliRunner()
            result = runner.invoke(main, ('-c', configuration_file_path, '--help',), catch_exceptions=False)
            self.assertEqual(1, result.exit_code)

    def test_help_with_invalid_configuration(self, _, __):
        with TemporaryDirectory() as working_directory_path:
            configuration_file_path = Path(working_directory_path) / 'betty.json'
            config_dict = {}
            with open(configuration_file_path, 'w') as f:
                dump(config_dict, f)

            runner = CliRunner()
            result = runner.invoke(main, ('-c', configuration_file_path, '--help',), catch_exceptions=False)
            self.assertEqual(1, result.exit_code)

    def test_with_discovered_configuration(self, _, __):
        with TemporaryDirectory() as working_directory_path:
            with open(Path(working_directory_path) / 'betty.json', 'w') as config_file:
                url = 'https://example.com'
                config_dict = {
                    'base_url': url,
                    'extensions': {
                        TestExtension.name(): None,
                    },
                }
                dump(config_dict, config_file)
            with ChDir(working_directory_path):
                runner = CliRunner()
                result = runner.invoke(main, ('test',), catch_exceptions=False)
                self.assertEqual(1, result.exit_code)


class CatchExceptionsTest(unittest.TestCase):
    def test_logging_user_facing_error(self) -> None:
        error_message = 'Something went wrong!'
        with self.assertLogs() as watcher:
            with self.assertRaises(SystemExit):
                with catch_exceptions():
                    raise UserFacingError(error_message)
            self.assertEqual('ERROR:root:%s' % error_message, watcher.output[0])

    def test_logging_uncaught_exception(self) -> None:
        error_message = 'Something went wrong!'
        with self.assertLogs() as watcher:
            with self.assertRaises(SystemExit):
                with catch_exceptions():
                    raise Exception(error_message)
            self.assertTrue(watcher.output[0].startswith('ERROR:root:%s' % error_message))
            self.assertIn('Traceback', watcher.output[0])


class VersionTest(TestCase):
    def test(self):
        runner = CliRunner()
        result = runner.invoke(main, ('--version'), catch_exceptions=False)
        self.assertEqual(0, result.exit_code)
        self.assertIn('Betty', result.stdout)


class ClearCachesTest(TestCase):
    @patch_cache
    def test(self):
        cached_file_path = Path(fs.CACHE_DIRECTORY_PATH) / 'KeepMeAroundPlease'
        open(cached_file_path, 'w').close()
        runner = CliRunner()
        result = runner.invoke(main, ('clear-caches',), catch_exceptions=False)
        self.assertEqual(0, result.exit_code)
        with self.assertRaises(FileNotFoundError):
            open(cached_file_path)


class DemoTest(TestCase):
    @patch('betty.serve.AppServer', new_callable=lambda: _KeyboardInterruptedServer)
    def test(self, m_server):
        runner = CliRunner()
        result = runner.invoke(main, ('demo',), catch_exceptions=False)
        self.assertEqual(0, result.exit_code)


class GenerateTest(TestCase):
    @patch('betty.generate.generate', new_callable=AsyncMock)
    @patch('betty.load.load', new_callable=AsyncMock)
    def test(self, m_parse, m_generate):
        with TemporaryDirectory() as working_directory_path:
            configuration_file_path = Path(working_directory_path) / 'betty.json'
            url = 'https://example.com'
            config_dict = {
                'base_url': url,
            }
            with open(configuration_file_path, 'w') as f:
                dump(config_dict, f)

            runner = CliRunner()
            result = runner.invoke(main, ('-c', configuration_file_path, 'generate',), catch_exceptions=False)
            self.assertEqual(0, result.exit_code)

            m_parse.assert_called_once()
            parse_args, parse_kwargs = m_parse.await_args
            self.assertEqual(1, len(parse_args))
            self.assertIsInstance(parse_args[0], App)
            self.assertEqual({}, parse_kwargs)

            m_generate.assert_called_once()
            render_args, render_kwargs = m_generate.call_args
            self.assertEqual(1, len(render_args))
            self.assertIsInstance(render_args[0], App)
            self.assertEqual({}, render_kwargs)


class _KeyboardInterruptedServer(Server):
    def __init__(self, *args, **kwargs):
        pass

    async def start(self) -> None:
        raise KeyboardInterrupt


class ServeTest(TestCase):
    @patch('betty.serve.AppServer', new_callable=lambda: _KeyboardInterruptedServer)
    def test(self, m_server):
        configuration = ProjectConfiguration()
        configuration.write()
        os.makedirs(configuration.www_directory_path)
        runner = CliRunner()
        result = runner.invoke(main, ('-c', configuration.configuration_file_path, 'serve',), catch_exceptions=False)
        self.assertEqual(0, result.exit_code)

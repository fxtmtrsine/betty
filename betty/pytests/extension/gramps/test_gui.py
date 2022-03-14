from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog
from reactives import ReactiveList

from betty.app import App, AppExtensionConfiguration
from betty.asyncio import sync
from betty.gramps import Gramps, GrampsConfiguration
from betty.gramps.config import FamilyTreeConfiguration
from betty.gramps.gui import _AddFamilyTreeWindow


@sync
async def test_add_family_tree_set_path(assert_not_window, assert_window, tmpdir, qtbot) -> None:
    async with App() as app:
        app.configuration.extensions.add(AppExtensionConfiguration(Gramps))
        sut = app.extensions[Gramps]
        widget = sut.gui_build()
        qtbot.addWidget(widget)
        widget.show()

        qtbot.mouseClick(widget._add_family_tree_button, Qt.MouseButton.LeftButton)
        add_family_tree_window = assert_window(_AddFamilyTreeWindow)

        file_path = '/tmp/family-tree.gpkg'
        add_family_tree_window._widget._file_path.setText(file_path)

        qtbot.mouseClick(add_family_tree_window._widget._save_and_close, Qt.MouseButton.LeftButton)
        assert_not_window(_AddFamilyTreeWindow)

        assert len(sut._configuration.family_trees) == 1
        family_tree = sut._configuration.family_trees[0]
        assert family_tree.file_path == Path(file_path)


@sync
async def test_add_family_tree_find_path(assert_window, mocker, tmpdir, qtbot) -> None:
    async with App() as app:
        app.configuration.extensions.add(AppExtensionConfiguration(Gramps))
        sut = app.extensions[Gramps]
        widget = sut.gui_build()
        qtbot.addWidget(widget)
        widget.show()

        qtbot.mouseClick(widget._add_family_tree_button, Qt.MouseButton.LeftButton)

        add_family_tree_window = assert_window(_AddFamilyTreeWindow)
        file_path = '/tmp/family-tree.gpkg'
        mocker.patch.object(QFileDialog, 'getOpenFileName', mocker.MagicMock(return_value=[file_path, None]))
        qtbot.mouseClick(add_family_tree_window._widget._file_path_find, Qt.MouseButton.LeftButton)
        qtbot.mouseClick(add_family_tree_window._widget._save_and_close, Qt.MouseButton.LeftButton)

        assert len(sut._configuration.family_trees) == 1
        family_tree = sut._configuration.family_trees[0]
        assert family_tree.file_path == Path(file_path)


@sync
async def test_remove_family_tree(tmpdir, qtbot) -> None:
    async with App() as app:
        app.configuration.extensions.add(AppExtensionConfiguration(
            Gramps,
            extension_configuration=GrampsConfiguration(
                family_trees=ReactiveList([
                    FamilyTreeConfiguration('/tmp/family-tree.gpkg'),
                ])
            ),
        ))
        sut = app.extensions[Gramps]
        widget = sut.gui_build()
        qtbot.addWidget(widget)
        widget.show()

        qtbot.mouseClick(widget._family_trees_widget._remove_buttons[0], Qt.MouseButton.LeftButton)

        assert len(sut._configuration.family_trees) == 0
        assert [] == widget._family_trees_widget._remove_buttons

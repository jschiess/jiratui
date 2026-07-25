from pathlib import Path
import re
from typing import cast
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from pydantic import SecretStr
import pytest

import jiratui
from jiratui.api_controller.controller import APIController
from jiratui.app import JiraApp
from jiratui.config import ApplicationConfiguration
from jiratui.keys import (
    KNOWN_BINDING_IDS,
    VIM_KEYMAP,
    VimCommand,
    build_keymap,
    effective_key,
    parse_vim_command,
    unknown_binding_ids,
    vim_keybindings_enabled,
)
from jiratui.models import JiraIssue, JiraIssueSearchResponse, WorkItemsSearchOrderBy
from jiratui.widgets.screen import MainScreen, WorkItemSearchResult
from jiratui.widgets.screens.vim import VimCommandScreen


def _config(**overrides) -> ApplicationConfiguration:
    config_mock = Mock(spec=ApplicationConfiguration)
    config_mock.configure_mock(
        jira_api_base_url='foo.bar',
        jira_api_username='foo',
        jira_api_token=SecretStr('bar'),
        jira_api_version=3,
        use_bearer_authentication=False,
        cloud=True,
        ignore_users_without_email=True,
        default_project_key_or_id=None,
        active_sprint_on_startup=False,
        jira_account_id=None,
        tui_title=None,
        tui_custom_title=None,
        tui_title_include_jira_server_title=False,
        on_start_up_only_fetch_projects=False,
        log_file='',
        log_level='ERROR',
        enable_logging=False,
        theme=None,
        search_results_page_filtering_enabled=False,
        ssl=None,
        search_results_default_order=WorkItemsSearchOrderBy.CREATED_DESC,
        search_on_startup=False,
        show_keybinding_hints=False,
        enable_recent_history=False,
        enable_goto=False,
        confirm_before_quit=False,
        search_results_truncate_work_item_summary=10,
        search_results_style_work_item_status=False,
        search_results_style_work_item_type=False,
        search_results_per_page=10,
        enable_vim_keybindings=False,
        keybindings=None,
    )
    config_mock.configure_mock(**overrides)
    return config_mock


def _app(**overrides) -> JiraApp:
    config_mock = _config(**overrides)
    app = JiraApp(config_mock)
    app.api = APIController(config_mock)
    app._setup_logging = MagicMock()  # type:ignore[method-assign]
    return app


@pytest.fixture()
def app() -> JiraApp:
    return _app()


@pytest.fixture()
def vim_app() -> JiraApp:
    return _app(enable_vim_keybindings=True)


# -- keymap --


def test_keymap_is_empty_by_default():
    assert build_keymap(_config()) == {}


def test_keymap_with_vim_keybindings_enabled():
    assert build_keymap(_config(enable_vim_keybindings=True)) == VIM_KEYMAP


def test_keymap_with_user_defined_keybindings():
    keymap = build_keymap(_config(keybindings={'main.find_by_text': 'ctrl+f'}))

    assert keymap == {'main.find_by_text': 'ctrl+f'}


def test_user_defined_keybindings_take_precedence_over_the_vim_keybindings():
    keymap = build_keymap(
        _config(enable_vim_keybindings=True, keybindings={'app.quit': 'ctrl+q,Q'})
    )

    assert keymap['app.quit'] == 'ctrl+q,Q'
    assert keymap['main.focus_jql'] == VIM_KEYMAP['main.focus_jql']


def test_keymap_ignores_empty_keys():
    assert build_keymap(_config(keybindings={'app.quit': '  '})) == {}


def test_vim_keybindings_are_disabled_by_default():
    assert vim_keybindings_enabled(_config()) is False
    assert vim_keybindings_enabled(_config(enable_vim_keybindings=True)) is True


def test_unknown_binding_ids():
    config = _config(keybindings={'app.quit': 'q', 'app.does_not_exist': 'x'})

    assert unknown_binding_ids(config) == ['app.does_not_exist']


def test_effective_key():
    assert effective_key('main.focus_jql', 'j', _config()) == 'j'
    assert effective_key('main.focus_jql', 'j', _config(enable_vim_keybindings=True)) == 'J'
    assert (
        effective_key('main.focus_jql', 'j', _config(keybindings={'main.focus_jql': 'ctrl+j,x'}))
        == 'ctrl+j'
    )


def test_every_binding_id_in_the_code_base_is_documented():
    """The IDs used by the widgets must be listed in `KNOWN_BINDING_IDS` so they can be re-mapped and validated."""

    ids = set()
    for source_file in Path(jiratui.__file__).parent.rglob('*.py'):
        source = source_file.read_text(encoding='utf-8')
        for start in (match.end() for match in re.finditer(r'Binding\(', source)):
            depth, position = 1, start
            while depth:
                if source[position] == '(':
                    depth += 1
                elif source[position] == ')':
                    depth -= 1
                position += 1
            ids.update(re.findall(r"id='([^']+)'", source[start:position]))

    assert ids == set(KNOWN_BINDING_IDS)


def test_vim_keymap_only_contains_known_binding_ids():
    assert set(VIM_KEYMAP) <= set(KNOWN_BINDING_IDS)


# -- the Vim-like command line --


@pytest.mark.parametrize('value', [':q', 'q', ' :q ', ':quit', 'x', 'wq'])
def test_parse_quit_command(value: str):
    command, _ = parse_vim_command(value)

    assert command == VimCommand.QUIT


@pytest.mark.parametrize('value', [':q!', 'q!', ':quit!', 'qa!'])
def test_parse_force_quit_command(value: str):
    command, _ = parse_vim_command(value)

    assert command == VimCommand.FORCE_QUIT


@pytest.mark.parametrize('value', [':h', 'help'])
def test_parse_help_command(value: str):
    command, _ = parse_vim_command(value)

    assert command == VimCommand.HELP


@pytest.mark.parametrize('value', ['', None, ':w', 'foo'])
def test_parse_unknown_command(value: str | None):
    command, cleaned = parse_vim_command(value)

    assert command == VimCommand.UNKNOWN
    assert not cleaned.startswith(':')


def test_run_quit_command(app: JiraApp):
    app.action_quit = Mock()  # type:ignore[method-assign]
    app.run_worker = Mock()  # type:ignore[method-assign]

    app._handle_vim_command(':q')

    app.action_quit.assert_called_once()
    app.run_worker.assert_called_once()


def test_run_force_quit_command(app: JiraApp):
    app._exit_application = Mock()  # type:ignore[method-assign]
    app.run_worker = Mock()  # type:ignore[method-assign]

    app._handle_vim_command(':q!')

    app._exit_application.assert_called_once()


def test_run_unknown_command(app: JiraApp):
    app.notify = Mock()  # type:ignore[method-assign]
    app.run_worker = Mock()  # type:ignore[method-assign]

    app._handle_vim_command(':foo')

    app.run_worker.assert_not_called()
    assert 'E492' in app.notify.call_args.args[0]


def test_dismissing_the_command_line_does_nothing(app: JiraApp):
    app.run_worker = Mock()  # type:ignore[method-assign]
    app.notify = Mock()  # type:ignore[method-assign]

    app._handle_vim_command(None)

    app.run_worker.assert_not_called()
    app.notify.assert_not_called()


# -- the Vim-like keybindings in the UI --


@patch('jiratui.widgets.screen.MainScreen.fetch_issue')
@patch('jiratui.widgets.screen.MainScreen._search_work_items')
@patch('jiratui.widgets.screen.MainScreen.fetch_statuses')
@patch('jiratui.widgets.screen.MainScreen.fetch_issue_types')
@patch('jiratui.widgets.screen.MainScreen.fetch_projects')
@pytest.mark.asyncio
async def test_j_and_k_move_the_cursor_of_the_search_results(
    fetch_projects_mock: AsyncMock,
    fetch_issue_types_mock: AsyncMock,
    fetch_statuses_mock: AsyncMock,
    search_work_items_mock: AsyncMock,
    fetch_issue_mock: AsyncMock,
    jira_issues: list[JiraIssue],
    vim_app: JiraApp,
):
    async with vim_app.run_test() as pilot:
        # GIVEN
        search_work_items_mock.return_value = WorkItemSearchResult(
            total=2, response=JiraIssueSearchResponse(issues=jira_issues)
        )
        main_screen = cast(MainScreen, vim_app.screen)
        await pilot.press('ctrl+r')
        # WHEN
        await pilot.press('j')
        # THEN
        assert main_screen.search_results_table.current_work_item_key == jira_issues[1].key
        # WHEN
        await pilot.press('k')
        # THEN
        assert main_screen.search_results_table.current_work_item_key == jira_issues[0].key
        # WHEN
        await pilot.press('G')
        # THEN
        assert main_screen.search_results_table.current_work_item_key == jira_issues[1].key
        # WHEN
        await pilot.press('g')
        # THEN
        assert main_screen.search_results_table.current_work_item_key == jira_issues[0].key


@patch('jiratui.widgets.screen.MainScreen._search_work_items')
@patch('jiratui.widgets.screen.MainScreen.fetch_statuses')
@patch('jiratui.widgets.screen.MainScreen.fetch_issue_types')
@patch('jiratui.widgets.screen.MainScreen.fetch_projects')
@pytest.mark.asyncio
async def test_j_focuses_the_jql_input_when_the_vim_keybindings_are_disabled(
    fetch_projects_mock: AsyncMock,
    fetch_issue_types_mock: AsyncMock,
    fetch_statuses_mock: AsyncMock,
    search_work_items_mock: AsyncMock,
    jira_issues: list[JiraIssue],
    app: JiraApp,
):
    async with app.run_test() as pilot:
        # GIVEN
        search_work_items_mock.return_value = WorkItemSearchResult(
            total=2, response=JiraIssueSearchResponse(issues=jira_issues)
        )
        await pilot.press('ctrl+r')
        # WHEN
        await pilot.press('j')
        # THEN
        assert app.focused.id == 'input_search_term'


@patch('jiratui.widgets.screen.MainScreen.fetch_statuses')
@patch('jiratui.widgets.screen.MainScreen.fetch_issue_types')
@patch('jiratui.widgets.screen.MainScreen.fetch_projects')
@pytest.mark.asyncio
async def test_the_inputs_that_use_j_and_k_are_re_mapped(
    fetch_projects_mock: AsyncMock,
    fetch_issue_types_mock: AsyncMock,
    fetch_statuses_mock: AsyncMock,
    vim_app: JiraApp,
):
    async with vim_app.run_test() as pilot:
        # WHEN
        await pilot.press('J')
        # THEN
        assert vim_app.focused.id == 'input_search_term'
        # WHEN
        await pilot.press('escape')
        await pilot.press('K')
        # THEN
        assert vim_app.focused.id == 'input_issue_key'


@patch('jiratui.widgets.screen.MainScreen.fetch_statuses')
@patch('jiratui.widgets.screen.MainScreen.fetch_issue_types')
@patch('jiratui.widgets.screen.MainScreen.fetch_projects')
@pytest.mark.asyncio
async def test_j_and_k_move_between_the_search_filters(
    fetch_projects_mock: AsyncMock,
    fetch_issue_types_mock: AsyncMock,
    fetch_statuses_mock: AsyncMock,
    vim_app: JiraApp,
):
    async with vim_app.run_test() as pilot:
        # GIVEN: the project dropdown is focused
        main_screen = cast(MainScreen, vim_app.screen)
        main_screen.project_selector.focus()
        # WHEN
        await pilot.press('j')
        # THEN: the focus moved to the next filter instead of the JQL input
        assert vim_app.focused is main_screen.issue_type_selector
        # WHEN
        await pilot.press('k')
        # THEN
        assert vim_app.focused is main_screen.project_selector


@patch('jiratui.widgets.screen.MainScreen.fetch_statuses')
@patch('jiratui.widgets.screen.MainScreen.fetch_issue_types')
@patch('jiratui.widgets.screen.MainScreen.fetch_projects')
@pytest.mark.asyncio
async def test_the_hint_of_the_jql_input_shows_the_re_mapped_key(
    fetch_projects_mock: AsyncMock,
    fetch_issue_types_mock: AsyncMock,
    fetch_statuses_mock: AsyncMock,
    vim_app: JiraApp,
):
    async with vim_app.run_test():
        main_screen = cast(MainScreen, vim_app.screen)

        assert main_screen.jql_expression_input.border_subtitle == '(J)'
        assert main_screen.issue_key_input.border_subtitle == '(K)'


@patch('jiratui.widgets.screen.MainScreen.fetch_statuses')
@patch('jiratui.widgets.screen.MainScreen.fetch_issue_types')
@patch('jiratui.widgets.screen.MainScreen.fetch_projects')
@pytest.mark.asyncio
async def test_h_and_l_move_between_the_panes(
    fetch_projects_mock: AsyncMock,
    fetch_issue_types_mock: AsyncMock,
    fetch_statuses_mock: AsyncMock,
    vim_app: JiraApp,
):
    async with vim_app.run_test() as pilot:
        # GIVEN
        main_screen = cast(MainScreen, vim_app.screen)
        main_screen.search_results_table.focus()
        # WHEN
        await pilot.press('l')
        # THEN
        assert vim_app.focused is not main_screen.search_results_table
        # WHEN
        await pilot.press('h')
        # THEN
        assert vim_app.focused is main_screen.search_results_table


@patch('jiratui.widgets.screen.MainScreen.fetch_statuses')
@patch('jiratui.widgets.screen.MainScreen.fetch_issue_types')
@patch('jiratui.widgets.screen.MainScreen.fetch_projects')
@pytest.mark.asyncio
async def test_escape_goes_back_to_the_work_items(
    fetch_projects_mock: AsyncMock,
    fetch_issue_types_mock: AsyncMock,
    fetch_statuses_mock: AsyncMock,
    vim_app: JiraApp,
):
    async with vim_app.run_test() as pilot:
        # GIVEN: the details of a work item are focused
        main_screen = cast(MainScreen, vim_app.screen)
        await pilot.press('3')
        assert vim_app.focused is main_screen.issue_details_widget
        # WHEN
        await pilot.press('escape')
        # THEN
        assert vim_app.focused is main_screen.search_results_table


@patch('jiratui.widgets.screen.MainScreen.fetch_statuses')
@patch('jiratui.widgets.screen.MainScreen.fetch_issue_types')
@patch('jiratui.widgets.screen.MainScreen.fetch_projects')
@pytest.mark.asyncio
async def test_escape_does_not_move_the_focus_when_the_vim_keybindings_are_disabled(
    fetch_projects_mock: AsyncMock,
    fetch_issue_types_mock: AsyncMock,
    fetch_statuses_mock: AsyncMock,
    app: JiraApp,
):
    async with app.run_test() as pilot:
        # GIVEN
        main_screen = cast(MainScreen, app.screen)
        await pilot.press('3')
        # WHEN
        await pilot.press('escape')
        # THEN
        assert app.focused is main_screen.issue_details_widget


@patch('jiratui.widgets.screen.MainScreen.fetch_statuses')
@patch('jiratui.widgets.screen.MainScreen.fetch_issue_types')
@patch('jiratui.widgets.screen.MainScreen.fetch_projects')
@pytest.mark.asyncio
async def test_slash_filters_the_current_page_of_search_results(
    fetch_projects_mock: AsyncMock,
    fetch_issue_types_mock: AsyncMock,
    fetch_statuses_mock: AsyncMock,
    vim_app: JiraApp,
):
    vim_app.config.search_results_page_filtering_enabled = True
    async with vim_app.run_test() as pilot:
        # GIVEN
        main_screen = cast(MainScreen, vim_app.screen)
        main_screen.search_results_table.focus()
        # WHEN
        await pilot.press('/')
        # THEN
        assert vim_app.focused is main_screen.search_results_filter_input


@patch('jiratui.widgets.screen.MainScreen.fetch_statuses')
@patch('jiratui.widgets.screen.MainScreen.fetch_issue_types')
@patch('jiratui.widgets.screen.MainScreen.fetch_projects')
@pytest.mark.asyncio
async def test_colon_opens_the_command_line(
    fetch_projects_mock: AsyncMock,
    fetch_issue_types_mock: AsyncMock,
    fetch_statuses_mock: AsyncMock,
    vim_app: JiraApp,
):
    async with vim_app.run_test() as pilot:
        # WHEN
        await pilot.press(':')
        # THEN
        assert isinstance(vim_app.screen, VimCommandScreen)


@patch('jiratui.widgets.screen.MainScreen.fetch_statuses')
@patch('jiratui.widgets.screen.MainScreen.fetch_issue_types')
@patch('jiratui.widgets.screen.MainScreen.fetch_projects')
@pytest.mark.asyncio
async def test_colon_does_nothing_when_the_vim_keybindings_are_disabled(
    fetch_projects_mock: AsyncMock,
    fetch_issue_types_mock: AsyncMock,
    fetch_statuses_mock: AsyncMock,
    app: JiraApp,
):
    async with app.run_test() as pilot:
        # WHEN
        await pilot.press(':')
        # THEN
        assert isinstance(app.screen, MainScreen)


@patch('jiratui.widgets.screen.MainScreen.fetch_statuses')
@patch('jiratui.widgets.screen.MainScreen.fetch_issue_types')
@patch('jiratui.widgets.screen.MainScreen.fetch_projects')
@pytest.mark.asyncio
async def test_q_quits_the_application(
    fetch_projects_mock: AsyncMock,
    fetch_issue_types_mock: AsyncMock,
    fetch_statuses_mock: AsyncMock,
    vim_app: JiraApp,
):
    vim_app._exit_application = AsyncMock()  # type:ignore[method-assign]
    async with vim_app.run_test() as pilot:
        # GIVEN
        main_screen = cast(MainScreen, vim_app.screen)
        main_screen.search_results_table.focus()
        # WHEN
        await pilot.press('q')
        # THEN
        vim_app._exit_application.assert_awaited_once()


@patch('jiratui.widgets.screen.MainScreen.fetch_statuses')
@patch('jiratui.widgets.screen.MainScreen.fetch_issue_types')
@patch('jiratui.widgets.screen.MainScreen.fetch_projects')
@pytest.mark.asyncio
async def test_q_does_not_quit_when_typing_in_an_input(
    fetch_projects_mock: AsyncMock,
    fetch_issue_types_mock: AsyncMock,
    fetch_statuses_mock: AsyncMock,
    vim_app: JiraApp,
):
    vim_app._exit_application = AsyncMock()  # type:ignore[method-assign]
    async with vim_app.run_test() as pilot:
        # GIVEN
        main_screen = cast(MainScreen, vim_app.screen)
        main_screen.issue_key_input.focus()
        # WHEN
        await pilot.press('q')
        # THEN
        vim_app._exit_application.assert_not_awaited()
        assert main_screen.issue_key_input.value == 'q'


@patch('jiratui.widgets.screen.MainScreen.fetch_statuses')
@patch('jiratui.widgets.screen.MainScreen.fetch_issue_types')
@patch('jiratui.widgets.screen.MainScreen.fetch_projects')
@pytest.mark.asyncio
async def test_user_defined_keybindings_are_applied(
    fetch_projects_mock: AsyncMock,
    fetch_issue_types_mock: AsyncMock,
    fetch_statuses_mock: AsyncMock,
):
    app = _app(keybindings={'main.focus_jql': 'ctrl+b'})
    async with app.run_test() as pilot:
        # WHEN
        await pilot.press('ctrl+b')
        # THEN
        assert app.focused.id == 'input_search_term'

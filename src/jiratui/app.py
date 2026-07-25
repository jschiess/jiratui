import logging
import os
from pathlib import Path
import sys

from pythonjsonlogger.json import JsonFormatter
from textual.app import App, InvalidThemeError
from textual.binding import Binding

from jiratui.api_controller.controller import APIController, APIControllerResponse
from jiratui.config import CONFIGURATION, ApplicationConfiguration
from jiratui.constants import LOGGER_NAME
from jiratui.keys import (
    VIM_ACTION_PREFIX,
    VimCommand,
    build_keymap,
    parse_vim_command,
    unknown_binding_ids,
    vim_keybindings_enabled,
)
from jiratui.models import JiraServerInfo
from jiratui.utils.logging import JiraTUILogger
from jiratui.utils.session import ApplicationSession
from jiratui.widgets.screen import MainScreen
from jiratui.widgets.screens.config import ConfigFileScreen
from jiratui.widgets.screens.quit import QuitScreen
from jiratui.widgets.screens.server import ServerInfoScreen


class JiraApp(App):
    """Implements the application."""

    CSS_PATH = 'css/jt.tcss'
    """The path to the file with the TCSS (Textual CSS) definitions."""

    TITLE = 'JiraTUI'
    BINDINGS = [
        Binding(
            key='f1,ctrl+question_mark,ctrl+shift+slash',
            action='help',
            description='?',
            id='app.help',
        ),
        Binding(
            key='f2',
            action='server_info',
            description='Server',
            tooltip='Show details of the Jira server',
            id='app.server_info',
        ),
        Binding(
            key='f3',
            action='config_info',
            description='Config',
            tooltip='Show the settings in the configuration file',
            id='app.config_info',
        ),
        Binding(
            key='ctrl+q',
            action='quit',
            description='\U000023fb',
            key_display='^q',
            tooltip='Quit',
            show=True,
            id='app.quit',
        ),
        Binding(
            key=':',
            action='vim_command',
            description='Command',
            key_display=':',
            tooltip='Open the command line, e.g. :q',
            show=False,
            id='app.vim_command',
        ),
        # these are the fall-back bindings for `j` and `k`: widgets that hold a list of items, e.g. the search
        # results, handle these keys themselves; anywhere else they simply move the focus
        Binding(
            key='j',
            action='vim_focus_next',
            description='Focus the next widget',
            show=False,
            id='app.vim_focus_next',
        ),
        Binding(
            key='k',
            action='vim_focus_previous',
            description='Focus the previous widget',
            show=False,
            id='app.vim_focus_previous',
        ),
    ]
    DEFAULT_THEME = 'textual-dark'

    def __init__(
        self,
        settings: ApplicationConfiguration,
        project_key: str | None = None,
        user_account_id: str | None = None,
        jql_expression_id: int | None = None,
        work_item_key: str | None = None,
        user_theme: str | None = None,
        focus_item_on_startup: int | None = None,
    ):
        """Initializes the application.

        Args:
            settings: the settings for the application.
            project_key: the initial project key to set the selection in the project's dropdown.
            user_account_id: the initial assignee to set the selection in the assignee's dropdown.
            jql_expression_id: the ID of a JQL expression defined in the config file to use as the default expression
            for searching work items when the user does not select any criteria in the UI.
            work_item_key: a work item key to set the work item widget.
            user_theme: the name of a Textual theme to use as the theme of the app. If this value is provided it will
            override the value set in the config variable `theme`.
            focus_item_on_startup: the position of the work item to focus and open on startup. Requires search_on_startup to be enabled.
        """
        super().__init__()
        self.config = settings
        CONFIGURATION.set(settings)

        # set the session object
        self.__session = ApplicationSession()

        self.api = APIController()  # required so screens can have access to the API

        self.initial_project_key: str | None = None
        selected_project_key = project_key or CONFIGURATION.get().default_project_key_or_id or None
        if selected_project_key and (cleaned_selected_project_key := selected_project_key.strip()):
            self.initial_project_key = cleaned_selected_project_key

        self.initial_work_item_key: str | None = None
        if work_item_key and (cleaned_work_item_key := work_item_key.strip()):
            self.initial_work_item_key = cleaned_work_item_key

        self.initial_user_account_id: str | None = None
        selected_assignee_account_id = (
            user_account_id or CONFIGURATION.get().jira_account_id or None
        )
        if selected_assignee_account_id and (
            cleaned_selected_assignee_account_id := selected_assignee_account_id.strip()
        ):
            self.initial_user_account_id = cleaned_selected_assignee_account_id

        self.initial_jql_expression_id: int | None = (
            int(jql_expression_id) if jql_expression_id is not None else None
        )

        self.focus_item_on_startup: int | None = focus_item_on_startup
        self.server_info: JiraServerInfo | None = None
        self._setup_logging()
        self.logger = JiraTUILogger(
            logging.getLogger(LOGGER_NAME), CONFIGURATION.get().enable_logging
        )
        self._setup_theme(user_theme)

    def _setup_theme(self, user_theme: str | None = None) -> None:
        if input_theme := (user_theme or CONFIGURATION.get().theme):
            try:
                self.theme = input_theme
            except InvalidThemeError:
                self.logger.warning(
                    f'Unknown theme {input_theme}. Using the default theme: {self.DEFAULT_THEME}'
                )
                self.theme = self.DEFAULT_THEME
        else:
            self.theme = self.DEFAULT_THEME

    @property
    def session(self) -> ApplicationSession:
        return self.__session

    def _setup_keybindings(self) -> None:
        """Applies the keymap of the application.

        The keymap contains the Vim-like keybindings, when `enable_vim_keybindings` is enabled, and the keybindings
        that the user defined via the setting `keybindings`.

        Returns:
            None
        """

        if unknown_ids := unknown_binding_ids(self.config):
            self.logger.warning(
                f'Ignoring unknown keybinding IDs in the setting `keybindings`: {", ".join(unknown_ids)}'
            )
        if keymap := build_keymap(self.config):
            self.set_keymap(keymap)

    async def on_mount(self) -> None:
        self._set_application_title()
        self._setup_keybindings()

        await self.push_screen(
            MainScreen(
                self.api,
                self.initial_project_key,
                self.initial_user_account_id,
                self.initial_jql_expression_id,
                self.initial_work_item_key,
                self.focus_item_on_startup,
            )
        )

    def on_unmount(self) -> None:
        self.__session.clear()

    async def action_help(self) -> None:
        from jiratui.widgets.screens.help import HelpScreen

        # get the widget that is currently focused
        focused = self.focused

        def restore_focus(response) -> None:
            if focused:
                # re-focus the widget that was focused before the action
                self.screen.set_focus(focused)

        self.set_focus(None)
        anchor = None
        if hasattr(focused, 'help_anchor'):
            anchor = focused.help_anchor
        await self.push_screen(HelpScreen(anchor), restore_focus)

    async def action_server_info(self) -> None:
        """Handles the event to show the information of the Jira server instance."""
        await self.push_screen(ServerInfoScreen(server_info=self.server_info))

    async def action_config_info(self) -> None:
        """Handles the event to show the config file"""
        await self.push_screen(ConfigFileScreen())

    async def action_quit(self) -> None:
        """Handles the event to quit the application."""
        if CONFIGURATION.get().confirm_before_quit:
            await self.push_screen(QuitScreen())
        else:
            await self._exit_application()

    async def _exit_application(self) -> None:
        """Closes the HTTP clients and exits the application without asking for confirmation."""

        await self.api.api.client.close_async_client()
        await self.api.api.async_http_client.close_async_client()
        self.app.exit()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Check if an action may run."""

        if action.startswith(VIM_ACTION_PREFIX) and not vim_keybindings_enabled(self.config):
            return False
        return super().check_action(action, parameters)

    def action_vim_focus_next(self) -> None:
        """Focuses the next widget. This is the fall-back behaviour of `j`."""

        self.screen.focus_next()

    def action_vim_focus_previous(self) -> None:
        """Focuses the previous widget. This is the fall-back behaviour of `k`."""

        self.screen.focus_previous()

    async def action_vim_command(self) -> None:
        """Opens the Vim-like command line."""

        from jiratui.widgets.screens.vim import VimCommandScreen

        await self.push_screen(VimCommandScreen(), self._handle_vim_command)

    def _handle_vim_command(self, value: str | None = None) -> None:
        """Runs the command that the user entered in the Vim-like command line.

        Args:
            value: the command entered by the user, e.g. `q!`. This is `None` when the user closes the command line
            without entering a command.

        Returns:
            None
        """

        if not value or not value.strip():
            return

        command, cleaned_value = parse_vim_command(value)
        if command == VimCommand.QUIT:
            self.run_worker(self.action_quit())
        elif command == VimCommand.FORCE_QUIT:
            self.run_worker(self._exit_application())
        elif command == VimCommand.HELP:
            self.run_worker(self.action_help())
        else:
            self.notify(
                f'E492: Not an editor command: {cleaned_value}',
                title='Command',
                severity='error',
            )

    async def _set_application_title_using_server_info(self) -> None:
        response_server_info: APIControllerResponse = await self.api.server_info()
        if (
            response_server_info.success
            and response_server_info.result
            and response_server_info.result.base_url_or_server_title
        ):
            self.server_info = response_server_info.result
            self.title = f'{self.title} - {self.server_info.base_url_or_server_title}'  # type:ignore[has-type]

    def _set_application_title(self) -> None:
        config = CONFIGURATION.get()

        # Check if tui_custom_title is defined
        if config.tui_custom_title is not None:
            # If tui_custom_title is an empty string, don't render title at all
            if config.tui_custom_title == '':
                self.title = ''
                return
            # If tui_custom_title has a value, use it
            elif config.tui_custom_title.strip():
                self.title = config.tui_custom_title.strip()
        # Fall back to tui_title if tui_custom_title is not set
        elif (custom_title := config.tui_title) and custom_title.strip():
            self.title = custom_title.strip()

        # Append Jira server title if configured
        if config.tui_title_include_jira_server_title and self.title:
            if self.server_info:
                self.title = f'{self.title} - {self.server_info.base_url_or_server_title}'
            else:
                self.run_worker(self._set_application_title_using_server_info())

    def _setup_logging(self) -> None:
        log_level = CONFIGURATION.get().log_level or logging.WARNING
        base_logger = logging.getLogger(LOGGER_NAME)
        base_logger.setLevel(log_level)

        log_file = None
        if jira_tui_log_file := os.getenv('JIRA_TUI_LOG_FILE'):
            log_file = Path(jira_tui_log_file).resolve()
        elif config_log_file := CONFIGURATION.get().log_file:
            log_file = Path(str(config_log_file)).resolve()

        handlers = []

        if log_file:
            try:
                fh = logging.FileHandler(log_file)
            except Exception:
                pass
            else:
                fh.setLevel(log_level)
                fh.setFormatter(
                    JsonFormatter(
                        '%(asctime)s %(levelname)s %(message)s %(lineno)s %(module)s %(pathname)s '
                    )
                )
                handlers.append(fh)

        logging.basicConfig(level=log_level, handlers=handlers)


if __name__ == '__main__':
    try:
        JiraApp(ApplicationConfiguration()).run()  # type: ignore[call-arg] # noqa
    except Exception as e:
        sys.exit(str(e))

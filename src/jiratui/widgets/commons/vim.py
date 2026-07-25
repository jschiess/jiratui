"""Widgets that provide Vim-like navigation.

The widgets in this module define keybindings that are only active when the setting `enable_vim_keybindings` is
enabled. The bindings use actions prefixed with `vim_` and the widgets disable those actions, via `check_action()`,
when the Vim-like keybindings are disabled. This way the keys they use, e.g. `j` and `k`, keep their standard
behaviour for users that do not use the Vim-like keybindings.
"""

from textual.binding import Binding
from textual.widgets import Collapsible, DataTable

from jiratui.keys import VIM_ACTION_PREFIX, vim_keybindings_enabled


class VimNavigationMixin:
    """Disables the actions that are only available when the Vim-like keybindings are enabled."""

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Check if an action may run."""

        if action.startswith(VIM_ACTION_PREFIX) and not vim_keybindings_enabled():
            return False
        return super().check_action(action, parameters)  # type:ignore[misc]


class VimDataTable(VimNavigationMixin, DataTable):
    """A [DataTable](#textual.widgets.DataTable) that supports Vim-like navigation.

    | Key | Action                            |
    |-----|-----------------------------------|
    | `j` | Moves the cursor one row down     |
    | `k` | Moves the cursor one row up       |
    | `g` | Moves the cursor to the first row |
    | `G` | Moves the cursor to the last row  |
    """

    BINDINGS = [
        Binding(
            key='j',
            action='vim_cursor_down',
            description='Down',
            show=False,
            id='vim.cursor_down',
        ),
        Binding(
            key='k',
            action='vim_cursor_up',
            description='Up',
            show=False,
            id='vim.cursor_up',
        ),
        Binding(
            key='g',
            action='vim_cursor_top',
            description='Top',
            show=False,
            id='vim.cursor_top',
        ),
        Binding(
            key='G',
            action='vim_cursor_bottom',
            description='Bottom',
            show=False,
            id='vim.cursor_bottom',
        ),
    ]

    def action_vim_cursor_down(self) -> None:
        self.action_cursor_down()

    def action_vim_cursor_up(self) -> None:
        self.action_cursor_up()

    def action_vim_cursor_top(self) -> None:
        self.action_scroll_top()

    def action_vim_cursor_bottom(self) -> None:
        self.action_scroll_bottom()


class VimCollapsible(VimNavigationMixin, Collapsible):
    """A [Collapsible](#textual.widgets.Collapsible) that supports Vim-like navigation.

    Lists of items such as the comments, the web links or the subtasks of a work item are built with collapsible
    widgets. Users move between the items with `tab`; when the Vim-like keybindings are enabled they can also use `j`
    and `k`.

    | Key | Action                       |
    |-----|------------------------------|
    | `j` | Focuses the next item        |
    | `k` | Focuses the previous item    |
    """

    BINDINGS = [
        Binding(
            key='j',
            action='vim_focus_next',
            description='Next',
            show=False,
            id='vim.focus_next',
        ),
        Binding(
            key='k',
            action='vim_focus_previous',
            description='Previous',
            show=False,
            id='vim.focus_previous',
        ),
    ]

    def action_vim_focus_next(self) -> None:
        self.screen.focus_next()

    def action_vim_focus_previous(self) -> None:
        self.screen.focus_previous()

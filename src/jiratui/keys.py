"""Support for customizable and Vim-like keybindings.

Every keybinding defined by JiraTUI has a unique ID, e.g. `main.find_by_text`. These IDs can be used in the
configuration file to re-map the key (or keys) that trigger the binding:

```yaml
keybindings:
  main.find_by_text: 'ctrl+f'
  app.quit: 'ctrl+q,q'
```

In addition, the setting `enable_vim_keybindings` activates a set of Vim-like keybindings. This is implemented as a
"preset", i.e. a keymap that is applied before the user-defined `keybindings`. This means that users can enable the
Vim-like keybindings and still re-map any individual binding to a key of their choice.

Bindings that only make sense when the Vim-like keybindings are enabled, e.g. `j`/`k` to move the cursor of a table,
use actions whose name starts with `vim_`. Widgets that define such bindings check whether the actions are enabled
via `check_action()`; when `enable_vim_keybindings` is `False` these actions are disabled and the keys are handled as
usual by the rest of the application.
"""

from enum import Enum

from jiratui.config import CONFIGURATION, ApplicationConfiguration

VIM_ACTION_PREFIX = 'vim_'
"""The prefix of the actions that are only available when the Vim-like keybindings are enabled."""

VIM_KEYMAP: dict[str, str] = {
    # quit with `q`, like most Vim-like applications; ctrl+q keeps working
    'app.quit': 'ctrl+q,q',
    # `j` and `k` are used for moving up/down so the widgets they used to focus are moved to `J` and `K`
    'main.focus_jql': 'J',
    'main.focus_work_item_key': 'K',
    # `/` filters the items of the current page when the search results are focused
    'search_results.filter': '.,/',
}
"""The keymap applied when `enable_vim_keybindings` is enabled.

It only contains the bindings whose default key clashes with, or is superseded by, a Vim-like key. The rest of the
Vim-like keys are defined by the widgets themselves via actions prefixed with `vim_`.
"""

KNOWN_BINDING_IDS: frozenset[str] = frozenset(
    {
        # application
        'app.help',
        'app.server_info',
        'app.config_info',
        'app.quit',
        'app.vim_command',
        'app.vim_focus_next',
        'app.vim_focus_previous',
        # main screen
        'main.find_by_text',
        'main.search',
        'main.focus_project',
        'main.focus_issue_type',
        'main.focus_status',
        'main.focus_assignee',
        'main.focus_work_item_key',
        'main.focus_created_from',
        'main.focus_created_until',
        'main.focus_order_by',
        'main.focus_active_sprint',
        'main.focus_jql',
        'main.focus_search_results',
        'main.focus_info_tab',
        'main.focus_details_tab',
        'main.focus_comments_tab',
        'main.focus_related_tab',
        'main.focus_attachments_tab',
        'main.focus_links_tab',
        'main.focus_subtasks_tab',
        'main.create_work_item',
        'main.copy_work_item_key',
        'main.copy_work_item_url',
        'main.create_git_branch',
        'main.recent_history',
        'main.vim_focus_left_pane',
        'main.vim_focus_right_pane',
        'main.vim_previous_tab',
        'main.vim_next_tab',
        'main.vim_focus_search_results',
        # search results
        'search_results.filter',
        'search_results.hide_filter',
        'search_results.previous_page',
        'search_results.next_page',
        'search_results.open_in_browser',
        'search_results.delete',
        'search_results.goto',
        # work item details
        'details.save',
        'details.focus_assignee',
        'details.focus_priority',
        'details.focus_status',
        'details.worklog',
        'details.flag',
        # work item info
        'work_item_info.edit',
        'work_item_info.view',
        'work_item_info.copy',
        # comments
        'comments.add',
        'comment.delete',
        # attachments
        'attachments.add',
        'attachment.delete',
        'attachment.open_in_browser',
        # related work items
        'related_items.add',
        'related_item.quick_view',
        'related_item.unlink',
        'related_item.goto',
        # web links
        'remote_links.add',
        'remote_link.delete',
        # subtasks
        'subtasks.create',
        'subtask.quick_view',
        'subtask.goto',
        # worklogs
        'worklog.add',
        'worklog.edit',
        'worklog.delete',
        'worklog.open_in_browser',
        # recent history
        'history.empty',
        'history_item.copy_key',
        'history_item.copy_url',
        'history_item.open_in_browser',
        # go-to screen
        'goto_item.copy_key',
        'goto_item.copy_url',
        'goto_item.open_in_browser',
        # quick view screen
        'quick_view.copy_key',
        'quick_view.copy_url',
        'quick_view.open_in_browser',
        'quick_view.search',
        # editors
        'jql.editor',
        'rich_text.edit',
        'create_work_item.save',
        'create_work_item.edit_description',
        # Vim-like navigation
        'vim.cursor_up',
        'vim.cursor_down',
        'vim.cursor_top',
        'vim.cursor_bottom',
        'vim.focus_next',
        'vim.focus_previous',
    }
)
"""The IDs of all the keybindings that can be re-mapped via the `keybindings` setting."""


class VimCommand(Enum):
    """The commands supported by the Vim-like command line, e.g. `:q`."""

    QUIT = 'quit'
    FORCE_QUIT = 'force_quit'
    HELP = 'help'
    UNKNOWN = 'unknown'


def get_configuration(
    config: ApplicationConfiguration | None = None,
) -> ApplicationConfiguration | None:
    """Returns the configuration of the application; if any is available.

    Args:
        config: an optional configuration. When this is `None` the global configuration is used.

    Returns:
        The configuration of the application or `None` if there is no configuration available.
    """

    if config is not None:
        return config
    try:
        return CONFIGURATION.get()
    except LookupError:
        return None


def vim_keybindings_enabled(config: ApplicationConfiguration | None = None) -> bool:
    """Indicates whether the Vim-like keybindings are enabled.

    Args:
        config: an optional configuration. When this is `None` the global configuration is used.

    Returns:
        `True` if the setting `enable_vim_keybindings` is enabled; `False` otherwise.
    """

    config = get_configuration(config)
    return getattr(config, 'enable_vim_keybindings', False) is True


def user_keybindings(config: ApplicationConfiguration | None = None) -> dict[str, str]:
    """Returns the keybindings defined by the user in the setting `keybindings`.

    Args:
        config: an optional configuration. When this is `None` the global configuration is used.

    Returns:
        A mapping from binding IDs into the keys that trigger them.
    """

    config = get_configuration(config)
    keybindings = getattr(config, 'keybindings', None)
    if not isinstance(keybindings, dict):
        return {}
    return {
        str(binding_id): str(keys).strip()
        for binding_id, keys in keybindings.items()
        if keys and str(keys).strip()
    }


def build_keymap(config: ApplicationConfiguration | None = None) -> dict[str, str]:
    """Builds the keymap of the application.

    The keymap maps the ID of a binding into the key (or comma-separated list of keys) that triggers it. The keymap
    is built by applying the Vim-like preset, if `enable_vim_keybindings` is enabled, and then the keybindings that
    the user defined in the setting `keybindings`. This means that the user-defined keybindings take precedence over
    the ones in the Vim-like preset.

    Args:
        config: an optional configuration. When this is `None` the global configuration is used.

    Returns:
        A mapping from binding IDs into keys. The mapping is empty when there is nothing to re-map.
    """

    config = get_configuration(config)
    keymap: dict[str, str] = {}
    if vim_keybindings_enabled(config):
        keymap.update(VIM_KEYMAP)
    keymap.update(user_keybindings(config))
    return keymap


def unknown_binding_ids(config: ApplicationConfiguration | None = None) -> list[str]:
    """Returns the IDs in the setting `keybindings` that do not correspond to a known keybinding.

    Args:
        config: an optional configuration. When this is `None` the global configuration is used.

    Returns:
        A sorted list of unknown binding IDs.
    """

    return sorted(set(user_keybindings(config)) - KNOWN_BINDING_IDS)


def effective_key(
    binding_id: str, default: str, config: ApplicationConfiguration | None = None
) -> str:
    """Returns the key that triggers a binding taking into account the keymap of the application.

    This is used for displaying hints, e.g. the `(j)` legend of the JQL input widget, that must reflect the keys that
    the user needs to press.

    Args:
        binding_id: the ID of the binding.
        default: the key to return when the binding is not re-mapped.
        config: an optional configuration. When this is `None` the global configuration is used.

    Returns:
        The first key that triggers the binding.
    """

    keys = build_keymap(config).get(binding_id, default)
    return keys.split(',')[0].strip() or default


def parse_vim_command(value: str | None) -> tuple[VimCommand, str]:
    """Parses a command entered in the Vim-like command line.

    Args:
        value: the text entered by the user, e.g. `:q!`. A leading `:` is optional.

    Returns:
        A tuple with the command and the (cleaned) text provided by the user.
    """

    command = (value or '').strip()
    if command.startswith(':'):
        command = command[1:].strip()
    if command in {'q', 'qa', 'quit', 'quitall', 'x', 'wq'}:
        return VimCommand.QUIT, command
    if command in {'q!', 'qa!', 'quit!', 'quitall!'}:
        return VimCommand.FORCE_QUIT, command
    if command in {'h', 'help'}:
        return VimCommand.HELP, command
    return VimCommand.UNKNOWN, command

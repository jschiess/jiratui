from textual import on
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Input


class VimCommandScreen(ModalScreen[str]):
    """A modal screen that emulates the command line of Vim.

    The screen is opened by pressing `:` when the setting `enable_vim_keybindings` is enabled. It dismisses itself
    with the command entered by the user; the application is responsible for running the command.

    **See Also**:
    - [jiratui.keys.parse_vim_command](#jiratui.keys.parse_vim_command)
    """

    BINDINGS = [('escape', 'app.pop_screen', 'Close')]

    def compose(self) -> ComposeResult:
        command_field = Input(placeholder='q, q!, help', id='vim-command-input')
        command_field.border_title = ':'
        yield command_field

    @on(Input.Submitted)
    def run_command(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

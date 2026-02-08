# Re-export key components for cleaner imports in app.py
from .file_manager import (
    _handle_generate_actions,
    _handle_output_file_name_change,
    _handle_use_prefix_toggle,
    _handle_bulk_action_toggle,
    _open_profile_folder,
    _handle_view_html_logs,
)
from .dialogs.files.file_dialog import (
     _handle_path_selected_generic,
     _register_file_dialogs,
     _browse_folder_native,
)
from .layout import (
    setup_fonts,
    build_profile_summary,
    build_file_actions,
)

from .menu import build_menu_bar, _open_user_guide
from .dialogs.app.updates_dialog import check_for_updates_ui
from .dialogs.app.about_dialog import _show_about_dialog
from .shared import log_message
from .panels.device.device_panel import build_device_controls
from .palette_manager import _show_create_palette_dialog, _show_load_palette_dialog, _show_theme_editor
from .panels.logs.logs_panel import log_message as _log_message, _handle_log_filter

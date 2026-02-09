# Re-export key components for cleaner imports in app.py
from .dialogs.app.about_dialog import _show_about_dialog
from .dialogs.app.updates_dialog import check_for_updates_ui
from .dialogs.files.file_dialog import (
    _browse_folder_native,
    _handle_path_selected_generic,
    _register_file_dialogs,
)
from .file_manager import (
    _get_unique_output_path,
    _handle_bulk_action_toggle,
    _handle_generate_actions,
    _handle_output_file_name_change,
    _handle_use_prefix_toggle,
    _handle_view_html_logs,
    _open_profile_folder,
)
from .layout import (
    build_file_actions,
    build_profile_summary,
    setup_fonts,
)
from .menu import _open_user_guide, build_menu_bar
from .palette_manager import (
    _show_create_palette_dialog,
    _show_load_palette_dialog,
    _show_theme_editor,
)
from .panels.device.device_panel import build_device_controls
from .panels.logs.logs_panel import (
    _clear_logs,
    _handle_export_logs,
    _handle_log_filter,
    _render_log_entries,
)
from .panels.logs.logs_panel import log_message as _log_message
from .shared import log_message

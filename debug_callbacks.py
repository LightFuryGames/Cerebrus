
import dearpygui.dearpygui as dpg
from cerebrus.ui.state import UIState
from cerebrus.ui.components.shared import log_message
from cerebrus.ui.components.menu import _handle_theme_change
from cerebrus.ui.themes import get_theme_manager
from cerebrus.ui.components.ui_config import UIConfig

def test_callbacks():
    print("Initializing components...")
    dpg.create_context()
    
    # Init config
    try:
        config = UIConfig.get_instance()
        print(f"UIConfig loaded. Keys: {config._config.keys()}")
    except Exception as e:
        print(f"UIConfig Failed: {e}")

    # Init ThemeManager
    try:
        tm = get_theme_manager()
        print(f"ThemeManager loaded. Palettes: {list(tm.themes.keys())}")
    except Exception as e:
        print(f"ThemeManager Failed: {e}")

    state = UIState()
    
    # Test log_message
    try:
        log_message(state, "INFO", "Test log message")
        print("log_message succeeded")
    except Exception as e:
        print(f"log_message Failed: {e}")
        import traceback
        traceback.print_exc()

    # Test theme change
    try:
        # Mock DPG items if needed
        if not dpg.does_item_exist("menu_mode_system"):
             with dpg.window(label="Mock"):
                 dpg.add_menu_item(tag="menu_mode_system")
        
        _handle_theme_change(state, mode="Light")
        print("_handle_theme_change succeeded")
    except Exception as e:
        print(f"_handle_theme_change Failed: {e}")
        import traceback
        traceback.print_exc()

    dpg.destroy_context()

if __name__ == "__main__":
    test_callbacks()

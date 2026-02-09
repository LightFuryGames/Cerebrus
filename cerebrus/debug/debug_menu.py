import dearpygui.dearpygui as dpg

from cerebrus.ui.components.menu import build_menu_bar
from cerebrus.ui.state import UIState

dpg.create_context()
dpg.create_viewport()
dpg.setup_dearpygui()

state = UIState()

with dpg.window(label="Debug Menu"):
    try:
        build_menu_bar(state)
        print("Menu bar built successfully")
    except Exception as e:
        print(f"Error building menu bar: {e}")
        import traceback

        traceback.print_exc()

dpg.show_viewport()
# dpg.start_dearpygui() # Don't block, just run to test build
dpg.destroy_context()

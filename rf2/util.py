from pywinauto import Desktop, WindowSpecification
from os.path import join
from time import sleep


def get_main_window(server_config: dict):
    """
    Get the server main window

    Args:
        server_config: The global configuration for this instance

    Returns:
        A WindowSpecification containing the dialog window.
    """
    root_path = server_config["server"]["root_path"]
    server_root_path = join(root_path, "server") + "\\"
    dialog = Desktop(backend="win32").window(title=server_root_path)
    return dialog


def set_slider_value(slider: WindowSpecification, value: int):
    slider.set_position(value)


def set_updown_value(updown: WindowSpecification, value: int):
    updown.set_text(value)


def select_from_list(listbox: WindowSpecification, listElements: dict):
    list_box_items = listbox.item_texts()
    for element in listElements:
        index = list_box_items.index(element)
        if index >= 0:
            listbox.select(index)


def set_window_elements_value(elements: dict, container: WindowSpecification):
    for key, value in elements.items():
        if "edit" in key.lower():
            container[key].set_text(value)
        if "combo" in key.lower():
            select_from_list(container[key], value)
        if "updown" in key.lower():
            container[key].SetValue(value)
        if "Trackbar" in key:
            container[key].set_position(value)
        if "check" in key.lower() or "radio" in key.lower():
            if value:
                container[key].check()
            else:
                container[key].uncheck(value)
        sleep(0.5)

## Objective

The primary goal of this task was to address Issue #1271, which required decluttering the main user interface. 

## Requirements

REQ-01: Consolidated Search Settings Dropdown The UI must reduce clutter by moving 'Show hidden entries', 'Sorting Mode', and 'Sorting Direction' settings into a single 'Search Settings' dropdown menu.

## Technical Approach

The modifications were strictly contained within the UI view layer using the PySide6 framework. To encapsulate complex widgets (like QComboBox) inside a standard QMenu, we utilized the QWidgetAction wrapper. 

## Detailed Code Modifications

**File 1:** 

src/tagstudio/qt/views/main_window.py


This file received the bulk of the refactoring, specifically within the setup_extra_input_bar
 method.

- **Import Updates:**
    Imported QWidgetAction from PySide6.QtWidgets to allow appending complex interactive widgets into a standard QMenu.

- **Creation of the Dropdown Menu:**
    Introduced a new QPushButton named search_settings_button as the interaction point.
    Attached a native QMenu (search_settings_menu) to this button using the .setMenu() method.

- **Refactoring "Show Hidden Entries":**
    
    - **Native Action Mapping:** 
        Instead of rendering a custom layout for the checkbox inside the menu (which can cause width rendering bugs in Qt), a native checkable QAction (show_hidden_entries_action) was added to the standard menu.
    - **Ghost Component Pattern:** The original self.show_hidden_entries_checkbox was intentionally preserved but set to hidden (.hide()).
    - **Signal Synchronization:** Dual-binding was implemented using .toggled.connect() between the new menu action and the hidden checkbox. This ensures that when the user clicks the menu item, the invisible checkbox's state changes identically, allowing external components to blindly query the checkbox as they historically did.

- **Refactoring "Sorting Mode" and "Sorting Direction":**
    Both self.sorting_mode_combobox and self.sorting_direction_combobox were retained intact with their original Enum iterations and configurations.
    Rather than appending them to the root extra_input_layout, they were encapsulated into QWidgetAction instances (sorting_mode_action and sorting_direction_action) and injected directly into the newly created search_settings_menu.

- **Layout Reordering (UX Polish):**
    The appending sequence in extra_input_layout was modified. The thumb_size_combobox (Medium Thumbnail config) was moved to the left of the QSpacerItem, while the new search_settings_button was pushed to the far right. This layout swap ensures better visual alignment and separation of display constraints versus search constraints.

**File 2:**

src/tagstudio/resources/translations/en.json

To adhere to the application's i18n (Internationalization) standards, hardcoded text was avoided.

Added the specific KV-pair: "home.search_settings": "Search Settings".
This key is referenced dynamically by the new dropdown button during its instantiation (Translations["home.search_settings"]).

# This file is part of MyPaint.
# Copyright (C) 2014 by Andrew Chadwick <a.t.chadwick@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.


"""Global AccelMap editor, for backwards compatibility"""

## Imports

import logging
logger = logging.getLogger(__name__)

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango
from gettext import gettext as _

from lib.helpers import escape


## Class defs

class AccelMapEditor (Gtk.Grid):
    """Ugly properties list for editing the global accel map

    MyPaint normally doesn't use properties lists for reasons of
    simplicity. However since Gtk 3.12 these are no longer editable via
    the menus themselves, so we must create an alternative for 3.12
    users who want to rebind keys.
    """
    # This interface is likely to evolve into an accelerator editor for
    # GtkApplication's GAction-based way of doing things when we drop
    # support for 3.10.

    ## Consts

    __gtype_name__ = 'AccelMapEditor'

    _COLUMN_TYPES = (str, str, str)
    _PATH_COLUMN = 0
    _ACCEL_LABEL_COLUMN = 1
    _ACTION_LABEL_COLUMN = 2

    _USE_NORMAL_DIALOG_KEYS = True
    _SHOW_ACCEL_PATH = True

    ## Setup

    def __init__(self):
        super(AccelMapEditor, self).__init__()
        self.ui_manager = None
        self.connect("show", self._show_cb)

        store = Gtk.ListStore(*self._COLUMN_TYPES)
        self._store = store
        self._action_labels = {}

        scrolls = Gtk.ScrolledWindow()
        scrolls.set_shadow_type(Gtk.ShadowType.IN)
        view = Gtk.TreeView()
        view.set_model(store)
        view.set_size_request(480, 320)
        view.set_hexpand(True)
        view.set_vexpand(True)
        scrolls.add(view)
        self.attach(scrolls, 0, 0, 1, 1)
        view.set_headers_clickable(True)
        view.set_enable_search(True)
        view.set_search_column(self._ACTION_LABEL_COLUMN)
        self._view = view

        cell = Gtk.CellRendererText()
        cell.set_property("ellipsize", Pango.EllipsizeMode.END)
        cell.set_property("editable", False)
        col = Gtk.TreeViewColumn(_("Action"), cell)
        col.add_attribute(cell, "text", self._ACTION_LABEL_COLUMN)
        col.set_expand(True)
        col.set_resizable(True)
        col.set_min_width(200)
        col.set_sort_column_id(self._ACTION_LABEL_COLUMN)
        view.append_column(col)

        cell = Gtk.CellRendererText()
        cell.set_property("ellipsize", Pango.EllipsizeMode.END)
        cell.set_property("editable", True)
        cell.connect("edited", self._accel_edited_cb)
        cell.connect("editing-started", self._accel_editing_started_cb)
        col = Gtk.TreeViewColumn(_("Key combination"), cell)
        col.add_attribute(cell, "text", self._ACCEL_LABEL_COLUMN)
        col.set_expand(True)
        col.set_resizable(True)
        col.set_min_width(150)
        col.set_sort_column_id(self._ACCEL_LABEL_COLUMN)
        view.append_column(col)

    def _show_cb(self, widget):
        self._init_from_accel_map()

    def _init_from_accel_map(self):
        """Initializes from the app UIManager and the global AccelMap"""
        if self.ui_manager is None:
            import application
            app = application.get_app()
            self.ui_manager = app.ui_manager
        assert self.ui_manager is not None
        self._action_labels.clear()
        self._store.clear()
        accel_labels = {}
        for path, key, mods, changed in self._get_accel_map_entries():
            accel_labels[path] = Gtk.accelerator_get_label(key, mods)
        for group in self.ui_manager.get_action_groups():
            group_name = group.get_name()
            for action in group.list_actions():
                action_name = action.get_name()
                path = "<Actions>/%s/%s" % (group_name, action_name)
                action_label = action.get_label()
                if not action_label:
                    continue
                self._action_labels[path] = action_label
                accel_label = accel_labels.get(path)
                row = [None for t in self._COLUMN_TYPES]
                row[self._PATH_COLUMN] = path
                row[self._ACTION_LABEL_COLUMN] = action_label
                row[self._ACCEL_LABEL_COLUMN] = accel_label
                self._store.append(row)

    def _update_from_accel_map(self):
        """Updates the list from the global AccelMap, logging changes"""
        accel_labels = {}
        for path, key, mods, changed in self._get_accel_map_entries():
            accel_labels[path] = Gtk.accelerator_get_label(key, mods)
        for row in self._store:
            path = row[self._PATH_COLUMN]
            new_label = accel_labels.get(path)
            old_label = row[self._ACCEL_LABEL_COLUMN]
            if new_label != old_label:
                logger.debug("update: %r now uses %r", path, new_label)
                row[self._ACCEL_LABEL_COLUMN] = new_label

    @classmethod
    def _get_accel_map_entries(cls):
        """Gets all entries in the global GtkAccelMap as a list"""
        accel_map = Gtk.AccelMap.get()
        entries = []
        entries_populator = lambda *e: entries.append(e)
        accel_map.foreach_unfiltered(0, entries_populator)
        entries = [(accel_path, key, mods, changed)
                   for data, accel_path, key, mods, changed in entries]
        return entries

    ## Editing

    def _accel_edited_cb(self, cell, path, newname):
        """Arrange for list updates to happen after editing is done"""
        self._update_from_accel_map()

    def _accel_editing_started_cb(self, cell, editable, treepath):
        """Begin editing by showing a key capture dialog"""
        store = self._store
        it = store.get_iter(treepath)
        action_label = store.get_value(it, self._ACTION_LABEL_COLUMN)
        accel_label = store.get_value(it, self._ACCEL_LABEL_COLUMN)
        accel_path = store.get_value(it, self._PATH_COLUMN)

        editable.set_sensitive(False)
        dialog = Gtk.Dialog()
        dialog.set_modal(True)
        dialog.set_title(_("Edit Key for '%s'") % action_label)
        dialog.set_transient_for(self.get_toplevel())
        dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        dialog.add_buttons(
            Gtk.STOCK_DELETE, Gtk.ResponseType.REJECT,
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.connect(
            "response",
            self._edit_dialog_response_cb,
            editable,
            accel_path
        )

        evbox = Gtk.EventBox()
        evbox.set_border_width(12)
        dialog.connect(
            "key-press-event",
            self._edit_dialog_key_press_cb,
            editable
        )

        grid = Gtk.Grid()
        grid.set_row_spacing(12)
        grid.set_column_spacing(12)

        row = 0
        label = Gtk.Label()
        label.set_alignment(0, 0.5)
        label.set_text(_("Action:"))
        grid.attach(label, 0, row, 1, 1)
        label = Gtk.Label()
        label.set_alignment(0, 0.5)
        label.set_text(str(action_label))
        label.set_tooltip_text(str(accel_path))
        label.set_hexpand(True)
        grid.attach(label, 1, row, 1, 1)

        if self._SHOW_ACCEL_PATH:
            row += 1
            label = Gtk.Label()
            label.set_alignment(0, 0.5)
            label.set_text(_("Path:"))
            grid.attach(label, 0, row, 1, 1)
            label = Gtk.Label()
            label.set_alignment(0, 0.5)
            label.set_text(str(accel_path))
            label.set_hexpand(True)
            grid.attach(label, 1, row, 1, 1)

        row += 1
        label = Gtk.Label()
        label.set_alignment(0, 0.5)
        label.set_text(_("Key:"))
        grid.attach(label, 0, row, 1, 1)
        label = Gtk.Label()
        label.set_alignment(0, 0.5)
        label.set_text(str(accel_label))
        dialog.accel_label_widget = label
        label.set_hexpand(True)
        grid.attach(label, 1, row, 1, 1)

        row += 1
        label = Gtk.Label()
        label.set_hexpand(True)
        label.set_vexpand(True)
        label.set_margin_top(12)
        label.set_margin_bottom(12)
        label.set_alignment(0, 0)
        label.set_line_wrap(True)
        label.set_size_request(200, 75)
        dialog.hint_widget = label
        self._edit_dialog_set_standard_hint(dialog)
        grid.attach(label, 0, row, 2, 1)

        evbox.add(grid)
        dialog.get_content_area().pack_start(evbox, True, True, 0)
        evbox.show_all()

        dialog.initial_accel_label = accel_label
        dialog.accel_path = accel_path
        dialog.result_keyval = None
        dialog.result_mods = None
        dialog.show()

    def _edit_dialog_set_hint(self, dialog, markup):
        """Sets the hint message label in the capture dialog"""
        dialog.hint_widget.set_markup(markup)

    def _edit_dialog_set_standard_hint(self, dialog):
        """Set the boring how-to message in capture dialog"""
        markup = _("Press keys to update this assignment")
        self._edit_dialog_set_hint(dialog, markup)

    def _edit_dialog_key_press_cb(self, dialog, event, editable):
        if event.type != Gdk.EventType.KEY_PRESS:
            return False
        if event.is_modifier:
            return False
        if self._USE_NORMAL_DIALOG_KEYS:
            if event.keyval == Gdk.KEY_Return:
                dialog.response(Gtk.ResponseType.OK)
                return True
            elif event.keyval == Gdk.KEY_Escape:
                dialog.response(Gtk.ResponseType.CANCEL)
                return True
            elif event.keyval == Gdk.KEY_BackSpace:
                dialog.response(Gtk.ResponseType.REJECT)
                return True

        # Stolen from GTK 2.24's gtk/gtkmenu.c (gtk_menu_key_press())
        # Figure out what modifiers went into determining the key symbol
        keymap = Gdk.Keymap.get_default()
        bound, keyval, effective_group, level, consumed_modifiers = (
            keymap.translate_keyboard_state(
                event.hardware_keycode,
                event.state,
                event.group,
            ))
        keyval = Gdk.keyval_to_lower(keyval)
        mods = Gdk.ModifierType(
            event.state
            & Gtk.accelerator_get_default_mod_mask()
            & ~consumed_modifiers)

        # If lowercasing affects the keysym, then we need to include
        # SHIFT in the modifiers. We re-upper case when we match against
        # the keyval, but display and save in caseless form.
        if keyval != event.keyval:
            mods |= Gdk.ModifierType.SHIFT_MASK
        accel_name = Gtk.accelerator_name(keyval, mods)
        accel_label = Gtk.accelerator_get_label(keyval, mods)
        # So we get (<Shift>j, Shift+J) but just (plus, +). As I
        # understand it.

        if not Gtk.accelerator_valid(keyval, mods):
            return True

        clash_accel_path = None
        clash_action_label = None
        for path, kv, m, changed in self._get_accel_map_entries():
            if (kv, m) == (keyval, mods):
                clash_accel_path = path
                clash_action_label = self._action_labels.get(
                    clash_accel_path,
                    _("Unknown Action"),
                )
                break
        if clash_accel_path == dialog.accel_path:  # no change
            self._edit_dialog_set_standard_hint(dialog)
            label = str(accel_label)
            dialog.accel_label_widget.set_text(label)
        elif clash_accel_path:
            markup_tmpl = _(
                "<b>{accel} is already in use for '{action}'. "
                "The existing assignment will be replaced.</b>"
            )
            markup = markup_tmpl.format(
                accel=escape(accel_label),
                action=escape(clash_action_label),
            )
            self._edit_dialog_set_hint(dialog, markup)
            label = "%s (replace)" % (accel_label,)
            dialog.accel_label_widget.set_text(str(label))
        else:
            self._edit_dialog_set_standard_hint(dialog)
            label = "%s (changed)" % (accel_label,)
            dialog.accel_label_widget.set_text(label)
        dialog.result_mods = mods
        dialog.result_keyval = keyval
        return True

    def _edit_dialog_response_cb(self, dialog, response_id, editable, path):
        mods = dialog.result_mods
        keyval = dialog.result_keyval
        if response_id == Gtk.ResponseType.REJECT:
            entry_exists, junk = Gtk.AccelMap.lookup_entry(path)
            if entry_exists:
                logger.info("Delete entry %r", path)
                if not Gtk.AccelMap.change_entry(path, 0, 0, True):
                    logger.warning("Failed to delete entry for %r", path)
            editable.editing_done()
        elif response_id == Gtk.ResponseType.OK:
            if keyval is not None:
                self._set_accelmap_entry(path, keyval, mods)
            editable.editing_done()
        editable.remove_widget()
        dialog.destroy()

    @classmethod
    def _delete_clashing_accelmap_entries(cls, keyval, mods, path_to_keep):
        accel_name = Gtk.accelerator_name(keyval, mods)
        for path, k, m, changed in cls._get_accel_map_entries():
            if path == path_to_keep:
                continue
            if (k, m) != (keyval, mods):
                continue
            if not Gtk.AccelMap.change_entry(path, 0, 0, True):
                logger.warning("Failed to delete clashing use of %r (%r)",
                               accel_name, path)
            else:
                logger.debug("Deleted clashing use of %r (was %r)",
                             accel_name, path)

    @classmethod
    def _set_accelmap_entry(cls, path, keyval, mods):
        cls._delete_clashing_accelmap_entries(keyval, mods, path)
        accel_label = Gtk.accelerator_get_label(keyval, mods)
        accel_name = Gtk.accelerator_name(keyval, mods)
        entry_exists, junk = Gtk.AccelMap.lookup_entry(path)
        if entry_exists:
            logger.info("Changing entry %r: %r", accel_name, path)
            if Gtk.AccelMap.change_entry(path, keyval, mods, True):
                logger.debug("Updated %r successfully", path)
            else:
                logger.error("Failed to update %r", path)
        else:
            logger.info("Adding new entry %r: %r", accel_name, path)
            Gtk.AccelMap.add_entry(path, keyval, mods)
        entry_exists, junk = Gtk.AccelMap.lookup_entry(path)
        assert entry_exists


## Testing

def _test():
    win = Gtk.Window()
    win.set_title("accelmap.py")
    win.connect("destroy", Gtk.main_quit)
    builder = Gtk.Builder()
    import gui.factoryaction
    builder.add_from_file("gui/resources.xml")
    uimgr = builder.get_object("app_ui_manager")
    editor = AccelMapEditor()
    editor.ui_manager = uimgr
    win.add(editor)
    win.set_default_size(400, 300)
    win.show_all()
    Gtk.main()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    import sys
    orig_excepthook = sys.excepthook
    def _excepthook(*args):
        orig_excepthook(*args)
        while Gtk.main_level():
            Gtk.main_quit()
        sys.exit()
    sys.excepthook = _excepthook
    _test()

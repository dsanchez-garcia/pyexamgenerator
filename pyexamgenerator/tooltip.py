# pyexamgenerator: A tool for generating exams from PDF files using AI.
# Copyright (C) 2024 Daniel Sánchez-García

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import tkinter as tk


class ToolTip(object):
    """
    Creates a tooltip (a pop-up window with text) for a given Tkinter widget.
    This is a standard helper class for providing hover-text functionality.
    """

    # Tooltips currently shown, hidden together when their window is hidden or closed.
    _shown = set()
    # Toplevel windows that already have the handler that hides them (one per window).
    _watched_toplevels = set()

    def __init__(self, widget, text=''):
        """
        Initializes the ToolTip.

        Args:
            widget: The widget this tooltip is associated with.
            text (str): The text to be displayed in the tooltip.
        """
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0

        # Bind events to the widget to show and hide the tooltip.
        # Use add='+' so existing widget bindings are not overwritten.
        self.widget.bind("<Enter>", self.showtip, add="+")
        self.widget.bind("<Leave>", self.hidetip, add="+")
        self.widget.bind("<ButtonPress>", self.hidetip, add="+")
        self.widget.bind("<FocusOut>", self.hidetip, add="+")
        self.widget.bind("<Unmap>", self.hidetip, add="+")
        self.widget.bind("<Destroy>", self.hidetip, add="+")

        # If the toplevel/root is closed or hidden, force-hide lingering tooltips.
        self.root = self.widget.winfo_toplevel()
        self._watch_toplevel(self.root)

    @classmethod
    def _watch_toplevel(cls, toplevel):
        """Hides the shown tooltips when ``toplevel`` is hidden or closed.

        A single handler per window: a binding on a toplevel also runs for the events of every
        widget inside it, so one handler per tooltip ran (tooltips x widgets) times on each
        <Unmap>/<Destroy> (changing tabs, closing the window) and was never removed.
        """
        key = str(toplevel)
        if key in cls._watched_toplevels:
            return
        cls._watched_toplevels.add(key)

        def on_toplevel_event(event):
            if str(event.widget) != key:
                return  # an event of a widget inside the window
            for tooltip in list(cls._shown):
                tooltip.hidetip()
            if str(event.type) == "Destroy":
                cls._watched_toplevels.discard(key)

        toplevel.bind("<Unmap>", on_toplevel_event, add="+")
        toplevel.bind("<Destroy>", on_toplevel_event, add="+")

    def showtip(self, event=None):
        """
        Display text in the tooltip window.
        This method is called when the mouse cursor enters the widget.
        """
        # Ensure we only have one tooltip window alive at any time.
        self.hidetip()

        self.x = self.y = 0
        # Some widgets do not support bbox("insert"); fallback to (0,0).
        try:
            x, y, cx, cy = self.widget.bbox("insert")
        except Exception:
            x, y = 0, 0
        # Calculate the position of the tooltip window on the screen
        x = x + self.widget.winfo_rootx() + 20
        y = y + self.widget.winfo_rooty() + 20

        # Creates a new Toplevel window (a window that floats on top of all others)
        self.tipwindow = tw = tk.Toplevel(self.widget)

        # Removes the window decorations (title bar, borders, etc.) to make it look like a tooltip
        tw.wm_overrideredirect(True)

        # Create a label inside the Toplevel window to display the text
        label = tk.Label(tw, text=self.text, relief='solid', borderwidth=1, font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

        # Position the tooltip window at the calculated coordinates
        tw.wm_geometry("+%d+%d" % (x, y))
        ToolTip._shown.add(self)

        # This commented-out line could be used to add a delay before the tooltip appears.
        # self.id = self.widget.after(1000, self.showtip) # Optional delay

    def hidetip(self, event=None):
        """
        Hides and destroys the tooltip window.
        This method is called when the mouse cursor leaves the widget.
        """
        tw = self.tipwindow
        self.tipwindow = None
        ToolTip._shown.discard(self)
        if tw is not None:
            try:
                tw.destroy()
            except tk.TclError:
                # Safe guard: window may already be destroyed during app shutdown.
                pass

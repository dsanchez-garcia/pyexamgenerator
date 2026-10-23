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

"""Entry point of the desktop application (the ``pyexamgenerator`` command).

The window is :class:`pyexamgenerator.gui.app.ExamApp` and each tab has its own module in
:mod:`pyexamgenerator.gui` (ARC-1); this module keeps the names it always had.
"""

from pyexamgenerator.gui._dialogs import messagebox
from pyexamgenerator.gui.app import ExamApp, main

__all__ = ["ExamApp", "main", "messagebox"]

if __name__ == "__main__":
    main()

"""Affiche le tableau de bord récapitulatif du portefeuille (marche à blanc).

Usage : python dashboard.py
"""
from __future__ import annotations

import sys

for flux in (sys.stdout, sys.stderr):
    try:
        flux.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from app import dashboard  # noqa: E402

if __name__ == "__main__":
    dashboard.afficher()

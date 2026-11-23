"""Segmentasi dan klasifikasi eritrosit: blueprint segmentation_bp.

Path route ditulis lengkap di tiap decorator (tanpa url_prefix), sama persis
dengan v0.1.0.
"""

from flask import Blueprint

segmentation_bp = Blueprint("segmentation", __name__)

from segmentation import export  # noqa: E402,F401  (mendaftarkan route)

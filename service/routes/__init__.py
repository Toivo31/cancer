"""Routers, one module per concern. ``service.app`` imports every module in this package and includes its
module-level ``router`` under ``/api`` (so adding a file adds its endpoints; no other file changes).

A module may also define ``on_startup(app)`` and ``on_shutdown(app)``; they run with the application's life
(for example the job runner's process pool).
"""

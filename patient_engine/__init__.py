"""Patient engine: synthetic patients as cards whose truth is hidden (component C1).

Modules (wave 2):
  card       card/1 types (hidden and revealed sides are different types, invariant I1),
             JSON round trip, library/1 manifest and cohort/1 spec shapes
  catalogue  catalogue/1 loader and validator (format: catalogue/README.md)
  schema     JSON Schema of a card generated from a catalogue, and a small validator for it
  problems   the problem object shared by the catalogue and card checks

Synthetic data only.
"""

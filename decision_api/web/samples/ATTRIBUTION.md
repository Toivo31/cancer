# Medical image examples

PAD-UFES-20, Andre G. C. Pacheco et al. (2020).
Original dataset: https://doi.org/10.17632/zr7vgbcyr2.1
License: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/

Three original PNG files, unchanged. Source IDs and SHA256 hashes are recorded
in catalog.json. The examples are from the existing training split. They are
for interface demonstrations, not held-out model evaluation. Context contains
published patient metadata; diagnostic labels are not sent as scoring input.

The bundled precomputed decisions were recorded from our checkpoint 1138 with
NF4 expert quantization. Their source and timestamp remain visible. Scores are
relative candidate scores, not calibrated disease probabilities. All three
also matched their dataset labels without the images; useful image understanding
has not been established by these examples.

# Three-Sensor Ensemble Report

The v4 artifacts use an 18-feature vector derived only from MAX30105 heart rate, GSR skin conductance, and MLX90614 temperature. Four base classifiers (SVM, Random Forest, XGBoost, and MLP) feed soft-voting and stacking ensembles.

WESAD inputs are limited to wrist BVP, EDA, and temperature for channel alignment with the wearable. Project GSR values and WESAD EDA still differ in units, so domain shift remains an important limitation.

Run `scripts/train_all_models.py` without `--skip-loso` to regenerate a complete nested subject-independent evaluation for v4.

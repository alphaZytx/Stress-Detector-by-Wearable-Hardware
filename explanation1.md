# Project Explanation

The wearable combines three physiological signals: MAX30105 optical heart rate, GSR skin conductance, and MLX90614 temperature. The ESP32 sends one five-field packet per second. The backend collects 30 seconds, advances by five seconds, and summarizes each window as 18 features.

The features capture heart-rate level/variation/trend, skin-conductance level/variation/responses, and temperature level/variation/trend. Four base classifiers and two ensemble options estimate baseline versus stress. Live results are smoothed and sent to the React dashboard, where users can inspect the three raw signals, record sessions, calibrate resting baselines, and open a guided breathing exercise.

Training and serving use the same feature code and order. WESAD contributes only BVP, EDA, and temperature so its channels align with the current wearable. See `README.md` for setup and `22freature_explanation.md` for the feature definitions.

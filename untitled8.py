# -*- coding: utf-8 -*-
"""
Created on Sat Sep  7 01:28:17 2024

@author: SATHISH
"""

import numpy as np
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from tensorflow.keras.models import load_model
import os
# Configuration
img_width, img_height = 150, 150
model_path = 'machine/plant_disease_model.h5.keras'

# Load the model
model = load_model(model_path)

def preprocess_image(image_path, target_size=(150, 150)):
    """Preprocess the input image for prediction."""
    image = load_img(image_path, color_mode='rgb', target_size=target_size)
    image = img_to_array(image)
    image = np.expand_dims(image, axis=0)
    image = image / 255.0
    return image

def predict_image(image_path):
    """Predict the class of an input image."""
    image = preprocess_image(image_path)
    prediction = model.predict(image)
    class_idx = np.argmax(prediction, axis=1)[0]
    class_names = os.listdir('data/train')# Update with your class names
    return class_names[class_idx]

# Example usage
image_path = 'data/test/am1.png'
predicted_class = predict_image(image_path)
print(f"Predicted Class: {predicted_class}")

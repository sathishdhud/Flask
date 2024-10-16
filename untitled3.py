import numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.callbacks import ModelCheckpoint
from PIL import UnidentifiedImageError, Image
import os

img_width, img_height = 150, 150
batch_size = 32
epochs = 20

train_dir = 'data/train'
validation_dir = 'data/validate'
model_path = 'machine/plant_disease_model.h5.keras'  # HDF5 format

# Function to remove corrupted images
def remove_corrupted_images(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                # Try to open the image
                img = Image.open(file_path)
                img.verify()  # Verify that it's a valid image
            except (UnidentifiedImageError, OSError) as e:
                # If the image is corrupted or not valid, remove it
                print(f"Removing corrupted image: {file_path}")
                os.remove(file_path)

# Remove corrupted images before loading data
remove_corrupted_images(train_dir)
remove_corrupted_images(validation_dir)

# Image data generators for augmenting training images and scaling validation images
train_datagen = ImageDataGenerator(
    rescale=1.0/255,
    rotation_range=40,
    width_shift_range=0.2,
    height_shift_range=0.2,
    shear_range=0.2,
    zoom_range=0.2,
    horizontal_flip=True,
    fill_mode='nearest'
)

validation_datagen = ImageDataGenerator(rescale=1.0/255)

# Generate batches of images and labels from the directories
train_generator = train_datagen.flow_from_directory(
    train_dir,
    target_size=(img_width, img_height),
    batch_size=batch_size,
    class_mode='categorical'
)

validation_generator = validation_datagen.flow_from_directory(
    validation_dir,
    target_size=(img_width, img_height),
    batch_size=batch_size,
    class_mode='categorical'
)

# Build the CNN model
model = Sequential([
    Conv2D(32, (3, 3), activation='relu', input_shape=(img_width, img_height, 3)),
    MaxPooling2D(pool_size=(3, 3)),
    Conv2D(64, (3, 3), activation='relu'),
    MaxPooling2D(pool_size=(3, 3)),
    Conv2D(128, (3, 3), activation='relu'),
    MaxPooling2D(pool_size=(3, 3)),
    Flatten(),
    Dense(512, activation='relu'),
    Dense(train_generator.num_classes, activation='softmax')  # Use the correct number of classes
])

# Compile the model with optimizer and loss function
model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])

# Save the best model based on validation loss
checkpoint = ModelCheckpoint(model_path, save_best_only=True, monitor='val_loss', verbose=1)

# Train the model
history = model.fit(
    train_generator,
    epochs=epochs,
    validation_data=validation_generator,
    callbacks=[checkpoint]
)

# Save the final model
model.save(model_path)

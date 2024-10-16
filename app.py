from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
import os
import numpy as np
from PIL import Image
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import img_to_array, load_img

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MODEL_PATH'] = 'machine/plant_disease_model.h5.keras'  
app.config['CATEGORY_IMAGE_FOLDER'] = 'D:\\App\\data\\train'  # Path to your category image folders

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def preprocess_image(image_path):
    image = load_img(image_path, target_size=(150, 150))  
    image = img_to_array(image)
    image = np.expand_dims(image, axis=0)
    image = image / 255.0  
    return image

def predict_disease(image_path):
    model = load_model(app.config['MODEL_PATH'])
    image = preprocess_image(image_path)
    prediction = model.predict(image)
    class_idx = np.argmax(prediction, axis=1)[0]  
    class_names = sorted(os.listdir(app.config['CATEGORY_IMAGE_FOLDER']))
    category = class_names[class_idx]
    
    # List all images in the predicted category folder
    category_folder = os.path.join(app.config['CATEGORY_IMAGE_FOLDER'], category)
    category_images = os.listdir(category_folder)
    category_images = [url_for('category_image', category=category, filename=img) for img in category_images]
    
    return category, category_images

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Predict the disease and get all category images
            category, category_images = predict_disease(filepath)
            
            # Generate the URL for the uploaded file
            image_url = url_for('uploaded_file', filename=filename)
            return render_template('module.html', prediction=category, image_url=image_url, category_images=category_images)
    
    return render_template('upload.html', prediction=None, image_url=None, category_images=[])

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/category/<category>/<filename>')
def category_image(category, filename):
    category_folder = os.path.join(app.config['CATEGORY_IMAGE_FOLDER'], category)
    return send_from_directory(category_folder, filename)

if __name__ == '__main__':
    print("Starting Flask app...")
    app.run(debug=True)

import io
import os
import hashlib
import re
import time
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, flash
from PIL import Image
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models, transforms
import pymongo
from functools import wraps

CLASS_NAMES = ["NORMAL", "PNEUMONIA", "UNKNOWN", "TUBERCULOSIS"]
MODEL_PATH = os.getenv("MODEL_PATH", os.path.join(os.path.dirname(__file__), "model.pt"))
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://projectDB:PEyHwQ2fF7e5saEf@cluster0.43hxo.mongodb.net/")
DB_NAME = os.getenv("DB_NAME", "ta7t-bety")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "paitents")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")


def init_db():
    try:
        client = pymongo.MongoClient(MONGODB_URI)
        db = client[DB_NAME]
        client.server_info()
        return db[COLLECTION_NAME]
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        return None

collection = init_db()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def is_valid_email(email):
    gmail_pattern = r'^[a-zA-Z0-9._%+-]+@gmail\.com$'
    return re.match(gmail_pattern, email) is not None

def register_user(collection, name, email, password):
    if collection is None:
        return False, "Failed to connect to database"
    
    if not is_valid_email(email):
        return False, "Please use a valid Gmail address (****@gmail.com)"
    
    try:
        if collection.find_one({"email": email}):
            return False, "Email already in use"
        
        user_data = {
            "name": name,
            "email": email,
            "password": hash_password(password),
            "created_at": time.time()
        }
        
        collection.insert_one(user_data)
        return True, "User registered successfully"
    except Exception as e:
        return False, f"Registration failed: {str(e)}"

def verify_user(collection, email, password):
    if collection is None:
        return False, None
    
    try:
        hashed_password = hash_password(password)
        user = collection.find_one({"email": email, "password": hashed_password})
        
        if user:
            return True, {"name": user['name'], "email": user['email']}
        return False, None
    except Exception as e:
        print(f"Login failed: {e}")
        return False, None


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def load_model(model_path):
    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, 4)
    state_dict = torch.load(model_path, map_location=DEVICE)
    model.load_state_dict(state_dict)
    model.to(DEVICE)
    model.eval()
    return model

preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.Grayscale(num_output_channels=3),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])

def preprocess_image(file_storage):
    image_bytes = file_storage.read()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = preprocess(img).unsqueeze(0)
    return tensor.to(DEVICE)

def predict(model, input_tensor):
    with torch.no_grad():
        outputs = model(input_tensor)
        probs = F.softmax(outputs, dim=1)[0].cpu().numpy()
    top_idx = int(probs.argmax())
    predicted_class = CLASS_NAMES[top_idx]
    probabilities = {CLASS_NAMES[i]: float(probs[i]) for i in range(len(CLASS_NAMES))}
    return predicted_class, probabilities


try:
    model = load_model(MODEL_PATH)
except Exception as e:
    print("Model load error:", e)
    model = None


@app.route("/api", methods=["GET"])
def api_home():
    return jsonify({
        "status": "ok",
        "message": "Chest X-Ray Classification API running",
        "classes": CLASS_NAMES
    })

@app.route("/api/predict", methods=["POST"])
def predict_route():
    if model is None:
        return jsonify({"error": "Model not loaded"}), 500

    if "image" not in request.files:
        return jsonify({"error": "Image file missing"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Invalid filename"}), 400

    try:
        input_tensor = preprocess_image(file)
        predicted_class, probabilities = predict(model, input_tensor)
        return jsonify({
            "predicted_class": predicted_class,
            "probabilities": probabilities
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        if email and password:
            success, user_data = verify_user(collection, email, password)
            if success:
                session['user'] = user_data
                session['authenticated'] = True
                flash("Login successful!", "success")
                return redirect(url_for('index'))
            else:
                flash("Invalid email or password. Please register if you don't have an account.", "error")
        else:
            flash("Please fill in all fields", "error")
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        
        if name and email and password and confirm_password:
            if password != confirm_password:
                flash("Passwords do not match", "error")
            else:
                success, message = register_user(collection, name, email, password)
                if success:
                    flash("Account created successfully! Please login.", "success")
                    return redirect(url_for('login'))
                else:
                    flash(message, "error")
        else:
            flash("Please fill in all fields", "error")
    
    return render_template_string(REGISTER_TEMPLATE)

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))

@app.route("/")
@login_required
def index():
    return render_template_string(MAIN_TEMPLATE, user=session.get('user'))


LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>MediScan - Login</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 400px; margin: 50px auto; padding: 20px; }
        input { width: 100%; padding: 10px; margin: 10px 0; }
        button { width: 100%; padding: 10px; background: #14213d; color: white; border: none; cursor: pointer; }
        .error { color: red; }
        .success { color: green; }
    </style>
</head>
<body>
    <h1>🔬 MediScan</h1>
    <h2>Login</h2>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <p class="{{ category }}">{{ message }}</p>
            {% endfor %}
        {% endif %}
    {% endwith %}
    <form method="POST">
        <input type="email" name="email" placeholder="your.email@gmail.com" required>
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit">Sign In</button>
    </form>
    <p><a href="{{ url_for('register') }}">Don't have an account? Register</a></p>
</body>
</html>
"""

REGISTER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>MediScan - Register</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 400px; margin: 50px auto; padding: 20px; }
        input { width: 100%; padding: 10px; margin: 10px 0; }
        button { width: 100%; padding: 10px; background: #14213d; color: white; border: none; cursor: pointer; }
        .error { color: red; }
        .success { color: green; }
    </style>
</head>
<body>
    <h1>🔬 MediScan</h1>
    <h2>Register</h2>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <p class="{{ category }}">{{ message }}</p>
            {% endfor %}
        {% endif %}
    {% endwith %}
    <form method="POST">
        <input type="text" name="name" placeholder="Full Name" required>
        <input type="email" name="email" placeholder="your.email@gmail.com" required>
        <input type="password" name="password" placeholder="Password" required>
        <input type="password" name="confirm_password" placeholder="Confirm Password" required>
        <button type="submit">Create Account</button>
    </form>
    <p><a href="{{ url_for('login') }}">Already have an account? Login</a></p>
</body>
</html>
"""

MAIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>MediScan - Chest X-Ray Analysis</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #04080f; color: white; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        .container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .box { background: rgba(20, 33, 61, 0.95); padding: 20px; border-radius: 12px; }
        input[type="file"] { margin: 20px 0; }
        button { padding: 10px 20px; background: #14213d; color: white; border: none; cursor: pointer; border-radius: 8px; }
        button:hover { background: #1a2950; }
        #result { margin-top: 20px; }
        .prob-bar { background: rgba(255,255,255,0.2); height: 20px; border-radius: 4px; margin: 5px 0; }
        .prob-fill { background: white; height: 100%; border-radius: 4px; transition: width 0.3s; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔬 MediScan - Chest X-Ray Analysis</h1>
        <div>
            <span>Welcome, {{ user.name }}</span>
            <a href="{{ url_for('logout') }}" style="color: white; margin-left: 20px;">Logout</a>
        </div>
    </div>
    
    <div class="container">
        <div class="box">
            <h2>Upload X-Ray Image</h2>
            <input type="file" id="imageInput" accept="image/*">
            <div id="imagePreview"></div>
            <button onclick="analyzeImage()" id="analyzeBtn" disabled>Analyze Image</button>
        </div>
        
        <div class="box">
            <h2>Diagnosis Results</h2>
            <div id="result">
                <p>Upload and analyze an X-ray image to see results</p>
            </div>
        </div>
    </div>
    
    <script>
        const imageInput = document.getElementById('imageInput');
        const analyzeBtn = document.getElementById('analyzeBtn');
        const imagePreview = document.getElementById('imagePreview');
        const resultDiv = document.getElementById('result');
        
        imageInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    imagePreview.innerHTML = `<img src="${e.target.result}" style="max-width: 100%; border-radius: 8px;">`;
                    analyzeBtn.disabled = false;
                };
                reader.readAsDataURL(file);
            }
        });
        
        async function analyzeImage() {
            const file = imageInput.files[0];
            if (!file) return;
            
            analyzeBtn.disabled = true;
            analyzeBtn.textContent = 'Analyzing...';
            resultDiv.innerHTML = '<p>Analyzing image...</p>';
            
            const formData = new FormData();
            formData.append('image', file);
            
            try {
                const response = await fetch('/api/predict', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    let html = `<h3>${data.predicted_class}</h3>`;
                    html += `<p>Confidence: ${(data.probabilities[data.predicted_class] * 100).toFixed(2)}%</p>`;
                    html += '<h4>Detailed Probabilities:</h4>';
                    
                    for (const [condition, prob] of Object.entries(data.probabilities)) {
                        html += `<div>
                            <div style="display: flex; justify-content: space-between;">
                                <span>${condition}</span>
                                <span>${(prob * 100).toFixed(2)}%</span>
                            </div>
                            <div class="prob-bar">
                                <div class="prob-fill" style="width: ${prob * 100}%"></div>
                            </div>
                        </div>`;
                    }
                    
                    html += '<p style="margin-top: 20px; font-size: 0.9em; opacity: 0.8;"><strong>Disclaimer:</strong> This analysis is for informational purposes only. Always consult with a qualified healthcare professional for medical diagnosis and treatment.</p>';
                    
                    resultDiv.innerHTML = html;
                } else {
                    resultDiv.innerHTML = `<p style="color: red;">Error: ${data.error}</p>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
            }
            
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = 'Analyze Image';
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


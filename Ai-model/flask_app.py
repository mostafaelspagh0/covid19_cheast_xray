import io
import os
from flask import Flask, request, jsonify
from PIL import Image
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models, transforms

CLASS_NAMES = ["NORMAL", "PNEUMONIA", "UNKNOWN", "TUBERCULOSIS"]
MODEL_PATH = r"C:\Users\mostafa\Documents\GitHub\covid19_cheast_xray\Ai-model\model.pt"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

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

app = Flask(__name__)

try:
    model = load_model(MODEL_PATH)
except Exception as e:
    print("Model load error:", e)
    model = None

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "Chest X-Ray Classification API running",
        "classes": CLASS_NAMES
    })

@app.route("/predict", methods=["POST"])
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

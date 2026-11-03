
# TUVE QUE INSTALAR PYTHON 3.10 !!!

from pathlib import Path
from tensorflow.keras.models import load_model
from tensorflow.keras.layers import DepthwiseConv2D
from PIL import Image, ImageOps
import numpy as np


# # Keep keras_Model.h5 and labels.txt in the directory where you run this script.
model = load_model("C2_4_keras_model.h5", compile=False)

with open("labels.txt", encoding="utf-8") as f:
    # Handles labels such as "0 Normal" and "1 Neumonia_viral".
    class_names = [line.strip().split(maxsplit=1)[-1]
                   for line in f if line.strip()]

image_folder = Path(
    r"C:\Users\Evelyn\Downloads\TP-2\TP 2\Prueba_NO_CARGAR_EN_ENTRENAMIENTO"
)
image_paths = sorted(
    path for path in image_folder.rglob("*")
    if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
)

for image_path in image_paths:
    with Image.open(image_path) as image:
        image = ImageOps.fit(
            image.convert("RGB"),
            (224, 224),
            method=Image.Resampling.LANCZOS,
        )
        image_array = np.asarray(image, dtype=np.float32)

    data = np.empty((1, 224, 224, 3), dtype=np.float32)
    data[0] = (image_array / 127.5) - 1

    probabilities = model.predict(data, verbose=0)[0]
    if len(probabilities) != len(class_names):
        raise ValueError("The number of labels does not match the model output.")

    print(f"\nImage: {image_path.name}")
    print(f"Real class: {image_path.parent.name}")
    for class_name, probability in zip(class_names, probabilities):
        print(f"  {class_name}: {probability:.2%}")
    print(f"Predicted class: {class_names[np.argmax(probabilities)]}")

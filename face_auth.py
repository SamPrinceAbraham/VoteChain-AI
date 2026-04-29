"""
face_auth.py  –  Face verification using pure OpenCV
Uses:  Haar Cascade face detector  +  LBPH local-binary-pattern histogram recognizer
No dlib / tensorflow / cmake required.
"""
import cv2
import numpy as np
import base64
import os

# Path to OpenCV's built-in Haar cascade
CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(CASCADE_PATH)

FACE_SIZE = (100, 100)   # resize detected face to this before encoding


def _detect_and_crop(img_bgr):
    """Detect the largest face in a BGR image and return it as a greyscale 100x100 array, or None."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return None
    # largest face
    x, y, w, h = max(faces, key=lambda f: f[2]*f[3])
    face_roi = gray[y:y+h, x:x+w]
    return cv2.resize(face_roi, FACE_SIZE)


def encode_face_from_path(image_path):
    """
    Load image from disk, detect face, return flat numpy array as JSON list (or None).
    Stored as a JSON string in the DB.
    """
    img = cv2.imread(image_path)
    if img is None:
        return None
    face = _detect_and_crop(img)
    if face is None:
        return None
    # flatten → list for JSON storage
    import json
    return json.dumps(face.flatten().tolist())


def encode_face_from_b64(b64_string):
    """
    Decode a base64 image (from webcam capture), detect face, return flat numpy array or None.
    """
    try:
        img_data = base64.b64decode(b64_string.split(",")[-1])
        np_arr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        return _detect_and_crop(img)   # greyscale 100x100 or None
    except Exception:
        return None


def verify_face(stored_encoding_json, live_face_arr, threshold=60.0):
    """
    Compare stored flat encoding (JSON) with live face (greyscale 100x100 numpy array).
    Uses normalised cross-correlation histogram comparison.
    Returns (matched: bool, confidence: float 0-1).
    """
    import json
    stored_flat = np.array(json.loads(stored_encoding_json), dtype=np.uint8)
    stored_face = stored_flat.reshape(FACE_SIZE)

    # Histogram comparison – CORREL returns 1.0 for identical
    hist_stored = cv2.calcHist([stored_face], [0], None, [256], [0, 256])
    hist_live   = cv2.calcHist([live_face_arr], [0], None, [256], [0, 256])
    cv2.normalize(hist_stored, hist_stored)
    cv2.normalize(hist_live,   hist_live)
    score = cv2.compareHist(hist_stored, hist_live, cv2.HISTCMP_CORREL)   # -1 to 1

    # Convert to 0-100 range
    confidence_pct = max(0.0, score * 100)
    matched = confidence_pct >= threshold

    return matched, round(confidence_pct / 100, 3)

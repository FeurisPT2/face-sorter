import os
import urllib.request
import cv2
import numpy as np
from pathlib import Path
import uuid

class FaceProcessor:
    YUNET_URL = "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx"
    SFACE_URL = "https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx"
    
    def __init__(self, models_dir=None):
        if models_dir is None:
            # Default models dir in the project
            models_dir = Path(__file__).parent.parent / "models"
        
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.yunet_path = self.models_dir / "face_detection_yunet_2023mar.onnx"
        self.sface_path = self.models_dir / "face_recognition_sface_2021dec.onnx"
        
        self.detector = None
        self.recognizer = None

    def ensure_models(self, progress_callback=None):
        """Ensures both YuNet and SFace model files are downloaded locally."""
        def download_with_progress(url, dest_path, model_name):
            if dest_path.exists():
                # Check if it's not a tiny file (pointer)
                if dest_path.stat().st_size > 100000:
                    return
                dest_path.unlink()
            
            if progress_callback:
                progress_callback(f"Đang tải mô hình {model_name}...")
            
            print(f"Downloading {model_name} from {url} to {dest_path}...")
            
            # Simple download
            urllib.request.urlretrieve(url, dest_path)
            
            # Verify file size
            if dest_path.stat().st_size < 100000:
                raise Exception(f"Tải mô hình {model_name} thất bại hoặc tệp tin bị hỏng (kích thước quá nhỏ).")

        download_with_progress(self.YUNET_URL, self.yunet_path, "YuNet (Phát hiện khuôn mặt)")
        download_with_progress(self.SFACE_URL, self.sface_path, "SFace (Nhận diện khuôn mặt)")

    def load_models(self):
        """Initializes OpenCV YuNet and SFace models."""
        self.ensure_models()
        
        # Initialize YuNet Detector
        # Default input size is (320, 320), will be updated dynamically based on image size
        self.detector = cv2.FaceDetectorYN.create(
            model=str(self.yunet_path),
            config="",
            input_size=(320, 320),
            score_threshold=0.75, # Good balance of precision and recall
            nms_threshold=0.3,
            top_k=5000
        )
        
        # Initialize SFace Recognizer
        self.recognizer = cv2.FaceRecognizerSF.create(
            model=str(self.sface_path),
            config=""
        )

    def scan_image(self, img_path, cache_dir, max_dim=1200):
        """
        Scans a single image, detects faces, aligns & crops them, and extracts embeddings.
        Returns a list of dictionaries with face metadata.
        """
        if self.detector is None or self.recognizer is None:
            self.load_models()
            
        img_path = Path(img_path)
        # Read image with OpenCV, or rawpy for Sony RAW .ARW files
        img = None
        try:
            if img_path.suffix.lower() == ".arw":
                import rawpy
                with rawpy.imread(str(img_path)) as raw:
                    # Postprocess RAW to RGB numpy array
                    rgb = raw.postprocess()
                    # Convert RGB to BGR for OpenCV
                    img = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            else:
                img_data = np.fromfile(str(img_path), np.uint8)
                img = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
        except Exception as e:
            print(f"Error reading image {img_path}: {e}")
            return []
            
        if img is None:
            print(f"Skipping {img_path}: Could not decode image.")
            return []
            
        h, w, _ = img.shape
        if h == 0 or w == 0:
            return []
            
        # Scale image down for faster and more reliable detection on CPU if it's too large
        scale = 1.0
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img_detect = cv2.resize(img, (new_w, new_h))
        else:
            img_detect = img
            
        dh, dw, _ = img_detect.shape
        self.detector.setInputSize((dw, dh))
        
        # Detect faces
        try:
            _, faces = self.detector.detect(img_detect)
        except Exception as e:
            print(f"YuNet detection error on {img_path.name}: {e}")
            return []
            
        results = []
        if faces is not None:
            cache_dir = Path(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            for idx, face in enumerate(faces):
                # face contains 15 elements:
                # 0:4 bounding box [x, y, w, h]
                # 4:14 facial landmarks [x, y] x 5
                # 14 confidence score
                
                # Scale landmarks and bbox back to original image size
                face_orig = face.copy()
                if scale != 1.0:
                    face_orig[0:14] = face_orig[0:14] / scale
                
                # Bounding box coordinates in original image
                x, y, width, height = face_orig[0:4].astype(int)
                score = float(face_orig[14])
                
                # Align and crop the face using original high-resolution image
                try:
                    aligned_face = self.recognizer.alignCrop(img, face_orig)
                    # Extract 128-d feature representation
                    feature = self.recognizer.feature(aligned_face)
                    feature_vector = feature[0].tolist() # Convert to a flat list
                except Exception as e:
                    print(f"SFace processing error on face {idx} of {img_path.name}: {e}")
                    continue
                
                # Generate unique ID for this face crop
                face_id = str(uuid.uuid4())
                crop_filename = f"{face_id}.jpg"
                crop_path = cache_dir / crop_filename
                
                # Save cropped face thumbnail (112x112 pixels, guaranteed by alignCrop)
                _, crop_buf = cv2.imencode(".jpg", aligned_face)
                crop_buf.tofile(str(crop_path))
                
                results.append({
                    "id": face_id,
                    "original_image": str(img_path),
                    "original_image_name": img_path.name,
                    "crop_image": f"/static/cache/{crop_filename}",
                    "crop_path": str(crop_path),
                    "bbox": [int(x), int(y), int(width), int(height)],
                    "score": score,
                    "embedding": feature_vector
                })
                
        return results

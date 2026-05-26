import os
import gc
import urllib.request
import cv2
import numpy as np
from pathlib import Path
import uuid
import onnxruntime as ort
from math import ceil
from itertools import product

# --- Module-level worker support for ProcessPoolExecutor ---
# Each worker process keeps its own FaceProcessor instance in this global variable.
# This avoids re-loading RetinaFace + ArcFace models for every single image.
_worker_processor = None

def _init_worker(models_dir_str):
    """Called once when a worker process starts. Loads models into process-local global."""
    global _worker_processor
    _worker_processor = FaceProcessor(models_dir=models_dir_str)
    _worker_processor.load_models()

def _process_single_image(args):
    """
    Top-level function callable by ProcessPoolExecutor.
    Receives (img_path_str, cache_dir_str) and returns list of face dicts.
    Uses the process-local _worker_processor initialized by _init_worker.
    """
    global _worker_processor
    img_path_str, cache_dir_str = args
    try:
        results = _worker_processor.scan_image(img_path_str, cache_dir_str)
        # Explicit GC after processing to free large RAW buffers in worker memory
        gc.collect()
        return results
    except Exception as e:
        print(f"Worker error processing {img_path_str}: {e}")
        return []

class FaceProcessor:
    RETINAFACE_URL = "https://github.com/yakhyo/retinaface-pytorch/releases/download/v0.0.1/retinaface_mv1_0.25.onnx"
    ARCFACE_URL = "https://huggingface.co/yolkailtd/face-swap-models/resolve/main/insightface/models/buffalo_l/w600k_r50.onnx"
    
    MIN_LAPLACIAN_VAR = 350.0  # Minimum sharpness score (blurry face filter)
    MAX_BLACK_RATIO = 0.10    # Maximum pure black pixels ratio (cropped face filter)
    
    # RetinaFace MobileNet0.25 standard anchor config
    cfg_mnet = {
        'min_sizes': [[16, 32], [64, 128], [256, 512]],
        'steps': [8, 16, 32],
        'variance': [0.1, 0.2],
        'clip': False,
    }
    
    # ArcFace standard 112x112 aligned template landmarks in BGR/RGB order
    # (InsightFace standard eye-nose-mouth reference coordinates)
    arcface_src_pts = np.array([
        [30.2946, 51.6963],  # left eye
        [65.5318, 51.5014],  # right eye
        [48.0252, 71.7366],  # nose tip
        [33.5493, 92.3655],  # left mouth corner
        [62.7299, 92.2041]   # right mouth corner
    ], dtype=np.float32)
    
    def __init__(self, models_dir=None):
        if models_dir is None:
            # Default models dir in the project
            models_dir = Path(__file__).parent.parent / "models"
        
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.retinaface_path = self.models_dir / "retinaface_mv1_0.25.onnx"
        self.arcface_path = self.models_dir / "w600k_r50.onnx"
        
        self.detector_session = None
        self.recognizer_session = None

    def ensure_models(self, progress_callback=None):
        """Ensures both RetinaFace and ArcFace model files are downloaded locally."""
        def download_with_progress(url, dest_path, model_name):
            if dest_path.exists():
                # Check if it's not a tiny file (pointer)
                if dest_path.stat().st_size > 1000000:
                    return
                dest_path.unlink()
            
            if progress_callback:
                progress_callback(f"Đang tải mô hình {model_name}...")
            
            print(f"Downloading {model_name} from {url} to {dest_path}...")
            
            # Download with standard browser User-Agent header to bypass HF blocks
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
            )
            try:
                with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
                    out_file.write(response.read())
            except Exception as e:
                if dest_path.exists():
                    dest_path.unlink()
                raise e
            
            # Verify file size
            if dest_path.stat().st_size < 1000000:
                raise Exception(f"Tải mô hình {model_name} thất bại hoặc tệp tin bị hỏng (kích thước quá nhỏ).")

        download_with_progress(self.RETINAFACE_URL, self.retinaface_path, "RetinaFace (Phát hiện khuôn mặt)")
        download_with_progress(self.ARCFACE_URL, self.arcface_path, "ArcFace INT8 (Nhận diện khuôn mặt)")

    def load_models(self):
        """Initializes ONNX Runtime sessions for RetinaFace and ArcFace."""
        self.ensure_models()
        
        # Configure CPU thread counts optimized for parallel/multi-processing execution
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        # Initialize detector session
        self.detector_session = ort.InferenceSession(
            str(self.retinaface_path),
            sess_options=opts,
            providers=['CPUExecutionProvider']
        )
        
        # Initialize recognizer session
        self.recognizer_session = ort.InferenceSession(
            str(self.arcface_path),
            sess_options=opts,
            providers=['CPUExecutionProvider']
        )
        
        # Query and map input/output names dynamically to be bulletproof against ONNX changes
        self.det_input_name = self.detector_session.get_inputs()[0].name
        self.det_output_names = [o.name for o in self.detector_session.get_outputs()]
        
        self.rec_input_name = self.recognizer_session.get_inputs()[0].name
        self.rec_output_name = self.recognizer_session.get_outputs()[0].name
        
        # Resolve output names by analyzing their static output dimension signatures
        self.det_loc_name = None
        self.det_conf_name = None
        self.det_landms_name = None
        
        for out in self.detector_session.get_outputs():
            shape = out.shape
            if len(shape) == 3:
                last_dim = shape[2]
                if last_dim == 4:
                    self.det_loc_name = out.name
                elif last_dim == 2:
                    self.det_conf_name = out.name
                elif last_dim == 10:
                    self.det_landms_name = out.name
        
        # Fallback to index-based ordering if dynamic detection finds anomalies
        if not (self.det_loc_name and self.det_conf_name and self.det_landms_name):
            self.det_loc_name = self.det_output_names[0]
            self.det_conf_name = self.det_output_names[1]
            self.det_landms_name = self.det_output_names[2]

    def _generate_priors(self, image_size):
        """
        Generates anchor boxes (priors) for the given image size (h, w)
        matching the MobileNet0.25 feature strides and scales.
        """
        min_sizes = self.cfg_mnet['min_sizes']
        steps = self.cfg_mnet['steps']
        
        feature_maps = [
            [ceil(image_size[0] / step), ceil(image_size[1] / step)]
            for step in steps
        ]
        
        anchors = []
        for k, f in enumerate(feature_maps):
            min_sizes_k = min_sizes[k]
            for i, j in product(range(f[0]), range(f[1])):
                for min_size in min_sizes_k:
                    s_kx = min_size / image_size[1]
                    s_ky = min_size / image_size[0]
                    cx = (j + 0.5) * steps[k] / image_size[1]
                    cy = (i + 0.5) * steps[k] / image_size[0]
                    anchors.append([cx, cy, s_kx, s_ky])
                    
        return np.array(anchors, dtype=np.float32)

    def _decode_boxes(self, loc, priors):
        """
        Decodes bounding boxes from location offsets relative to priors.
        loc shape: [num_anchors, 4] where elements are [dx, dy, dw, dh]
        priors shape: [num_anchors, 4] where elements are [cx, cy, pw, ph]
        Returns: decoded boxes of shape [num_anchors, 4] in corner coordinates [x1, y1, x2, y2]
        """
        variance = self.cfg_mnet['variance']
        boxes = np.zeros_like(loc)
        # cx = prior_cx + dx * var[0] * prior_pw
        # cy = prior_cy + dy * var[0] * prior_ph
        boxes[:, 0:2] = priors[:, 0:2] + loc[:, 0:2] * variance[0] * priors[:, 2:4]
        # w = prior_pw * exp(dw * var[1])
        # h = prior_ph * exp(dh * var[1])
        boxes[:, 2:4] = priors[:, 2:4] * np.exp(loc[:, 2:4] * variance[1])
        
        # Convert [cx, cy, w, h] to [x1, y1, x2, y2]
        boxes[:, 0:2] -= boxes[:, 2:4] / 2
        boxes[:, 2:4] += boxes[:, 0:2]
        return boxes

    def _decode_landmarks(self, pre, priors):
        """
        Decodes facial landmarks from offsets relative to priors.
        pre shape: [num_anchors, 10]
        priors shape: [num_anchors, 4]
        Returns: decoded landmarks of shape [num_anchors, 10] as [x1, y1, ..., x5, y5]
        """
        variance = self.cfg_mnet['variance']
        landms = np.zeros_like(pre)
        for i in range(5):
            idx = i * 2
            # lx = prior_cx + l_dx * var[0] * prior_pw
            # ly = prior_cy + l_dy * var[0] * prior_ph
            landms[:, idx:idx+2] = priors[:, 0:2] + pre[:, idx:idx+2] * variance[0] * priors[:, 2:4]
        return landms

    def _apply_clahe(self, img):
        """
        Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to improve
        face detection in challenging lighting conditions common in yearbook photos.
        Operates on the L channel of LAB color space to preserve color.
        """
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l_channel)
        
        enhanced_lab = cv2.merge([l_enhanced, a_channel, b_channel])
        enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
        return enhanced_bgr

    def _detect_faces_at_scale(self, img, max_dim):
        """
        Detect faces in image at a specific max dimension scale using RetinaFace.
        Returns a list of 15-element arrays compatible with OpenCV YN format.
        """
        h, w = img.shape[:2]
        scale = 1.0
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img_detect = cv2.resize(img, (new_w, new_h))
        else:
            img_detect = img.copy()
            
        dh, dw = img_detect.shape[:2]
        
        # Preprocessing: BGR mean subtraction, channel transpose, batch expand
        img_input = img_detect.astype(np.float32)
        img_input -= np.array([104.0, 117.0, 123.0], dtype=np.float32)
        img_input = img_input.transpose(2, 0, 1)  # (H, W, C) -> (C, H, W)
        img_input = np.expand_dims(img_input, axis=0)  # (1, C, H, W)
        
        try:
            outputs = self.detector_session.run(
                [self.det_loc_name, self.det_conf_name, self.det_landms_name],
                {self.det_input_name: img_input}
            )
            
            loc = None
            conf = None
            landms = None
            
            for idx, out_name in enumerate([self.det_loc_name, self.det_conf_name, self.det_landms_name]):
                out_val = outputs[idx]
                if out_name == self.det_loc_name:
                    loc = out_val[0]
                elif out_name == self.det_conf_name:
                    conf = out_val[0]
                elif out_name == self.det_landms_name:
                    landms = out_val[0]
        except Exception as e:
            print(f"RetinaFace inference error at scale {max_dim}: {e}")
            return []
            
        priors = self._generate_priors((dh, dw))
        
        boxes = self._decode_boxes(loc, priors)
        landmarks = self._decode_landmarks(landms, priors)
        
        # Scale decoded coordinates from normalized (0..1) to actual pixel coordinates on img_detect
        scale_box = np.array([dw, dh, dw, dh], dtype=np.float32)
        boxes = boxes * scale_box
        
        scale_landms = np.array([dw, dh, dw, dh, dw, dh, dw, dh, dw, dh], dtype=np.float32)
        landmarks = landmarks * scale_landms
        
        if conf.shape[1] == 2:
            # Apply softmax to raw logits to convert them to actual probabilities
            exp_conf = np.exp(conf - np.max(conf, axis=1, keepdims=True))
            probs = exp_conf / np.sum(exp_conf, axis=1, keepdims=True)
            scores = probs[:, 1]
        else:
            # Sigmoid fallback for single logit case
            scores = 1.0 / (1.0 + np.exp(-conf[:, 0]))
            
        # Select candidates with score > 0.5 to forward to strict NMS checks
        idx_keep = np.where(scores > 0.5)[0]
        
        boxes = boxes[idx_keep]
        scores = scores[idx_keep]
        landmarks = landmarks[idx_keep]
        
        result_faces = []
        for i in range(len(boxes)):
            box = boxes[i] / scale
            score = scores[i]
            lms = landmarks[i] / scale
            
            x1, y1, x2, y2 = box
            
            # Pack into standard 15-element array compatible with OpenCV YN
            face_arr = np.zeros(15, dtype=np.float32)
            face_arr[0] = x1
            face_arr[1] = y1
            face_arr[2] = x2 - x1
            face_arr[3] = y2 - y1
            face_arr[4:14] = lms
            face_arr[14] = score
            
            result_faces.append(face_arr)
            
        return result_faces

    def _nms_faces(self, all_faces, iou_threshold=0.4, iom_threshold=0.7):
        """
        Apply Non-Maximum Suppression to merge overlapping face detections
        from multi-scale detection passes. Uses both IoU (Intersection over Union)
        and IoM (Intersection over Minimum) to effectively merge boxes of different scales
        (e.g., tight vs loose scaled bounding boxes on the same face).
        """
        if len(all_faces) == 0:
            return []
        
        # Extract bounding boxes and scores
        boxes = []
        scores = []
        for face in all_faces:
            x, y, w, h = face[0:4]
            boxes.append([float(x), float(y), float(x + w), float(y + h)])
            scores.append(float(face[14]))
        
        boxes = np.array(boxes)
        scores = np.array(scores)
        
        # Sort by score descending
        order = scores.argsort()[::-1]
        
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            
            if order.size == 1:
                break
            
            # Compute intersection coordinates
            xx1 = np.maximum(boxes[i, 0], boxes[order[1:], 0])
            yy1 = np.maximum(boxes[i, 1], boxes[order[1:], 1])
            xx2 = np.minimum(boxes[i, 2], boxes[order[1:], 2])
            yy2 = np.minimum(boxes[i, 3], boxes[order[1:], 3])
            
            inter_w = np.maximum(0, xx2 - xx1)
            inter_h = np.maximum(0, yy2 - yy1)
            intersection = inter_w * inter_h
            
            # Compute areas
            area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
            area_rest = (boxes[order[1:], 2] - boxes[order[1:], 0]) * (boxes[order[1:], 3] - boxes[order[1:], 1])
            
            # IoU (Intersection over Union)
            union = area_i + area_rest - intersection
            iou = intersection / (union + 1e-6)
            
            # IoM (Intersection over Minimum / Self)
            min_area = np.minimum(area_i, area_rest)
            iom = intersection / (min_area + 1e-6)
            
            # Merge if either IoU or IoM exceeds threshold
            remaining = np.where((iou <= iou_threshold) & (iom <= iom_threshold))[0]
            order = order[remaining + 1]
        
        return [all_faces[i] for i in keep]

    def align_crop_face(self, img, face):
        """
        Align and crop face to 112x112 using similarity transform from 5 landmarks.
        `face` is the standard 15-element array where face[4:14] are landmarks.
        """
        landmarks = face[4:14].reshape(5, 2).astype(np.float32)
        
        # Estimate similarity transform matrix M (rotation, translation, scaling)
        M, _ = cv2.estimateAffinePartial2D(landmarks, self.arcface_src_pts)
        if M is None:
            # Fallback to direct box cropping if estimation fails
            x, y, w, h = face[0:4].astype(int)
            x = max(0, x)
            y = max(0, y)
            w = max(10, w)
            h = max(10, h)
            cropped = img[y:y+h, x:x+w]
            if cropped.size > 0:
                return cv2.resize(cropped, (112, 112))
            else:
                return np.zeros((112, 112, 3), dtype=np.uint8)
                
        # Warp the image to the standard 112x112 template
        aligned_face = cv2.warpAffine(img, M, (112, 112))
        return aligned_face

    def extract_embedding(self, aligned_face):
        """
        Extracts 512-d feature representation from aligned face (112x112) using ArcFace FP32.
        Returns L2-normalized embedding vector.
        """
        # Preprocessing: Convert BGR (OpenCV format) to RGB, and scale to [-1, 1] range
        rgb_face = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2RGB)
        img_input = rgb_face.astype(np.float32)
        img_input = (img_input - 127.5) / 128.0
        img_input = img_input.transpose(2, 0, 1)  # (H, W, C) -> (C, H, W)
        img_input = np.expand_dims(img_input, axis=0)  # (1, C, H, W)
        
        # Run recognizer session
        outputs = self.recognizer_session.run(
            [self.rec_output_name],
            {self.rec_input_name: img_input}
        )
        
        feature_vector = outputs[0][0]  # Squeeze batch dimension
        
        # L2 normalize
        norm = np.linalg.norm(feature_vector)
        if norm > 0:
            feature_vector = feature_vector / norm
            
        return feature_vector.tolist()

    def scan_image(self, img_path, cache_dir, max_dim=1920):
        """
        Scans a single image, detects faces using RetinaFace multi-scale with CLAHE
        preprocessing, aligns & crops them using similarity transforms, and extracts
        ArcFace INT8 512-dimensional embeddings.
        Returns a list of dictionaries with face metadata.
        """
        if self.detector_session is None or self.recognizer_session is None:
            self.load_models()
            
        img_path = Path(img_path)
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

        # Apply CLAHE preprocessing for better contrast in challenging lighting
        img_enhanced = self._apply_clahe(img)

        # Multi-scale detection: detect at primary scale and a secondary lower scale
        all_faces = []

        # Primary detection at max_dim
        faces_primary = self._detect_faces_at_scale(img_enhanced, max_dim)
        all_faces.extend(faces_primary)

        # Secondary detection at a lower resolution to catch different face sizes
        secondary_dim = int(max_dim * 0.6)
        if max(h, w) > max_dim:
            faces_secondary = self._detect_faces_at_scale(img_enhanced, secondary_dim)
            all_faces.extend(faces_secondary)

        # Apply NMS to remove duplicate detections from multi-scale passes
        if len(all_faces) > 0:
            merged_faces = self._nms_faces(all_faces, iou_threshold=0.4, iom_threshold=0.7)
        else:
            merged_faces = []
            
        results = []
        if merged_faces:
            cache_dir = Path(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            for idx, face_orig in enumerate(merged_faces):
                # Bounding box coordinates in original image
                x, y, width, height = face_orig[0:4].astype(int)
                score = float(face_orig[14])
                
                # Apply high scores threshold
                if score < 0.72:
                    continue
                
                # Align and crop the face using original high-resolution image
                try:
                    aligned_face = self.align_crop_face(img, face_orig)
                    
                    # 1. Filter out cut off/partially obscured faces on the edge of the frame
                    black_pixels = np.all(aligned_face == 0, axis=-1)
                    black_ratio = np.sum(black_pixels) / (112 * 112)
                    if black_ratio > self.MAX_BLACK_RATIO:
                        continue
                        
                    # 2. Filter out extremely blurry faces using Laplacian Variance
                    gray_face = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2GRAY)
                    laplacian_var = cv2.Laplacian(gray_face, cv2.CV_64F).var()
                    if laplacian_var < self.MIN_LAPLACIAN_VAR:
                        continue

                    # 2b. Filter out pixelated/mosaic blurred faces
                    diff_h = np.all(aligned_face[:, 1:] == aligned_face[:, :-1], axis=-1)
                    diff_v = np.all(aligned_face[1:, :] == aligned_face[:-1, :], axis=-1)
                    ratio_flat = (np.sum(diff_h) + np.sum(diff_v)) / (112 * 111 * 2)
                    if ratio_flat > 0.12:
                        continue
                    
                    # Extract 512-d feature representation using ArcFace INT8
                    feature_list = self.extract_embedding(aligned_face)
                    
                except Exception as e:
                    print(f"ArcFace processing error on face {idx} of {img_path.name}: {e}")
                    continue
                
                # Generate unique ID for this face crop
                face_id = str(uuid.uuid4())
                crop_filename = f"{face_id}.jpg"
                crop_path = cache_dir / crop_filename
                
                # Save cropped face thumbnail (112x112 pixels, guaranteed by alignment warp)
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
                    "embedding": feature_list
                })
                
        return results

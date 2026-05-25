import os
import sys
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add current directory to path to import core modules
sys.path.append(str(Path(__file__).parent))

from core.face_processor import FaceProcessor, _init_worker, _process_single_image
from core.clusterer import FaceClusterer
from core.exporter import FaceExporter

app = FastAPI(title="Yearbook Face Sorter API")

# Initialize directories
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR = BASE_DIR / "models"

# Mount cache for cropped images
app.mount("/static/cache", StaticFiles(directory=str(CACHE_DIR)), name="cache")

# Global states
processor = FaceProcessor()
scan_state = {
    "status": "idle",  # "idle", "scanning", "done", "error"
    "total_files": 0,
    "processed_files": 0,
    "current_file": "",
    "faces_found": 0,
    "error_message": "",
}
scan_results = []       # Stores the raw face detections with embeddings
clustered_groups = {}   # Map of cluster_id -> group details
person_names = {}       # Map of cluster_id -> custom person name
custom_assignments = {} # Map of face_id -> target_cluster_id (for manual override)

class ScanRequest(BaseModel):
    source_dir: str
    workers: int = 4

class RenameRequest(BaseModel):
    cluster_id: str
    new_name: str

class MoveRequest(BaseModel):
    face_id: str
    target_cluster_id: str

class ExportRequest(BaseModel):
    export_dir: str
    source_dir: Optional[str] = None
    structure_type: Optional[str] = "flat"
    group_threshold: Optional[int] = 5
    exclude_groups_from_individuals: Optional[bool] = False

# Thread lock for safe scan_state updates from background thread
_scan_lock = threading.Lock()

def run_background_scan(source_path: Path, num_workers: int = 4):
    global scan_state, scan_results, clustered_groups, person_names, custom_assignments
    try:
        # 1. Reset states
        scan_state["status"] = "scanning"
        scan_state["total_files"] = 0
        scan_state["processed_files"] = 0
        scan_state["current_file"] = ""
        scan_state["faces_found"] = 0
        scan_state["error_message"] = ""
        
        scan_results = []
        custom_assignments = {}
        person_names = {}
        
        # 2. Get list of files
        valid_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".arw"}
        image_files = []
        
        # Walk source directory
        for root, _, files in os.walk(source_path):
            # Ignore hidden folders like .venv, cache, etc. relative to source_path
            try:
                rel_parts = Path(root).relative_to(source_path).parts
                if any(part.startswith(".") for part in rel_parts):
                    continue
            except Exception:
                pass
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in valid_extensions:
                    image_files.append(Path(root) / f)
                    
        total = len(image_files)
        scan_state["total_files"] = total
        
        if total == 0:
            scan_state["status"] = "error"
            scan_state["error_message"] = "Không tìm thấy bất kỳ tệp ảnh nào (.jpg, .jpeg, .png, .webp, .bmp, .arw) trong thư mục này."
            return
        
        # Ensure models are downloaded before spawning workers
        scan_state["current_file"] = "Đang kiểm tra và tải các mô hình học máy (YuNet & SFace)..."
        processor.ensure_models()
        
        # Clamp workers to valid range
        max_workers = min(max(1, num_workers), os.cpu_count() or 4)
        
        # 3. Process images in parallel using ProcessPoolExecutor
        cache_dir_str = str(CACHE_DIR)
        models_dir_str = str(MODELS_DIR)
        
        # Build task arguments
        task_args = [(str(img_file), cache_dir_str) for img_file in image_files]
        
        faces_accumulator = []
        processed_count = 0
        
        scan_state["current_file"] = f"Khởi tạo {max_workers} luồng xử lý song song..."
        
        if max_workers == 1:
            # Sequential mode — use the main processor directly (no subprocess overhead)
            processor.load_models()
            for idx, img_file in enumerate(image_files):
                scan_state["current_file"] = img_file.name
                scan_state["processed_files"] = idx + 1
                try:
                    faces = processor.scan_image(img_file, CACHE_DIR)
                    if faces:
                        faces_accumulator.extend(faces)
                        scan_state["faces_found"] += len(faces)
                except Exception as e:
                    print(f"Lỗi khi xử lý ảnh {img_file.name}: {e}")
        else:
            # Parallel mode — each worker process loads its own models via _init_worker
            with ProcessPoolExecutor(
                max_workers=max_workers,
                initializer=_init_worker,
                initargs=(models_dir_str,)
            ) as executor:
                # Submit all tasks and map futures back to filenames
                future_to_filename = {}
                for args in task_args:
                    future = executor.submit(_process_single_image, args)
                    future_to_filename[future] = Path(args[0]).name
                
                # Collect results as they complete (real-time progress)
                for future in as_completed(future_to_filename):
                    processed_count += 1
                    filename = future_to_filename[future]
                    
                    with _scan_lock:
                        scan_state["current_file"] = filename
                        scan_state["processed_files"] = processed_count
                    
                    try:
                        faces = future.result()
                        if faces:
                            faces_accumulator.extend(faces)
                            with _scan_lock:
                                scan_state["faces_found"] += len(faces)
                    except Exception as e:
                        print(f"Lỗi khi xử lý ảnh {filename}: {e}")
        
        scan_results = faces_accumulator
        scan_state["status"] = "done"
        
        # Initial clustering
        run_clustering(eps=1.12)
        
    except Exception as e:
        scan_state["status"] = "error"
        scan_state["error_message"] = f"Lỗi hệ thống trong quá trình quét: {str(e)}"
        print(f"Background scanning critical error: {e}")

def run_clustering(eps: float = 1.12):
    """Internal function to run clustering and merge manual overrides."""
    global scan_results, clustered_groups, person_names, custom_assignments
    
    if not scan_results:
        clustered_groups = {}
        return
        
    # 1. Run raw DBSCAN clustering
    updated_faces, raw_groups = FaceClusterer.cluster_faces(scan_results, eps=eps)
    
    # 2. Re-apply manual move assignments
    # We first collect all faces that were not moved, and those that were moved.
    # Map face_id to their respective face details
    face_map = {face["id"]: face for face in updated_faces}
    
    # If a face was manually assigned, update its cluster_id
    for face_id, target_cluster in custom_assignments.items():
        if face_id in face_map:
            face_map[face_id]["cluster_id"] = target_cluster
            # We don't change the default person_name here, we will merge it below
            
    # 3. Re-group based on final cluster IDs
    final_groups = {}
    for face in face_map.values():
        cluster_id = face["cluster_id"]
        
        # Get appropriate person name
        # If user renamed this cluster, use that name.
        # Otherwise, check if we already have a saved name for this cluster_id.
        # If not, generate a default one.
        if cluster_id not in person_names:
            if "person_unidentified" in cluster_id:
                # Retain or regenerate
                name_num = cluster_id.split("_")[-1]
                person_names[cluster_id] = f"Người chưa biết {name_num}"
            else:
                name_num = str(int(cluster_id.split("_")[-1]) + 1)
                person_names[cluster_id] = f"Nhóm người {name_num}"
                
        person_name = person_names[cluster_id]
        face["person_name"] = person_name
        
        if cluster_id not in final_groups:
            final_groups[cluster_id] = {
                "cluster_id": cluster_id,
                "person_name": person_name,
                "faces": []
            }
        final_groups[cluster_id]["faces"].append(face)
        
    # Sort groups by size (descending)
    sorted_groups = sorted(final_groups.values(), key=lambda g: len(g["faces"]), reverse=True)
    
    # Re-build sorted groups dictionary
    clustered_groups = {g["cluster_id"]: g for g in sorted_groups}

# --- REST API Endpoints ---

@app.post("/api/scan")
def scan_directory(request: ScanRequest, background_tasks: BackgroundTasks):
    source_path = Path(request.source_dir)
    if not source_path.exists() or not source_path.is_dir():
        raise HTTPException(status_code=400, detail="Thư mục nguồn không tồn tại hoặc không phải là thư mục hợp lệ.")
        
    if scan_state["status"] == "scanning":
        return {"status": "scanning", "message": "Quá trình quét đang diễn ra, vui lòng chờ."}
        
    # Start scanning in background
    background_tasks.add_task(run_background_scan, source_path, request.workers)
    return {"status": "started", "message": f"Bắt đầu quét ảnh với {request.workers} luồng xử lý song song."}

@app.get("/api/scan-status")
def get_scan_status():
    return JSONResponse(content=scan_state)

@app.get("/api/cluster")
def get_clusters(eps: float = Query(1.12, description="DBSCAN clustering epsilon parameter")):
    run_clustering(eps=eps)
    return JSONResponse(content=list(clustered_groups.values()))

@app.post("/api/rename")
def rename_person(request: RenameRequest):
    global clustered_groups, person_names
    cluster_id = request.cluster_id
    new_name = request.new_name.strip()
    
    if not new_name:
        raise HTTPException(status_code=400, detail="Tên không được để trống.")
        
    person_names[cluster_id] = new_name
    
    # Update current clustered groups names in-place
    if cluster_id in clustered_groups:
        clustered_groups[cluster_id]["person_name"] = new_name
        for face in clustered_groups[cluster_id]["faces"]:
            face["person_name"] = new_name
            
    return {"status": "success", "message": f"Đã đổi tên nhóm thành '{new_name}'"}

@app.post("/api/move-face")
def move_face_to_group(request: MoveRequest):
    global custom_assignments
    face_id = request.face_id
    target_cluster_id = request.target_cluster_id
    
    # Register manual assignment override
    custom_assignments[face_id] = target_cluster_id
    
    # Re-run grouping (maintaining current eps or default)
    # The frontend will fetch current clusters with `/api/cluster?eps=...` subsequently,
    # but we trigger a default re-cluster here to update internal dictionary
    run_clustering()
    
    return {"status": "success", "message": "Đã chuyển khuôn mặt sang nhóm mới."}

@app.post("/api/choose-directory")
def choose_directory():
    import tkinter as tk
    from tkinter import filedialog
    try:
        root = tk.Tk()
        root.withdraw()  # Hide main window
        root.attributes('-topmost', True)  # Bring dialog to the front
        directory = filedialog.askdirectory(title="Chọn thư mục")
        root.destroy()
        if directory:
            return {"directory": os.path.abspath(directory)}
    except Exception as e:
        print(f"Error selecting folder: {e}")
        raise HTTPException(status_code=500, detail=f"Không thể khởi chạy hộp thoại chọn thư mục: {str(e)}")
    return {"directory": ""}

@app.post("/api/export")
def export_images(request: ExportRequest):
    global clustered_groups
    export_path = Path(request.export_dir)
    
    if not clustered_groups:
        raise HTTPException(status_code=400, detail="Chưa có dữ liệu phân cụm để xuất. Vui lòng quét thư mục ảnh trước.")
        
    try:
        summary = FaceExporter.export_clusters(
            clustered_groups, 
            export_path,
            source_dir=request.source_dir,
            structure_type=request.structure_type,
            group_threshold=request.group_threshold,
            exclude_groups_from_individuals=request.exclude_groups_from_individuals
        )
        return JSONResponse(content=summary)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xuất ảnh: {str(e)}")

@app.post("/api/create-samples")
def create_samples():
    import urllib.request
    
    samples_dir = BASE_DIR / "sample_photos"
    samples_dir.mkdir(parents=True, exist_ok=True)
    
    export_default_dir = BASE_DIR / "output"
    export_default_dir.mkdir(parents=True, exist_ok=True)
    
    # Famous historical figures portraits for testing face clustering
    samples = [
        {
            "name": "barack_obama_1.jpg",
            "url": "https://upload.wikimedia.org/wikipedia/commons/8/8d/President_Barack_Obama.jpg"
        },
        {
            "name": "barack_obama_2.jpg",
            "url": "https://upload.wikimedia.org/wikipedia/commons/e/e9/Official_portrait_of_Barack_Obama%2C_2012.jpg"
        },
        {
            "name": "donald_trump_1.jpg",
            "url": "https://upload.wikimedia.org/wikipedia/commons/5/56/Donald_Trump_official_portrait.jpg"
        },
        {
            "name": "donald_trump_2.jpg",
            "url": "https://upload.wikimedia.org/wikipedia/commons/5/53/Donald_Trump_by_Gage_Skidmore_2017_cropped.jpg"
        },
        {
            "name": "albert_einstein_1.jpg",
            "url": "https://upload.wikimedia.org/wikipedia/commons/3/3e/Einstein_1921_by_F_Schmutzer_-_restoration.jpg"
        },
        {
            "name": "albert_einstein_2.jpg",
            "url": "https://upload.wikimedia.org/wikipedia/commons/d/d3/Albert_Einstein_Head.jpg"
        },
        {
            "name": "ada_lovelace.jpg",
            "url": "https://upload.wikimedia.org/wikipedia/commons/a/a4/Ada_Lovelace_portrait.jpg"
        },
        {
            "name": "marie_curie.jpg",
            "url": "https://upload.wikimedia.org/wikipedia/commons/7/7c/MarieCurie.jpg"
        }
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    
    downloaded = 0
    for s in samples:
        dest_path = samples_dir / s["name"]
        if dest_path.exists() and dest_path.stat().st_size > 10000:
            downloaded += 1
            continue
            
        try:
            req = urllib.request.Request(s["url"], headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response, open(dest_path, 'wb') as out_file:
                out_file.write(response.read())
            downloaded += 1
        except Exception as e:
            print(f"Error downloading sample {s['name']}: {e}")
            
    if downloaded == 0:
        raise HTTPException(status_code=500, detail="Không thể tải xuống bất kỳ ảnh mẫu nào. Vui lòng kiểm tra kết nối mạng của bạn.")
        
    return {
        "status": "success",
        "message": f"Đã chuẩn bị thành công {downloaded}/{len(samples)} ảnh mẫu thử nghiệm tại thư mục 'sample_photos'.",
        "source_dir": str(samples_dir),
        "export_dir": str(export_default_dir)
    }

@app.get("/api/original-photo")
def get_original_photo(path: str):
    photo_path = Path(path)
    if not photo_path.exists():
        raise HTTPException(status_code=404, detail="Ảnh gốc không tồn tại.")
    return FileResponse(str(photo_path))

# Serve HTML/JS/CSS assets
@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        # Create a placeholder if not exists yet
        return HTMLResponse("<html><body><h1>Giao diện đang được khởi tạo...</h1></body></html>")
    return FileResponse(str(index_file))

# Mount static directory for JS/CSS assets
# Note: Mount at /static *after* specific routes to avoid routing conflicts
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

import os
import shutil
import sys
import threading
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed, wait, FIRST_COMPLETED
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add current directory to path to import core modules
sys.path.append(str(Path(__file__).parent))

from core.face_processor import FaceProcessor, _init_worker, _process_single_image
from core.clusterer import FaceClusterer, DEFAULT_EPS
from core.exporter import FaceExporter
from core.face_learning import FaceLearningStore
from core.history import HistoryStore

app = FastAPI(title="Yearbook Face Sorter API")

# Initialize directories
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"
LEARNING_STORE = FaceLearningStore(DATA_DIR / "face_learning.json")
HISTORY_STORE = HistoryStore(DATA_DIR / "history.json")

# Mount cache for cropped images
app.mount("/static/cache", StaticFiles(directory=str(CACHE_DIR)), name="cache")

# Global states
processor = FaceProcessor()
scan_state = {
    "status": "idle",  # "idle", "scanning", "paused", "done", "error"
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
current_cluster_eps = DEFAULT_EPS

# Scan control events
scan_pause_event = threading.Event()
scan_pause_event.set()  # set means running, cleared means paused
scan_stop_event = threading.Event()

class ScanRequest(BaseModel):
    source_dir: str
    workers: int = 4
    detection_model: Optional[str] = "retinaface"
    recognition_model: Optional[str] = "arcface_r50"

class RenameRequest(BaseModel):
    cluster_id: str
    new_name: str

class MoveRequest(BaseModel):
    face_id: str
    target_cluster_id: str

class LearnFeedbackRequest(BaseModel):
    cluster_a: str
    cluster_b: str
    same: Optional[bool] = None
    skipped: bool = False
    similarity: Optional[float] = None

class MergeClustersRequest(BaseModel):
    source_cluster_id: str
    target_cluster_id: str

class ExportRequest(BaseModel):
    export_dir: str
    source_dir: Optional[str] = None
    structure_type: Optional[str] = "flat"
    group_threshold: Optional[int] = 5
    exclude_groups_from_individuals: Optional[bool] = False

# Thread lock for safe scan_state updates from background thread
_scan_lock = threading.Lock()

def run_background_scan(source_path: Path, num_workers: int = 4, detection_model: str = "retinaface", recognition_model: str = "arcface_r50"):
    global scan_state, scan_results, clustered_groups, person_names, custom_assignments, current_cluster_eps, processor
    try:
        # Instantiate/configure the local processor with selected models
        processor = FaceProcessor(
            models_dir=MODELS_DIR,
            detection_model=detection_model,
            recognition_model=recognition_model
        )
        
        # 1. Reset states
        scan_state["status"] = "scanning"
        scan_state["total_files"] = 0
        scan_state["processed_files"] = 0
        scan_state["current_file"] = ""
        scan_state["faces_found"] = 0
        scan_state["error_message"] = ""
        scan_state["optimal_eps"] = None
        scan_state["optimal_sensitivity"] = None
        
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
        scan_state["current_file"] = "Đang kiểm tra và tải các mô hình học máy (RetinaFace & ArcFace)..."
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
                if scan_stop_event.is_set():
                    break
                if not scan_pause_event.is_set():
                    scan_pause_event.wait()
                    if scan_stop_event.is_set():
                        break
                        
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
                initargs=(models_dir_str, detection_model, recognition_model)
            ) as executor:
                # Submit up to max_workers * 2 tasks initially to avoid overfilling worker queues
                pending_futures = {}
                img_idx = 0
                total_imgs = len(image_files)
                
                def submit_next():
                    nonlocal img_idx
                    if img_idx < total_imgs:
                        img_file = image_files[img_idx]
                        args = (str(img_file), cache_dir_str)
                        future = executor.submit(_process_single_image, args)
                        pending_futures[future] = img_file.name
                        img_idx += 1
                
                # Populate initial batch
                for _ in range(min(total_imgs, max_workers * 2)):
                    submit_next()
                
                while pending_futures:
                    if scan_stop_event.is_set():
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                        
                    # Check for pause state
                    if not scan_pause_event.is_set():
                        scan_pause_event.wait()
                        if scan_stop_event.is_set():
                            executor.shutdown(wait=False, cancel_futures=True)
                            break
                    
                    # Top up queue if we have room and are not paused/stopped
                    while len(pending_futures) < max_workers * 2 and img_idx < total_imgs and not scan_stop_event.is_set() and scan_pause_event.is_set():
                        submit_next()
                        
                    # Wait for at least one future to complete
                    done, _ = wait(
                        list(pending_futures.keys()),
                        return_when=FIRST_COMPLETED
                    )
                    
                    for future in done:
                        if future in pending_futures:
                            processed_count += 1
                            filename = pending_futures.pop(future)
                            
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
        
        # Auto-tune DBSCAN eps for ArcFace embeddings, then cluster
        scan_state["current_file"] = "Đang tối ưu phân nhóm khuôn mặt..."
        if len(scan_results) >= 2:
            current_cluster_eps = FaceClusterer.auto_tune_epsilon(
                scan_results,
                eps_offset=LEARNING_STORE.get_eps_offset(),
            )
        else:
            current_cluster_eps = DEFAULT_EPS
        scan_state["optimal_eps"] = round(current_cluster_eps, 3)
        scan_state["optimal_sensitivity"] = round(1.0 - current_cluster_eps, 2)
        run_clustering(eps=current_cluster_eps)
        
        HISTORY_STORE.add_event("scan", {
            "source_dir": str(source_path),
            "files_count": total,
            "faces_found": len(scan_results),
            "det_model": detection_model,
            "rec_model": recognition_model
        })
        
    except Exception as e:
        scan_state["status"] = "error"
        scan_state["error_message"] = f"Lỗi hệ thống trong quá trình quét: {str(e)}"
        print(f"Background scanning critical error: {e}")

def merge_clusters(source_cluster_id: str, target_cluster_id: str):
    """Move all faces from source cluster into target (must-link learning)."""
    global custom_assignments, person_names

    if source_cluster_id == target_cluster_id:
        return
    if source_cluster_id not in clustered_groups or target_cluster_id not in clustered_groups:
        raise HTTPException(status_code=400, detail="Một trong hai nhóm không tồn tại.")

    # Keep the larger group as target
    src_group = clustered_groups[source_cluster_id]
    tgt_group = clustered_groups[target_cluster_id]
    if len(src_group["faces"]) > len(tgt_group["faces"]):
        source_cluster_id, target_cluster_id = target_cluster_id, source_cluster_id
        src_group, tgt_group = tgt_group, src_group

    for face in src_group["faces"]:
        custom_assignments[face["id"]] = target_cluster_id

    target_name = person_names.get(target_cluster_id) or tgt_group.get("person_name")
    if target_name:
        person_names[target_cluster_id] = target_name

    if target_name and not target_name.startswith("Nhóm người") and not target_name.startswith(
        "Người chưa"
    ):
        for face in tgt_group.get("faces", []):
            raw = next((f for f in scan_results if f["id"] == face["id"]), None)
            if raw and raw.get("embedding"):
                LEARNING_STORE.add_person_prototype(target_name, raw["embedding"])
                break


def apply_learned_must_links(face_map: dict):
    """Union-find merge of clusters the user confirmed as same person."""
    components = LEARNING_STORE.get_must_link_components()
    if not components:
        return

    for face in face_map.values():
        cid = face["cluster_id"]
        if cid in components:
            face["cluster_id"] = components[cid]


def run_clustering(eps: float = None):
    """Internal function to run clustering and merge manual overrides."""
    global scan_results, clustered_groups, person_names, custom_assignments, current_cluster_eps
    if eps is None:
        eps = current_cluster_eps
    else:
        current_cluster_eps = eps
    
    if not scan_results:
        clustered_groups = {}
        return
        
    # 1. Run raw DBSCAN clustering
    updated_faces, raw_groups = FaceClusterer.cluster_faces(scan_results, eps=eps)
    
    # 2. Re-apply manual move assignments
    face_map = {face["id"]: face for face in updated_faces}
    
    for face_id, target_cluster in custom_assignments.items():
        if face_id in face_map:
            face_map[face_id]["cluster_id"] = target_cluster

    # 2b. Apply persisted must-link pairs from learning
    apply_learned_must_links(face_map)
            
    # 3. Re-group based on final person names (to merge groups with the exact same name)
    name_to_group = {}
    
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
        
        if person_name not in name_to_group:
            name_to_group[person_name] = {
                "cluster_id": cluster_id,  # Representative cluster_id (using the first encountered)
                "person_name": person_name,
                "faces": []
            }
        name_to_group[person_name]["faces"].append(face)
        
    # Re-map all faces in the merged groups to have the representative cluster_id
    # so that manual overrides and overrides state remain consistent!
    for group in name_to_group.values():
        rep_cluster_id = group["cluster_id"]
        for face in group["faces"]:
            face["cluster_id"] = rep_cluster_id
            
    # Sort groups by size (descending)
    sorted_groups = sorted(name_to_group.values(), key=lambda g: len(g["faces"]), reverse=True)
    
    # Re-build sorted groups dictionary
    clustered_groups = {g["cluster_id"]: g for g in sorted_groups}

# --- REST API Endpoints ---

@app.post("/api/scan")
def scan_directory(request: ScanRequest, background_tasks: BackgroundTasks):
    source_path = Path(request.source_dir)
    if not source_path.exists() or not source_path.is_dir():
        raise HTTPException(status_code=400, detail="Thư mục nguồn không tồn tại hoặc không phải là thư mục hợp lệ.")
        
    if scan_state["status"] in ("scanning", "paused"):
        return {"status": "scanning", "message": "Quá trình quét đang diễn ra, vui lòng chờ."}
        
    # Reset control events
    scan_pause_event.set()
    scan_stop_event.clear()
    
    # Start scanning in background
    background_tasks.add_task(
        run_background_scan, 
        source_path, 
        request.workers, 
        request.detection_model, 
        request.recognition_model
    )
    return {"status": "started", "message": f"Bắt đầu quét ảnh với {request.workers} luồng xử lý song song."}

@app.post("/api/scan/pause")
def pause_scan():
    if scan_state["status"] != "scanning":
        raise HTTPException(status_code=400, detail="Tiến trình không ở trạng thái đang quét.")
    scan_pause_event.clear()
    scan_state["status"] = "paused"
    return {"status": "success", "message": "Đã gửi yêu cầu tạm dừng tiến trình."}

@app.post("/api/scan/resume")
def resume_scan():
    if scan_state["status"] != "paused":
        raise HTTPException(status_code=400, detail="Tiến trình không ở trạng thái tạm dừng.")
    scan_pause_event.set()
    scan_state["status"] = "scanning"
    return {"status": "success", "message": "Đã gửi yêu cầu tiếp tục tiến trình."}

@app.post("/api/scan/stop")
def stop_scan():
    if scan_state["status"] not in ("scanning", "paused"):
        raise HTTPException(status_code=400, detail="Không có tiến trình quét nào đang chạy để dừng.")
    scan_stop_event.set()
    scan_pause_event.set() # Resume if paused so it can check stop status and exit
    return {"status": "success", "message": "Đã gửi yêu cầu kết thúc tiến trình."}

@app.get("/api/scan-status")
def get_scan_status():
    return JSONResponse(content=scan_state)

@app.get("/api/system-info")
def get_system_info():
    import os
    return {"cpu_count": os.cpu_count() or 4}

@app.get("/api/cluster")
def get_clusters(
    eps: Optional[float] = Query(None, description="DBSCAN epsilon; omit to use last auto-tuned value"),
):
    run_clustering(eps=eps)
    return JSONResponse(content=list(clustered_groups.values()))

@app.post("/api/auto-tune")
def auto_tune_clustering():
    global scan_results, current_cluster_eps
    if not scan_results:
        raise HTTPException(status_code=400, detail="Chưa có dữ liệu ảnh quét để tối ưu hóa.")
    
    current_cluster_eps = FaceClusterer.auto_tune_epsilon(
        scan_results,
        eps_offset=LEARNING_STORE.get_eps_offset(),
    )
    optimal_eps = round(current_cluster_eps, 3)
    optimal_sensitivity = float(round(1.0 - current_cluster_eps, 2))
    
    run_clustering(eps=current_cluster_eps)
    
    return {
        "status": "success",
        "optimal_eps": optimal_eps,
        "optimal_sensitivity": optimal_sensitivity,
        "message": f"Đã tìm thấy độ nhạy tối ưu: {optimal_sensitivity} (eps: {optimal_eps})",
    }

@app.post("/api/rename")
def rename_person(request: RenameRequest):
    global clustered_groups, person_names
    cluster_id = request.cluster_id
    new_name = request.new_name.strip()
    
    if not new_name:
        raise HTTPException(status_code=400, detail="Tên không được để trống.")
        
    old_name = person_names.get(cluster_id) or (clustered_groups[cluster_id].get("person_name") if cluster_id in clustered_groups else "")
    person_names[cluster_id] = new_name

    if cluster_id in clustered_groups:
        for face in clustered_groups[cluster_id].get("faces", []):
            raw = next((f for f in scan_results if f["id"] == face["id"]), None)
            if raw and raw.get("embedding"):
                LEARNING_STORE.add_person_prototype(new_name, raw["embedding"])
                break
    
    run_clustering()
    
    HISTORY_STORE.add_event("rename", {
        "cluster_id": cluster_id,
        "old_name": old_name,
        "new_name": new_name
    })
            
    return {"status": "success", "message": f"Đã đổi tên nhóm thành '{new_name}'"}

@app.get("/api/learn/suggestions")
def learn_suggestions(limit: int = Query(8, ge=1, le=20)):
    if not scan_results or not clustered_groups:
        return {"suggestions": [], "stats": LEARNING_STORE.get_stats()}
    suggestions = LEARNING_STORE.suggest_pairs(scan_results, clustered_groups, limit=limit)
    return {
        "suggestions": suggestions,
        "stats": LEARNING_STORE.get_stats(),
        "name_hints": LEARNING_STORE.prototype_hints_for_clusters(scan_results, clustered_groups),
    }


@app.get("/api/learn/stats")
def learn_stats():
    return LEARNING_STORE.get_stats()


def _learn_feedback_response(merged: bool, stale: bool = False, message: str = ""):
    suggestions = LEARNING_STORE.suggest_pairs(scan_results, clustered_groups, limit=12)
    return {
        "status": "stale" if stale else "success",
        "merged": merged,
        "stale": stale,
        "message": message,
        "optimal_eps": round(current_cluster_eps, 3),
        "optimal_sensitivity": round(1.0 - current_cluster_eps, 2),
        "stats": LEARNING_STORE.get_stats(),
        "remaining_suggestions": len(suggestions),
        "suggestions": suggestions,
        "groups": list(clustered_groups.values()),
    }


@app.post("/api/learn/feedback")
def learn_feedback(request: LearnFeedbackRequest):
    global current_cluster_eps

    if request.cluster_a == request.cluster_b:
        raise HTTPException(status_code=400, detail="Hai nhóm phải khác nhau.")

    a_exists = request.cluster_a in clustered_groups
    b_exists = request.cluster_b in clustered_groups

    centroids, _ = FaceLearningStore.build_cluster_centroids(scan_results, clustered_groups)
    sim = float(request.similarity) if request.similarity is not None else 0.5
    if request.cluster_a in centroids and request.cluster_b in centroids:
        sim = float(np.dot(centroids[request.cluster_a], centroids[request.cluster_b]))

    LEARNING_STORE.record_feedback(
        request.cluster_a,
        request.cluster_b,
        same=request.same,
        similarity=sim,
        skipped=request.skipped,
    )

    name_a = person_names.get(request.cluster_a) or (clustered_groups[request.cluster_a].get("person_name") if request.cluster_a in clustered_groups else "")
    name_b = person_names.get(request.cluster_b) or (clustered_groups[request.cluster_b].get("person_name") if request.cluster_b in clustered_groups else "")
    HISTORY_STORE.add_event("learn", {
        "cluster_a": request.cluster_a,
        "cluster_b": request.cluster_b,
        "name_a": name_a,
        "name_b": name_b,
        "same": request.same,
        "skipped": request.skipped,
        "similarity": sim
    })

    merged = False
    stale = not (a_exists and b_exists)

    if request.same is True and not request.skipped and a_exists and b_exists:
        merge_clusters(request.cluster_a, request.cluster_b)
        merged = True

    if len(scan_results) >= 2:
        current_cluster_eps = FaceClusterer.auto_tune_epsilon(
            scan_results,
            eps_offset=LEARNING_STORE.get_eps_offset(),
            verbose=False,
        )
    run_clustering(eps=current_cluster_eps)

    if stale:
        return _learn_feedback_response(
            merged=False,
            stale=True,
            message="Một hoặc hai nhóm đã được gộp/thay đổi. Đã ghi nhận phản hồi và tải câu hỏi mới.",
        )

    return _learn_feedback_response(merged=merged)


@app.post("/api/learn/reset")
def learn_reset_all():
    """Xóa toàn bộ dữ liệu AI đã học (file data/face_learning.json)."""
    global current_cluster_eps

    LEARNING_STORE.clear_all()

    if scan_results and len(scan_results) >= 2:
        current_cluster_eps = FaceClusterer.auto_tune_epsilon(
            scan_results,
            eps_offset=0.0,
            verbose=False,
        )
        run_clustering(eps=current_cluster_eps)
    elif scan_results:
        run_clustering()

    return {
        "status": "success",
        "message": "Đã xóa toàn bộ dữ liệu AI đã học.",
        "stats": LEARNING_STORE.get_stats(),
        "groups": list(clustered_groups.values()),
        "optimal_eps": round(current_cluster_eps, 3),
        "optimal_sensitivity": round(1.0 - current_cluster_eps, 2),
    }


@app.post("/api/merge-clusters")
def api_merge_clusters(request: MergeClustersRequest):
    src_name = person_names.get(request.source_cluster_id) or (clustered_groups[request.source_cluster_id].get("person_name") if request.source_cluster_id in clustered_groups else "")
    tgt_name = person_names.get(request.target_cluster_id) or (clustered_groups[request.target_cluster_id].get("person_name") if request.target_cluster_id in clustered_groups else "")
    
    merge_clusters(request.source_cluster_id, request.target_cluster_id)
    run_clustering()
    
    HISTORY_STORE.add_event("merge", {
        "source_cluster_id": request.source_cluster_id,
        "target_cluster_id": request.target_cluster_id,
        "source_name": src_name,
        "target_name": tgt_name
    })
    return {
        "status": "success",
        "groups": list(clustered_groups.values()),
    }


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
    
    target_name = person_names.get(target_cluster_id) or (clustered_groups[target_cluster_id].get("person_name") if target_cluster_id in clustered_groups else "")
    HISTORY_STORE.add_event("move", {
        "face_id": face_id,
        "target_cluster_id": target_cluster_id,
        "target_name": target_name
    })
    
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

def _cache_dir_stats():
    """Return (file_count, total_bytes) for face crop cache."""
    if not CACHE_DIR.exists():
        return 0, 0
    files = [p for p in CACHE_DIR.iterdir() if p.is_file()]
    total_bytes = sum(p.stat().st_size for p in files)
    return len(files), total_bytes


def clear_face_cache_dir():
    """Delete all cropped face JPEGs in cache/. Returns (files_deleted, bytes_freed)."""
    files_deleted, bytes_freed = _cache_dir_stats()
    try:
        if CACHE_DIR.exists():
            shutil.rmtree(str(CACHE_DIR))
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Không thể xóa cache: {e}") from e
    return files_deleted, bytes_freed


def _invalidate_crop_references():
    """Clear crop URLs in memory after cache files are removed."""
    for group in clustered_groups.values():
        for face in group.get("faces", []):
            face["crop_image"] = ""
    for face in scan_results:
        face.pop("crop_path", None)
        face["crop_image"] = ""


@app.get("/api/cache-info")
def get_cache_info():
    files_deleted, total_bytes = _cache_dir_stats()
    return {
        "file_count": files_deleted,
        "size_bytes": total_bytes,
        "size_mb": round(total_bytes / (1024 * 1024), 2),
    }


@app.post("/api/clear-cache")
def clear_cache():
    if scan_state["status"] in ("scanning", "paused"):
        raise HTTPException(
            status_code=400,
            detail="Không thể xóa cache khi đang quét. Hãy dừng hoặc chờ quét xong.",
        )

    files_deleted, bytes_freed = clear_face_cache_dir()
    had_session = bool(scan_results or clustered_groups)
    if had_session:
        _invalidate_crop_references()

    size_mb = round(bytes_freed / (1024 * 1024), 2)
    return {
        "status": "success",
        "files_deleted": files_deleted,
        "bytes_freed": bytes_freed,
        "size_mb": size_mb,
        "had_session": had_session,
        "message": (
            f"Đã xóa {files_deleted} ảnh crop ({size_mb} MB)."
            + (" Quét lại để tạo thumbnail mới." if had_session else "")
        ),
    }


@app.post("/api/reset")
def reset_application():
    global scan_results, clustered_groups, person_names, custom_assignments, scan_state
    
    # 1. Stop scanning if active
    if scan_state["status"] in ("scanning", "paused"):
        scan_stop_event.set()
        scan_pause_event.set()
        
    # 2. Clear memory variables
    scan_results.clear()
    clustered_groups.clear()
    person_names.clear()
    custom_assignments.clear()
    
    # 3. Reset scan_state
    scan_state["status"] = "idle"
    scan_state["total_files"] = 0
    scan_state["processed_files"] = 0
    scan_state["current_file"] = ""
    scan_state["faces_found"] = 0
    scan_state["error_message"] = ""
    scan_state["optimal_eps"] = None
    scan_state["optimal_sensitivity"] = None
    
    # 4. Clear cache directory contents
    try:
        clear_face_cache_dir()
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error clearing cache directory: {e}")
        
    return {"status": "success", "message": "Đã xóa toàn bộ dữ liệu hiện tại và đưa hệ thống về trạng thái ban đầu."}

@app.get("/api/original-photo")
def get_original_photo(path: str):
    photo_path = Path(path)
    if not photo_path.exists():
        raise HTTPException(status_code=404, detail="Ảnh gốc không tồn tại.")
    return FileResponse(str(photo_path))

@app.get("/api/history")
def get_history():
    return HISTORY_STORE.get_all_events()

@app.post("/api/history/clear")
def clear_history():
    HISTORY_STORE.clear_history()
    return {"status": "success", "message": "Đã xoá toàn bộ lịch sử hoạt động."}

@app.post("/api/history/delete/{event_id}")
def delete_history_event(event_id: int):
    success = HISTORY_STORE.delete_event(event_id)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự kiện lịch sử.")
    return {"status": "success", "message": "Đã xoá sự kiện lịch sử thành công."}

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

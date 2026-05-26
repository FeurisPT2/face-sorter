# instruction.md — Yearbook Face Sorter

Tài liệu này dành cho **AI agents** (và dev mới) cần hiểu nhanh dự án, sửa đúng chỗ, và tiếp tục phát triển mà không bị README cũ gây nhầm.

---

## 1. Mục tiêu dự án

**Yearbook Face Sorter** là ứng dụng web local (FastAPI + vanilla JS) để:

1. Quét thư mục ảnh kỷ yếu / sự kiện
2. Phát hiện khuôn mặt, trích embedding, gom cụm theo người (DBSCAN)
3. Cho phép đặt tên, chỉnh nhóm thủ công, **học từ phản hồi** (kiểu Google Photos)
4. Xuất ảnh gốc vào thư mục theo từng người + tách ảnh tập thể

Ngôn ngữ UI: **tiếng Việt**. Code comment/doc: hỗn hợp Vi/En.

---

## 2. Cảnh báo quan trọng — README vs code thực tế

| Tài liệu | Ghi | Thực tế trong code |
|----------|-----|-------------------|
| `README.md`, `README_VI.md`, `PROJECT_DETAILS.md` | YuNet + SFace (128-D), OpenCV DNN | **RetinaFace MobileNet 0.25** + **ArcFace ResNet50** (`w600k_r50.onnx`), **ONNX Runtime** |
| `app.py` message khi tải model | "YuNet & SFace" | Nên sửa thành RetinaFace & ArcFace khi đụng UI/backend message |
| `core/clusterer.py` docstring cũ | "128-d SFace" | Embedding **512-D** ArcFace |

**Luôn đọc `core/face_processor.py` và `core/clusterer.py` làm nguồn sự thật về ML.**

---

## 3. Chạy dự án

```bash
cd yearbook-face-sorter
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install --upgrade pip
pip install fastapi uvicorn opencv-python numpy scikit-learn pydantic onnxruntime

python -m uvicorn app:app --reload --port 8000
# Mở http://localhost:8000
```

**Kiểm thử pipeline ML (không cần server):**

```bash
python test_pipeline.py
# Cần có sample_photos/ (tạo qua nút "Tạo ảnh mẫu" trên UI hoặc POST /api/create-samples)
```

**Thư mục runtime (thường gitignore):**

| Path | Mục đích |
|------|----------|
| `cache/` | Crop khuôn mặt 112×112 phục vụ UI (`/static/cache/...`) |
| `data/face_learning.json` | Phản hồi học (must-link, cannot-link, eps_offset, prototypes) |
| `output/` | Thư mục xuất mặc định gợi ý |
| `sample_photos/` | Ảnh mẫu tải từ Wikipedia |
| `models/` | ONNX weights (tự tải lần đầu) |

---

## 4. Kiến trúc tổng quan

```mermaid
flowchart TB
    subgraph UI["static/"]
        HTML[index.html]
        JS[app.js]
        CSS[styles.css]
    end

    subgraph API["app.py — FastAPI"]
        Scan[/api/scan]
        Cluster[/api/cluster]
        Learn[/api/learn/*]
        Export[/api/export]
    end

    subgraph Core["core/"]
        FP[face_processor.py\nRetinaFace + ArcFace]
        CL[clusterer.py\nDBSCAN + auto-tune]
        FL[face_learning.py\npersistent feedback]
        EX[exporter.py]
    end

    HTML --> JS
    JS --> API
    Scan --> FP
    Scan --> CL
    Cluster --> CL
    Learn --> FL
    Learn --> CL
    Export --> EX
    FL --> data[(data/face_learning.json)]
    FP --> models[(models/*.onnx)]
    FP --> cache[(cache/)]
```

---

## 5. Cấu trúc thư mục

```text
yearbook-face-sorter/
├── app.py                 # FastAPI server, global state, REST API
├── instruction.md         # File này
├── README.md              # User docs (một phần lỗi thời — xem §2)
├── Design.md              # Quy tắc UI Dark Glassmorphism cho agent frontend
├── test_pipeline.py       # Smoke test RetinaFace + ArcFace
├── core/
│   ├── face_processor.py  # Detection, alignment, 512-D embeddings
│   ├── clusterer.py       # DBSCAN, FCQS v2 auto-tune eps
│   ├── face_learning.py   # Google Photos–style learning store
│   └── exporter.py        # Copy ảnh gốc ra cấu trúc thư mục
├── static/
│   ├── index.html
│   ├── app.js             # Toàn bộ logic UI (~1700 dòng)
│   └── styles.css
├── models/                # ONNX (auto-download)
│   ├── retinaface_mv1_0.25.onnx
│   └── w600k_r50.onnx
├── data/                  # Học máy phản hồi người dùng
└── cache/                 # Face crops
```

---

## 6. Pipeline xử lý ảnh

### 6.1 Quét (`FaceProcessor.scan_image`)

1. Đọc ảnh (jpg/png/webp/bmp/**arw** qua `rawpy`)
2. **CLAHE** trên kênh L (LAB) — cải thiện ảnh kỷ yếu tối/sáng
3. **RetinaFace** multi-scale (primary + ~60% scale), NMS IoU/IoM
4. Lọc: score ≥ 0.72, Laplacian variance ≥ 75, tỷ lệ pixel đen ≤ 10%
5. **Căn mặt** 112×112 (5 landmark → affine → template ArcFace)
6. **ArcFace** → vector 512-D, L2-normalize
7. Lưu crop vào `cache/{uuid}.jpg`, append vào `scan_results`

**Song song:** `ProcessPoolExecutor` + `_init_worker` — mỗi worker load model một lần (`face_processor.py`).

### 6.2 Phân cụm (`FaceClusterer` + `run_clustering`)

1. DBSCAN `metric='cosine'`, `eps` ≈ 0.26–0.58, `min_samples=2`
2. Noise DBSCAN (`-1`) → mỗi mặt một cụm `person_unidentified_N`
3. Đánh dấu `is_suspicious` nếu similarity với centroid cụm < ngưỡng thích ứng
4. **`run_clustering` trong `app.py`** (thứ tự quan trọng):
   - DBSCAN
   - Áp `custom_assignments` (kéo thả / move-face)
   - Áp **must-link** từ `FaceLearningStore`
   - Gộp theo **cùng `person_name`** (rename trùng tên → một nhóm)

### 6.3 Auto-tune eps (sau mỗi lần quét)

- `FaceClusterer.auto_tune_epsilon()` — k-NN knee + lưới eps + fine search + **FCQS v2**
- Cộng `LEARNING_STORE.get_eps_offset()` từ phản hồi người dùng
- Lưu `scan_state.optimal_eps`, `optimal_sensitivity = 1 - eps`
- Frontend đồng bộ slider **Độ nhạy**

**Quan hệ UI:** `eps = 1.0 - sensitivity` (slider tăng = phân nhóm chặt hơn = eps nhỏ hơn).

---

## 7. Hệ thống học (`core/face_learning.py`)

Giống **Google Photos**: hỏi hai nhóm có cùng người không → lưu → tối ưu lần sau.

### Dữ liệu `data/face_learning.json`

```json
{
  "must_link": ["clusterA::clusterB"],
  "cannot_link": ["..."],
  "dismissed": ["..."],
  "feedback": [{ "pair", "same", "similarity", "skipped", "ts" }],
  "eps_offset": 0.0,
  "person_prototypes": [{ "name", "embedding", "updated_at" }]
}
```

### Gợi ý cặp hỏi

- Centroid cosine similarity giữa hai cụm ∈ **[0.46, 0.72]** (vùng xám)
- Loại trừ: must-link, cannot-link, dismissed
- Ưu tiên cặp “borderline” + nhóm nhỏ (hay bị tách đôi)

### Khi user trả lời `POST /api/learn/feedback`

| Trả lời | Hành vi |
|---------|---------|
| Cùng người | `merge_clusters` → `custom_assignments`, lưu must-link, prototype nếu có tên |
| Khác người | cannot-link |
| Bỏ qua | dismissed |
| (mọi case) | Cập nhật `eps_offset`, chạy lại auto-tune + `run_clustering` |

**UI:** modal `#learn-modal`, nút sidebar `#btn-learn`, sau quét có `confirm()` mời học.

---

## 8. Trạng thái global trong `app.py`

Toàn bộ state **in-memory** (mất khi restart server, trừ `data/face_learning.json`):

| Biến | Ý nghĩa |
|------|---------|
| `scan_results` | List face dict **có `embedding`** (nguồn cho cluster & learn) |
| `clustered_groups` | `cluster_id` → `{ person_name, faces[] }` gửi UI (không có embedding) |
| `person_names` | `cluster_id` → tên hiển thị |
| `custom_assignments` | `face_id` → `target_cluster_id` (override thủ công) |
| `current_cluster_eps` | eps DBSCAN hiện tại |
| `scan_state` | Tiến trình quét + `optimal_sensitivity` khi xong |

**Không có database.** Reset: `POST /api/reset` (xóa cache, clear state).

---

## 9. REST API (đầy đủ)

| Method | Path | Mô tả |
|--------|------|--------|
| `GET` | `/` | `index.html` |
| `POST` | `/api/scan` | `{ source_dir, workers }` — quét nền |
| `GET` | `/api/scan-status` | Trạng thái + `optimal_sensitivity` khi done |
| `POST` | `/api/scan/pause` \| `/resume` \| `/stop` | Điều khiển quét |
| `GET` | `/api/cluster?eps=` | Chạy lại cluster; bỏ `eps` → dùng `current_cluster_eps` |
| `POST` | `/api/auto-tune` | Tối ưu eps + cluster lại |
| `POST` | `/api/rename` | `{ cluster_id, new_name }` — gộp nhóm trùng tên + prototype |
| `POST` | `/api/move-face` | `{ face_id, target_cluster_id }` |
| `POST` | `/api/merge-clusters` | Gộp hai cụm |
| `GET` | `/api/learn/suggestions` | Cặp nhóm cần hỏi |
| `GET` | `/api/learn/stats` | Thống kê học |
| `POST` | `/api/learn/feedback` | Phản hồi học |
| `POST` | `/api/export` | Xuất thư mục |
| `POST` | `/api/create-samples` | Tải ảnh mẫu Wikipedia |
| `POST` | `/api/reset` | Xóa session |
| `POST` | `/api/choose-directory` | Tkinter folder picker (cần display) |
| `GET` | `/api/original-photo?path=` | Ảnh gốc cho lightbox |
| `GET` | `/api/system-info` | `cpu_count` |

---

## 10. Frontend (`static/app.js`)

### State chính (`state` object)

- `clusteredGroups`, `sensitivity`, `workers`
- Wizard đặt tên: `wizardGroups`, `wizardIndex`
- Học: `learnQueue`, `learnIndex`, `learnActive`
- Khay kéo-thả: `trayFaces`

### Luồng sau quét

1. `pollScanStatus` → `status === 'done'`
2. Áp `optimal_sensitivity` từ server
3. `fetchClusters` → `promptLearningAfterScan` → (tuỳ chọn) `promptNamingWizardAfterScan`

### Quy ước UI

- Panel sidebar có class `disabled-before-scan` cho đến khi quét xong
- Thiết kế: xem **`Design.md`** (Dark Glassmorphism, sidebar 380px, visualizers)
- Debounce cluster slider 200ms

**Khi sửa UI:** giữ pattern toast `#toast-container`, modal `.modal.hidden`, không phá visualizer sensitivity/export tree.

---

## 11. Xuất ảnh (`core/exporter.py`)

- `group_threshold`: ảnh có ≥ N mặt → thư mục `Ảnh tập thể`
- `exclude_groups_from_individuals`: không copy ảnh tập thể vào folder từng người
- `structure_type`: `flat` \| `person_first` \| `subdir_first`

---

## 12. Hướng dẫn cho agent tiếp tục công việc

### Đọc file theo task

| Task | Đọc trước |
|------|-----------|
| Sửa ML / độ chính xác | `core/face_processor.py`, `core/clusterer.py` |
| Sửa học / gợi ý cặp | `core/face_learning.py`, `app.py` learn endpoints |
| Sửa API / state | `app.py` (`run_clustering`, `run_background_scan`) |
| Sửa UI / UX | `static/app.js`, `static/index.html`, `Design.md`, `styles.css` |
| Sửa xuất file | `core/exporter.py` |

### Nguyên tắc khi sửa code

1. **Giữ diff nhỏ** — không refactor lan man không liên quan task.
2. **Không commit** trừ khi user yêu cầu.
3. **`scan_results` giữ embedding**; response UI/API cluster **xóa embedding** trong `cluster_faces` (đỡ payload nặng).
4. Mọi thay đổi `eps` / học → gọi lại `run_clustering` hoặc document rõ side effect.
5. Cập nhật **README** nếu đổi model/stack; cập nhật **`instruction.md`** nếu đổi kiến trúc/API học.
6. Message UI tiếng Việt, lỗi rõ ràng (`HTTPException(detail=...)`).

### Việc thường được yêu cầu tiếp theo

- [ ] Đồng bộ README/PROJECT_DETAILS với RetinaFace + ArcFace
- [ ] Persist `person_names` / session theo `source_dir` (SQLite hoặc JSON)
- [ ] Gợi ý tên từ `person_prototypes` hiển thị trên card nhóm
- [ ] GPU EP cho ONNX (`CUDAExecutionProvider`)
- [ ] Unit test cho `auto_tune_epsilon` và `FaceLearningStore`
- [ ] Đóng gói PyInstaller / Docker

### Không nên làm (trừ khi được yêu cầu)

- Chuyển full PyTorch runtime chỉ để “mạnh hơn” — đã có ONNX từ cùng ecosystem
- Thay DBSCAN bằng HDBSCAN mà không benchmark trên ảnh kỷ yếu thật
- Commit `data/`, `cache/`, `models/` (models có thể lớn; đã auto-download)

---

## 13. Phụ thuộc Python

Không có `requirements.txt` chính thức; README liệt kê:

`fastapi`, `uvicorn`, `opencv-python`, `numpy`, `scikit-learn`, `pydantic`, **`onnxruntime`**

Tùy chọn: `rawpy` (ảnh ARW).

---

## 14. Liên hệ tài liệu khác

| File | Dùng khi |
|------|----------|
| `instruction.md` | Onboarding agent, kiến trúc thật |
| `README.md` / `README_VI.md` | End-user, cài đặt cơ bản |
| `Design.md` | Chuẩn UI cho agent frontend |
| `PROJECT_DETAILS.md` | Chi tiết cũ — **kiểm tra lại với §2** |

---

*Cập nhật lần cuối: phản ánh RetinaFace + ArcFace, FCQS v2 auto-tune, và hệ thống học Google Photos–style (`face_learning.py`).*

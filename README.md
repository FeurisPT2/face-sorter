# 🎓 Face Sorter (Intelligent AI-Powered Yearbook & Photo Classifier)

🌐 [Đọc bản tiếng Việt tại đây](./README_VI.md)

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-5.0+-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org/)
[![UI Style](https://img.shields.io/badge/UI--Style-Dark_Glassmorphism-purple?style=for-the-badge)](#)

**Face Sorter** is a modern, high-performance web application designed to automatically detect, recognize, and organize faces from hundreds of collective photos (e.g. school yearbooks, graduation photos, corporate events) into structured individual directories. The user interface features an exceptionally premium **Dark Glassmorphism** aesthetic, offering an ultra-smooth, responsive, and visually stunning interactive experience.

---

## ✨ Features

### 🧠 1. State-of-the-Art Face Recognition AI
- **Face Detection (Detection)**:
  - **RetinaFace (High Accuracy)**: Powered by ONNX Runtime, offering outstanding precision and robust detection in tricky angles and difficult lighting conditions.
  - **YuNet (Super Fast & Light)**: Built-in OpenCV wrapper, highly efficient and lightweight for quick scans.
- **Feature Extraction & Identification (Recognition)**:
  - **ArcFace ResNet50 (Balanced)**: 512-dimensional deep embedding representation with excellent balance between speed and precision.
  - **ArcFace ResNet100 (Maximum Precision)**: A heavier 512-D deep architecture offering premium, state-of-the-art accuracy.
  - **SFace (Super Fast & Light)**: 128-dimensional OpenCV model, optimized for low memory usage and lightning-fast comparisons.
- **Automatic Clustering**: Powered by the **DBSCAN** density-based algorithm, which automatically groups highly similar faces into distinct clusters (individuals) without requiring you to pre-define the number of people.

### 📜 2. System Activity History Timeline
- **Operations Log**: Keeps track of scan parameters, group renames, drag-and-drop face movements, merges, and machine learning feedback.
- **Persistence**: Automatically saved to a local database (`data/history.json`).
- **Timelined Feed**: Beautifully structured UI timeline feed showing styled event entries with full action details, color highlights, and timestamps.
- **Dynamic Control**: Clear the system history safely directly from the dashboard controls.

### 🪄 2. Interactive Naming Wizard
*A highly optimized step-by-step workflow designed for fast and intuitive human-in-the-loop naming.*
- **Automatic Launch**: The app prompts you to launch the wizard immediately after scanning is complete.
- **Intelligent Split View**:
  - *Left Column*: Shows a large portrait avatar of the current group and a clean text input box which is automatically focused and pre-selected so you can start typing immediately.
  - *Right Column*: Shows a gallery of all other face crops grouped in this cluster for visual cross-referencing, ensuring 100% correct identification.
- **Keyboard Optimization**: Simply type the name and press <kbd>Enter</kbd> to automatically save and advance to the next person, or press <kbd>Escape</kbd> to dismiss. When all groups are named, a beautiful fullscreen confetti celebration will trigger!

### 📂 3. Automatic Group/Collective Photos Filtering & Export
- **Face Count Detection**: The app automatically analyzes and counts the number of detected faces in each original image.
- **Dedicated Collective Directory**: Images with face counts greater than or equal to a configurable threshold (e.g. $\ge 5$ faces) are automatically designated as **Group Photos** and exported into a dedicated `Ảnh tập thể` folder.
- **Flexible UI Controls on Sidebar**:
  - Easily adjust the group photo threshold slider (from `3` to `10` faces).
  - Enable **"Exclude group photos from individual folders"** checkbox to prevent large class/group photos from being copied into dozens of separate individual folders, keeping student folders extremely clean while saving significant disk space.

---

## 🛠️ Architecture & Folder Structure

### Tech Stack:
- **Backend**: FastAPI (Python), OpenCV (YuNet & SFace), Scikit-Learn (DBSCAN).
- **Frontend**: HTML5, Vanilla CSS3 (Custom Design Tokens, micro-animations), JavaScript ES6.

### Directory Layout:
```text
face-sorter/
├── app.py                  # FastAPI API Server (Endpoints for scanning, renaming, exporting)
├── core/
│   ├── clusterer.py        # DBSCAN face clustering logic
│   ├── exporter.py         # Smart image exporter (Separates group photos & individual folders)
│   └── face_processor.py   # OpenCV face detection and embeddings generator
├── models/
│   ├── face_detection_yunet_2023mar.onnx     # YuNet model weights
│   └── face_recognition_sface_2021dec.onnx   # SFace model weights
├── static/                 # Web assets
│   ├── app.js              # Frontend UI logic (Wizard, Confetti, API integrations)
│   ├── index.html          # Web application template
│   └── styles.css          # Premium Dark Glassmorphism stylesheet
├── README.md               # Main Project Documentation (English)
├── README_VI.md            # Project Documentation (Vietnamese)
└── .gitignore              # Git ignored files configuration
```

---

## 🚀 Installation & Quick Start

### 1. Prerequisites
Ensure you have **Python 3.9 or higher** installed on Windows, macOS, or Linux.

### 2. Clone the Repository
```bash
git clone https://github.com/FeurisPT2/face-sorter.git
cd face-sorter
```

### 3. Set Up a Virtual Môi Trường (Virtual Environment)
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows (Command Prompt):
.venv\Scripts\activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

### 4. Install Dependencies
```bash
pip install --upgrade pip
pip install fastapi uvicorn opencv-python numpy scikit-learn pydantic
```

### 5. Launch the Application
```bash
python -m uvicorn app:app --reload --port 8000
```
Open your web browser and navigate to: [http://localhost:8000](http://localhost:8000).

---

## 💡 How to Use

1. **Step 1: Set Up Directories**
   - Enter the absolute directory path containing your yearbook photos into **"Thư mục ảnh gốc" (Source Directory)**. (Or click the *"Tạo ảnh mẫu thử nghiệm nhanh"* button to automatically download famous historical portrait samples to test immediately).
2. **Step 2: Run AI Face Scanning**
   - Click **"Quét khuôn mặt AI" (Scan Faces)** and watch the real-time scanning progress bar on the main panel.
3. **Step 3: Interactive Naming**
   - Once completed, accept the prompt to start the **Interactive Naming Wizard**.
   - Type each person's name and hit <kbd>Enter</kbd> to sequentially save and proceed.
   - You can also drag-and-drop face crops directly onto any person's card in the main grid if there are any misclassifications.
4. **Step 4: Configure & Export**
   - Enter your target output path in **"Thư mục xuất" (Export Directory)**.
   - Adjust the **Ngưỡng ảnh tập thể (Group Photo Threshold)** and choose whether to exclude group photos from individual folders.
   - Click **"Xuất thư mục phân loại" (Export Organized Folders)**.

---

## 📄 License
This project is licensed under the **MIT License** - you are free to use, modify, and distribute it for both personal and commercial purposes.

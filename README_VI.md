# 🎓 Face Sorter (Trình Phân Loại Ảnh Kỷ Yếu AI Thông Minh)

🌐 [Read the English version here](./README.md)

**Face Sorter** là một ứng dụng web hiện đại, mạnh mẽ, sử dụng trí tuệ nhân tạo (AI) tiên tiến để tự động phát hiện, nhận dạng và phân loại khuôn mặt từ hàng trăm bức ảnh kỷ yếu tập thể thành các thư mục cá nhân riêng biệt. Giao diện người dùng được thiết kế tỉ mỉ theo phong cách **Dark Glassmorphism** siêu cao cấp, mang lại trải nghiệm mượt mà và trực quan vượt trội.

---

## ✨ Các tính năng nổi bật

### 🧠 1. Công nghệ AI Nhận Diện Khuôn Mặt Tối Tân
- **Phát hiện khuôn mặt (Face Detection)**: Sử dụng mô hình học sâu siêu tốc **YuNet** tích hợp trực tiếp qua bộ thư viện OpenCV nâng cao, cho khả năng phát hiện khuôn mặt cực kỳ chính xác ở nhiều góc độ và điều kiện ánh sáng.
- **Trích xuất đặc trưng & Nhận dạng (Face Recognition)**: Sử dụng mô hình **SFace** của OpenCV để trích xuất vector đặc trưng (embeddings) 128 chiều có độ chính xác cao.
- **Tự động gom nhóm (Clustering)**: Thuật toán gom nhóm mật độ **DBSCAN** tự động gom các khuôn mặt có độ tương đồng cao vào cùng một nhóm (một người) mà không cần khai báo số lượng người trước.

### 🪄 2. Trình đặt tên từng người tuần tự (Interactive Naming Wizard)
*Đây là tính năng độc quyền giúp tối ưu hoá tối đa trải nghiệm đặt tên thành viên sau phân loại.*
- **Tự động kích hoạt**: Ngay sau khi quét xong, ứng dụng sẽ đề xuất mở trình đặt tên tuần tự.
- **Thiết kế phân vùng thông minh**:
  - *Cột bên trái*: Xem ảnh chân dung đại diện phóng to cùng ô nhập liệu được tự động focus và chọn sẵn văn bản để bạn gõ tên ngay lập tức.
  - *Cột bên phải*: Hiển thị danh sách tất cả các ảnh khuôn mặt nhỏ được gom vào nhóm này để đối chiếu chéo, giúp bạn nhận diện chính xác 100%.
- **Tối ưu phím tắt**: Nhập tên xong chỉ cần ấn `Enter` để Lưu & Tự động nhảy sang người tiếp theo, hoặc ấn `Escape` để đóng nhanh. Khi hoàn thành người cuối cùng, hiệu ứng pháo hoa confetti cực đẹp sẽ bùng nổ ăn mừng!

### 📂 3. Tự động gom & tách biệt Ảnh tập thể (Group Photos Export)
- **Tự động nhận diện**: Hệ thống tự động phân tích và đếm số lượng khuôn mặt trên mỗi bức ảnh gốc.
- **Xuất thư mục riêng biệt**: Ảnh có số lượng khuôn mặt lớn hơn hoặc bằng ngưỡng quy định (ví dụ $\ge 5$ mặt) sẽ được tự động xếp vào danh mục riêng **`Ảnh tập thể`**.
- **Cấu hình trực quan trên Sidebar**:
  - Tuỳ chỉnh ngưỡng ảnh tập thể linh hoạt bằng thanh trượt (từ `3` đến `10` khuôn mặt).
  - Tuỳ chọn **"Loại bỏ ảnh tập thể khỏi thư mục riêng của từng người"** giúp tránh hiện tượng một ảnh tập thể cả lớp bị sao chép lặp lại vào hàng chục thư mục cá nhân gây lãng phí bộ nhớ và làm nhiễu thư mục của từng người.

---

## 🛠️ Kiến trúc công nghệ & Cấu trúc thư mục

### Công nghệ sử dụng:
- **Backend**: FastAPI (Python), OpenCV (YuNet & SFace), Scikit-Learn (DBSCAN gom cụm).
- **Frontend**: HTML5, Vanilla CSS3 (Custom Design Tokens, animations), JavaScript ES6.

### Sơ đồ thư mục:
```text
face-sorter/
├── app.py                  # API Server FastAPI (Các endpoints nhận dạng, quét, đổi tên, xuất file)
├── core/
│   ├── clusterer.py        # Thuật toán gom cụm khuôn mặt sử dụng DBSCAN
│   ├── exporter.py         # Bộ xuất ảnh thông minh (Phân loại thư mục cá nhân & Ảnh tập thể)
│   └── face_processor.py   # Bộ xử lý ảnh (Đọc ảnh, chạy YuNet phát hiện, chạy SFace trích vector)
├── models/
│   ├── face_detection_yunet_2023mar.onnx     # Mô hình phát hiện YuNet
│   └── face_recognition_sface_2021dec.onnx   # Mô hình nhận dạng SFace
├── static/                 # Giao diện Frontend web
│   ├── app.js              # Logic tương tác điều khiển giao diện (Wizard, Confetti, API calls)
│   ├── index.html          # Khung xương giao diện ứng dụng kỷ yếu
│   └── styles.css          # Phong cách thiết kế Dark Glassmorphism cao cấp
├── README.md               # Tài liệu hướng dẫn sử dụng dự án (Tiếng Anh)
├── README_VI.md            # Tài liệu hướng dẫn sử dụng dự án (Tiếng Việt)
└── .gitignore              # Cấu hình bỏ qua các tệp không cần đẩy lên Git
```

---

## 🚀 Hướng dẫn cài đặt và khởi chạy nhanh

### 1. Chuẩn bị môi trường
Yêu cầu hệ điều hành: Windows, macOS hoặc Linux đã cài đặt **Python 3.9 trở lên**.

### 2. Clone dự án và truy cập thư mục
```bash
git clone https://github.com/FeurisPT2/face-sorter.git
cd face-sorter
```

### 3. Khởi tạo môi trường ảo (Virtual Environment)
```bash
# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt môi trường ảo
# Trên Linux/macOS:
source .venv/bin/activate
# Trên Windows (Command Prompt):
.venv\Scripts\activate
# Trên Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

### 4. Cài đặt các thư viện phụ thuộc (Dependencies)
```bash
pip install --upgrade pip
pip install fastapi uvicorn opencv-python numpy scikit-learn pydantic
```

### 5. Khởi chạy ứng dụng
```bash
python -m uvicorn app:app --reload --port 8000
```
Sau khi chạy, hãy mở trình duyệt web bất kỳ và truy cập địa chỉ: [http://localhost:8000](http://localhost:8000).

---

## 💡 Hướng dẫn sử dụng ứng dụng

1. **Bước 1: Thiết lập thư mục**
   - Nhập đường dẫn thư mục tuyệt đối chứa toàn bộ ảnh kỷ yếu của bạn vào ô **"Thư mục ảnh gốc"**. (Có thể bấm nút *"Tạo ảnh mẫu thử nghiệm nhanh"* bên dưới để tải tự động một số bức ảnh mẫu của các nhân vật lịch sử nổi tiếng để chạy thử).
2. **Bước 2: Quét khuôn mặt**
   - Nhấn nút **"Quét khuôn mặt AI"** và theo dõi tiến trình phân tích ảnh cực kỳ sinh động trên màn hình chính.
3. **Bước 3: Đặt tên thành viên**
   - Sau khi quét xong, hãy nhấn **OK** trên hộp thoại đề xuất gom nhóm để khởi động **Interactive Naming Wizard**.
   - Gõ tên từng người và bấm `Enter` để hoàn thành đặt tên tuần tự siêu tốc.
   - Bạn cũng có thể kéo thả thủ công các khuôn mặt bị phân loại nhầm giữa các thẻ người ở lưới màn hình chính để ghép nhóm lại.
4. **Bước 4: Thiết lập Xuất kết quả**
   - Nhập đường dẫn thư mục bạn muốn lưu ảnh đã phân loại tại ô **"Thư mục xuất"**.
   - Thiết lập số mặt để nhận diện ảnh tập thể bằng **Ngưỡng ảnh tập thể**.
   - Tích chọn *"Loại bỏ ảnh tập thể khỏi thư mục riêng của từng người"* nếu cần.
   - Nhấn **"Xuất thư mục phân loại"** và tận hưởng kết quả sắp xếp hoàn hảo!

---

## 📄 Giấy phép (License)
Dự án được phân phối dưới giấy phép **MIT License**. Bạn hoàn toàn có thể sử dụng, sửa đổi và chia sẻ cho mục đích cá nhân cũng như thương mại.

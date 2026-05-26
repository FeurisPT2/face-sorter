import sys
from pathlib import Path

# Add current directory to python path
BASE_DIR = Path(__file__).parent
sys.path.append(str(BASE_DIR))

from core.face_processor import FaceProcessor

def test_pipeline():
    print("=== Bắt đầu kiểm thử tích hợp RetinaFace + ArcFace INT8 ===")
    
    # 1. Khởi tạo bộ xử lý
    processor = FaceProcessor()
    
    # 2. Tải mô hình (sẽ tự động tải xuống nếu chưa có)
    print("1. Đang kiểm tra và tải mô hình...")
    try:
        processor.ensure_models()
        print("✓ Tải mô hình thành công hoặc đã có sẵn!")
    except Exception as e:
        print(f"✗ Lỗi khi tải mô hình: {e}")
        return
        
    print("2. Đang khởi tạo ONNX Runtime Sessions...")
    try:
        processor.load_models()
        print("✓ Khởi tạo sessions thành công!")
        print(f"  - RetinaFace inputs: {processor.det_input_name}, outputs: {processor.det_output_names}")
        print(f"  - ArcFace inputs: {processor.rec_input_name}, outputs: {processor.rec_output_name}")
    except Exception as e:
        print(f"✗ Lỗi khi khởi tạo sessions: {e}")
        return

    # 3. Quét thử một ảnh mẫu
    samples_dir = BASE_DIR / "sample_photos"
    cache_dir = BASE_DIR / "cache"
    
    if not samples_dir.exists():
        print(f"! Thư mục {samples_dir} chưa được tạo. Vui lòng bấm tạo mẫu trong ứng dụng trước.")
        return
        
    # Get first image from samples
    img_files = list(samples_dir.glob("*.jpg")) + list(samples_dir.glob("*.jpeg"))
    if not img_files:
        print("! Không tìm thấy ảnh mẫu nào trong 'sample_photos'.")
        return
        
    test_img = img_files[0]
    print(f"3. Đang quét thử ảnh mẫu: {test_img.name}...")
    try:
        results = processor.scan_image(test_img, cache_dir)
        print(f"✓ Quét thành công! Tìm thấy {len(results)} khuôn mặt.")
        for idx, face in enumerate(results):
            print(f"  Face {idx+1}:")
            print(f"    - ID: {face['id']}")
            print(f"    - Score: {face['score']:.4f}")
            print(f"    - Bounding Box: {face['bbox']}")
            print(f"    - Embedding length: {len(face['embedding'])}")
            
        print("\n=== KIỂM THỬ HOÀN TẤT THÀNH CÔNG! ===")
    except Exception as e:
        print(f"✗ Lỗi khi xử lý ảnh: {e}")

if __name__ == "__main__":
    test_pipeline()

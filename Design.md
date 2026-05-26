# 🎨 Quy Tắc Thiết Kế Giao Diện (UI/UX Rules) - Face Sorter

Tài liệu này quy định các tiêu chuẩn thiết kế và cấu trúc giao diện bắt buộc dành cho AI Agent khi sinh code frontend cho dự án **Face Sorter**.

## 1. Tổng Quan Về Phong Cách (Design Language)
* Ngôn ngữ thiết kế chủ đạo của ứng dụng là **Dark Glassmorphic** (kính mờ trên nền tối)[cite: 1].
* Phong cách thiết kế này cần tạo ra cảm giác không gian công nghệ tương lai, có chiều sâu và cực kỳ sang trọng[cite: 1].

## 2. Thành Phần Giao Diện: Thanh Sidebar Cấu Hình
* Thanh sidebar cần được thiết lập với chiều rộng cố định là `380px`[cite: 1].
* Giao diện sidebar phải bao gồm một dải màu gradient óng ánh chạy ngang qua logo thương hiệu "FaceSorter - Kỷ Yếu AI"[cite: 1].

### Thẻ Kính Nổi (Floating Glass Cards)
* Mỗi mục cấu hình (Thư mục, Bộ quét, Độ nhạy, Xuất kết quả) phải được bao bọc trong một khối thẻ riêng biệt bo tròn `18px`[cite: 1].
* CSS của thẻ cần sử dụng viền phản xạ ánh sáng mỏng với giá trị `1px solid rgba(255,255,255,0.03)`[cite: 1].
* Nền của thẻ phải mờ bán trong suốt bằng mã `rgba(255,255,255,0.015)`[cite: 1].
* Khi người dùng hover (rê chuột), thẻ phải tự động nổi lên thông qua thuộc tính `transform: translateY(-2px)`[cite: 1].
* Trạng thái hover cũng cần làm tăng độ sáng viền và tỏa ra ánh đèn nền neon mờ với CSS `box-shadow: 0 0 20px rgba(99, 102, 241, 0.06)`[cite: 1].
* Mỗi tiêu đề bên trong thẻ cần có các biểu tượng SVG viền neon phát sáng tương ứng nằm ở phía trước để trực quan hóa thao tác[cite: 1].

### Thao Tác Thanh Trượt (Sliders)
* Núm trượt điều chỉnh cho Workers và Độ nhạy phải là núm tròn màu trắng được bọc bởi viền màu Indigo nổi bật[cite: 1].
* Khi người dùng kéo hoặc hover, núm trượt phải phình to co giãn với thuộc tính `scale(1.25)` và lan tỏa vùng sáng neon[cite: 1].

### Interactive Visualizers (Minh Họa Trực Quan)
* Biểu đồ trực quan hóa độ nhạy phân loại phải sử dụng cụm 4 hạt nhân tròn[cite: 1].
* Khi giảm độ nhạy trên thanh trượt, 4 hạt nhân tự động chuyển sang màu Indigo và co cụm lại gần nhau[cite: 1].
* Khi tăng độ nhạy, 4 hạt nhân phải tự động đổi thành 4 màu chuyển sắc khác nhau và dãn cách xa nhau để mô phỏng thuật toán DBSCAN[cite: 1].
* Giao diện phải có một sơ đồ cây cấu trúc xuất ảnh (Live Export Tree) hiển thị dạng mã nguồn bằng thẻ `pre`, tự động cập nhật cấu trúc thư mục đích dựa trên tùy chọn của người dùng[cite: 1].

## 3. Thành Phần Giao Diện: Vùng Hiển Thị Chính

### Thanh Đầu Trang (Header)
* Huy hiệu trạng thái (Status Badge) phải được thiết kế bo tròn `30px` dưới dạng capsule[cite: 1].
* Huy hiệu này cần tích hợp một chấm trạng thái nhấp nháy phát sáng (pulse animation) liên tục trong quá trình quét ảnh[cite: 1].
* Khu vực này phải chứa các thẻ thống kê (Stat Cards) nhỏ bo góc tinh tế, hiển thị tổng số ảnh đã tìm thấy, số khuôn mặt đã nhận dạng và tốc độ quét[cite: 1].

### Trình Trạng Thái Quét (Scan Progress Panel)
* Giao diện chờ tải phải sử dụng hiệu ứng vòng xoay quay ngược chiều nhau (Spinner Kép), kết hợp chuyển màu kép mượt mà giữa màu Indigo và Pink[cite: 1].
* Thanh Tiến Trình (Progress Bar) phải mang thiết kế gradient óng ánh và có khả năng tự động tính toán phần trăm chính xác[cite: 1].
* Bảng tiến trình cần hiển thị tên file đang quét bằng hiệu ứng chạy chữ mượt mà[cite: 1].
* Hệ thống cần hiển thị tốc độ xử lý tính theo Ảnh/giây và đồng hồ đếm ngược thời gian hoàn thành dự kiến (ETA) theo thời gian thực[cite: 1].

### Lưới Kết Quả Gom Nhóm (People Results Grid)
* Danh sách các nhóm người được phát hiện phải hiển thị dưới dạng các thẻ bo tròn `20px` tinh xảo[cite: 1].
* Mỗi thẻ người cần được trang bị một dải màu gradient óng ánh ở phần viền trên[cite: 1].
* Khi hover, thẻ phải tự động sáng bừng viền và tạo hiệu ứng nâng nhẹ thẻ lên[cite: 1].
* Ảnh đại diện bên trong thẻ có dạng tròn với viền gradient óng ánh, đi kèm tên nhóm và số lượng ảnh thuộc về người đó[cite: 1].
* Giao diện phải hỗ trợ thao tác Kéo thả Thủ công (Drag & Drop) để chuyển khuôn mặt bị nhận diện nhầm sang thẻ người khác[cite: 1].
* Khi thực hiện thao tác kéo thả, giao diện tự động cập nhật chuyển nhóm tức thì với hiệu ứng viền đứt nét (`dashed line`) bao quanh cực kỳ trực quan[cite: 1].

## 4. Trình Đặt Tên Tuần Tự (Naming Wizard Modal)
* Cửa sổ Modal hiển thị sau khi quét phải sử dụng kính mờ bán trong suốt bọc blur nền sâu ở phía sau[cite: 1].

### Bố Cục Phân Vùng (Smart Split Layout)
* Cột trái của Modal được dùng để đặt tên, hiển thị chân dung đại diện phóng to siêu nét và ô nhập liệu tên[cite: 1].
* Ô nhập liệu tên phải được tự động focus và bôi đen sẵn văn bản[cite: 1].
* Cột phải dùng để đối chiếu chéo, hiển thị lưới tất cả các ảnh cắt khuôn mặt khác cùng nhóm[cite: 1].

### Điều Khiển Bằng Phím Tắt
* Agent cần lập trình phím `Enter` để lưu tên và tự động chuyển sang người kế tiếp[cite: 1].
* Phím `Escape` được sử dụng để hủy nhanh thao tác[cite: 1].

### Hiệu Ứng Hoàn Thành
* Khi người dùng đặt tên xong thành viên cuối cùng, giao diện phải kích hoạt một màn pháo hoa giấy Confetti đa sắc màu bùng nổ tung bay khắp màn hình[cite: 1].

## 5. Yêu Cầu Tích Hợp Kỹ Thuật
* Giao diện phải được thiết kế để phản hồi mượt mà trạng thái từ backend FastAPI, sử dụng khóa luồng `threading.Lock` để tránh xung đột dữ liệu khi nhiều tiến trình con báo cáo kết quả[cite: 1].
* Các thành phần loading và thống kê hiệu năng phải đảm bảo tính liên tục, không gây giật lag khi backend xử lý dữ liệu nặng từ thư viện `rawpy`[cite: 1].
* UI cần xử lý linh hoạt trạng thái hiển thị giữa chế độ Tuần tự (1 luồng) và chế độ Đa tiến trình (`ProcessPoolExecutor`) dựa trên cấu hình người dùng thiết lập[cite: 1].
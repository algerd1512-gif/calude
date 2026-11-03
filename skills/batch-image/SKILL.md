---
name: batch-image
description: "Tạo bộ ảnh hàng loạt từ danh sách prompt đánh số (\"001. ...\") qua MCP server auto-image: gửi vào hàng đợi theo lô, lưu ảnh thành 001.png, 002.png... trong thư mục dự án, tự kiểm tra và tạo lại ảnh có chữ (reads \"...\") bị sai, chạy tiếp khi bị ngắt, và báo cáo cuối. Dùng cho mọi kênh (Kinh Tế Học, What If...). Dùng khi người dùng nói \"tạo ảnh hàng loạt\", \"chạy batch ảnh\", \"batch-image\", dán danh sách prompt đánh số và muốn ra ảnh, hoặc \"tạo lại ảnh 012, 045\"."
---

# batch-image

Chạy danh sách prompt đánh số qua MCP server **auto-image**, lưu ảnh đúng số, kiểm tra ảnh có chữ.
Skill này là "máy chạy": **KHÔNG BAO GIỜ viết lại, sửa, dịch hay "cải thiện" prompt**. Gửi đúng
nguyên văn phần sau "NNN. ". Kể cả khi tạo lại ảnh lỗi chữ cũng gửi lại đúng prompt cũ.

Helper: `scripts/batch_image.py` (cùng thư mục với file này; gọi bằng đường dẫn tuyệt đối
`python3 <skill_dir>/scripts/batch_image.py ...`). Nó lo phần parse, state, file còn thiếu, báo cáo.

## BƯỚC 0 — Đọc schema tool auto-image (mỗi phiên một lần)

1. Tìm tool: các tool tên dạng `mcp__auto-image__*` (hoặc `mcp__auto_image__*`). Nếu là deferred tool,
   nạp bằng ToolSearch (`query: "auto-image"`, hoặc `"+auto image"`).
   **Không thấy tool nào → DỪNG**, báo người dùng: "MCP auto-image chưa kết nối trong phiên này" và
   hướng dẫn kiểm tra `/mcp` (Claude Code) hoặc cài đặt connector. Không giả lập, không tự gọi API khác.
2. Đọc schema, xác định và ghi nhớ cho phiên (nói ngắn gọn cho người dùng ở lần chạy đầu):
   - **Tool gửi job** (submit/enqueue/generate...) và tham số prompt.
   - **Tỉ lệ khung**: tham số kiểu `aspect_ratio` / `ratio` / `size` / `width,height`. Có → luôn đặt
     16:9 (hoặc 1920x1080 / 1344x768 tuỳ giá trị cho phép), trừ khi người dùng nói khác.
   - **Model**: tham số `model`. Có → hỏi người dùng một lần (đưa danh sách giá trị enum nếu schema có),
     ghi vào `state.json` qua câu trả lời; lần sau dùng lại.
   - **Tên file / thư mục lưu**: tham số kiểu `filename` / `output_path` / `output_dir` / `save_to`.
     Có → truyền thẳng `<project_dir>/NNN.png`. Không có → sau khi job xong, lấy đường dẫn/URL ảnh từ
     kết quả và tự copy/tải về `<project_dir>/NNN.png` bằng Bash (`cp`, hoặc `curl -sSL -o`). Nếu tool
     trả ảnh dạng base64 → giải mã ra file.
   - **Tool theo dõi** (status/get_job/list_queue/wait...) và **tool lấy kết quả**. Nếu tool gửi job
     đã chặn đến khi xong và trả luôn ảnh thì không cần poll.
   - Giới hạn hàng đợi / số job đồng thời nếu schema hoặc mô tả tool có nêu.

## BƯỚC 1 — Nhận đầu vào

1. Danh sách prompt: dán vào chat, hoặc đường dẫn file .txt/.md. Nếu dán → ghi nguyên văn ra file
   `<project_dir>/prompts.txt` (dùng Write, không sửa gì). Nếu là file → copy vào `<project_dir>/prompts.txt`.
   Mỗi prompt một dòng `NNN. nội dung` (chấp nhận `1.`, `001)`; dòng xuống hàng không có số được nối vào
   prompt trước).
2. **Tên dự án**: hỏi MỘT lần lúc đầu (nếu người dùng chưa nói). Thư mục dự án mặc định:
   `<thư mục làm việc hiện tại>/<tên-dự-án>/`. Nếu thư mục đã có `state.json` → đây là chạy tiếp.
3. Chạy `batch_image.py init <project_dir> <project_dir>/prompts.txt`. Đọc output:
   số prompt, prompt nào có chữ và chữ cần có, cảnh báo thiếu số / trùng số. Có cảnh báo → báo người
   dùng và hỏi có chạy tiếp không (không tự đánh lại số).
   `init` chạy lại trên dự án cũ giữ nguyên tiến độ của các prompt không đổi.

"Ảnh có chữ" = prompt có `reads "..."` / `reading "..."`, hoặc có cụm chữ trong ngoặc kép đi kèm
từ như label / text / title / brand name / sign. Danh sách chữ cần có nằm trong trường `texts`.

## BƯỚC 2 — Chạy theo lô

1. `batch_image.py todo <project_dir>` → các số còn THIẾU file ảnh. Đó là việc cần làm (tự động chạy
   tiếp từ chỗ bị ngắt; ảnh đã có không gửi lại).
2. Chia lô **5 prompt** một lần (giảm xuống 3 nếu tool báo quá tải/rate limit; tăng tới 10 nếu schema
   cho phép hàng đợi lớn và mọi thứ ổn định). Trong một lô:
   - Gửi lần lượt theo đúng thứ tự số, mỗi job một prompt. Ngay khi có job id →
     `batch_image.py mark <dir> NNN job <id>` (để khớp số ↔ job, không dựa vào thứ tự trả về).
   - Chờ cả lô xong bằng tool status/wait. KHÔNG dùng `sleep` dài trong Bash; nếu cần chờ, poll tool
     status với khoảng cách hợp lý (Monitor/until-loop nếu có), tối đa ~10 phút mỗi job rồi coi là lỗi.
   - Lưu từng ảnh thành `<project_dir>/NNN.png` (tham số filename hoặc copy/tải như Bước 0), rồi
     `mark <dir> NNN status done`. Job lỗi → `mark ... status error` + `note` lý do, gửi lại tối đa
     1 lần; vẫn lỗi thì để đó, báo cáo cuối sẽ liệt kê ở "Chưa có file ảnh".
3. Kiểm tra chữ (Bước 3) cho ảnh có chữ của lô vừa xong, rồi sang lô sau.
4. Báo tiến độ ngắn sau mỗi lô: "Lô 2/8 xong (006–010), 1 ảnh tạo lại".

## BƯỚC 3 — Kiểm tra ẢNH CÓ CHỮ (chỉ ảnh `has_text`)

Ảnh không chữ: KHÔNG kiểm tra, không xem.

Với mỗi ảnh có chữ: mở bằng Read (`<project_dir>/NNN.png`) và so với `texts` (xem bằng
`batch_image.py show <dir> NNN`). Đánh **lỗi** nếu có bất kỳ điều nào:
- Sai chính tả, thiếu/thừa/sai dấu tiếng Việt (VẬN ĐƠN ≠ VAN DON ≠ VẬN ĐON), sai số, sai dấu câu
  quan trọng (16,8% ≠ 16.8% ≠ 168%), sai hoa/thường rõ rệt.
- Chữ chồng chéo, méo, đứt, lặp lại, không đọc được.
- Có chữ thừa đọc được mà prompt không yêu cầu (nhãn lạ, tiêu đề phụ, chữ giả nghĩa). Dòng chữ mờ
  không đọc được mà prompt cho phép (placeholder lines) thì không tính.
- Có chữ "VOX", logo/watermark/chữ ký bất kỳ.
- Thiếu cụm chữ được yêu cầu.

Kết quả:
- Đạt → `mark <dir> NNN check ok`.
- Lỗi → `mark <dir> NNN note "<lỗi cụ thể>"`, `mark <dir> NNN retry`, gửi lại ĐÚNG prompt cũ, ghi đè
  `NNN.png`, kiểm tra lại. **Tối đa 2 lần tạo lại** (tổng 3 ảnh). Giữ bản tốt nhất: trước khi ghi đè,
  đổi tên ảnh cũ thành `NNN_try1.png`, `NNN_try2.png`; nếu cả 3 đều lỗi, để bản ít lỗi nhất làm `NNN.png`.
- Sau 2 lần vẫn lỗi → `mark <dir> NNN check bad` (note đã có lỗi cuối), không thử thêm.
- Xong và đạt sau khi tạo lại → xoá các file `NNN_try*.png`.

Nghiêm khắc nhưng đúng: chỉ đánh lỗi khi thật sự nhìn thấy lỗi; nếu chữ quá nhỏ để chắc chắn, ghi
note "không chắc" và coi là đạt.

## BƯỚC 4 — Báo cáo

Chạy `batch_image.py report <project_dir>` và trình bày ngắn:
- Tổng số ảnh (có/tổng), số ảnh tạo lại (và số nào),
- **Danh sách số ảnh vẫn lỗi sau 2 lần** kèm lỗi cụ thể → người dùng tự xử lý,
- Số chưa có file (job lỗi) nếu có, và đường dẫn thư mục dự án.

## LỆNH "tạo lại ảnh 012, 045"

1. Xác định dự án (dự án vừa chạy trong phiên; nếu không rõ thì hỏi tên).
2. `batch_image.py todo <dir> --only "012,045"` → danh sách hợp lệ (cảnh báo số không có trong danh sách).
3. Với mỗi số: đổi tên ảnh hiện có thành `NNN_old.png`, `mark NNN check ""`, gửi lại prompt gốc, lưu
   `NNN.png`. Đây là yêu cầu chủ động của người dùng → bộ đếm 2 lần tạo lại tính lại từ đầu cho lần này.
   Ảnh có chữ vẫn qua Bước 3. Xong và đạt → xoá `NNN_old.png`.
4. Báo cáo ngắn chỉ cho các số này.

Người dùng có thể kèm prompt mới cho một số ("tạo lại 012 với prompt: ..."): khi đó, và chỉ khi đó,
thay prompt của số đó trong `prompts.txt` bằng nguyên văn người dùng đưa, chạy `init` lại, rồi tạo.

## Chạy tiếp khi bị ngắt

Mọi tiến độ suy ra từ file ảnh trên đĩa + `state.json`. Khi người dùng nói "chạy tiếp" / chạy lại skill
với cùng dự án: `init` (giữ state) → `todo` → tiếp Bước 2. Job đã gửi mà chưa có file (có `job` id): kiểm
tra job đó trên auto-image trước; nếu đã xong thì lấy ảnh về, khỏi gửi lại.

## Nguyên tắc

- Không sửa prompt. Không đổi số. Không bỏ qua số.
- Không xem ảnh không chữ (tiết kiệm). Không in prompt dài ra chat.
- Mỗi lô xong mới gửi lô tiếp; không đổ cả trăm job vào hàng đợi cùng lúc.

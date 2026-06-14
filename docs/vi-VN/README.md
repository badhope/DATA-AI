# DATA-AI

> Một AI agent cuối cùng cũng hiểu dữ liệu doanh nghiệp của bạn.

Nói thật. Bạn biết rồi đó. Công ty nào cũng có đống báo cáo tài chính, tài liệu nội bộ, hồ sơ khách hàng, file dự án, cái thư mục không ai dám đụng, và vài file Excel mà thực ra là hệ thần kinh của công ty. Cái gì cũng không nói chuyện với cái gì, không ai tìm thấy gì, và mấy người thực sự hiểu dữ liệu thì đang chết chìm trong yêu cầu.

**DATA-AI** sinh ra vì cái đó.

**DATA-AI** là một AI agent tự host, sống ngay cạnh dữ liệu doanh nghiệp của bạn — tài chính, tri thức nội bộ, mấy thứ quan trọng — và làm thay mấy việc nhàm. Hỏi một câu, nó bới trong file của bạn và trả lời kèm nguồn. Giao một việc, nó chạy. Báo cáo tuần của `/finance/2025-Q4/`? Xong trong hai phút, không phải hai ngày.

## Trong hộp có gì

- **Knowledge base thực sự hiểu việc của bạn** — quăng PDF, Word, bảng tính, export Notion, wiki nội bộ, dump text vào. Nó index, học, rồi trả lời như một đồng nghiệp mười năm.
- **Workflow vẽ ra, không code** — kéo vài khối, nối dây, lưu. Làm sạch dữ liệu, báo cáo tháng, "tóm tắt hết cái mới trong `/legal/`", "đánh dấu hợp đồng hết hạn quý này", gì cũng được.
- **Agent làm tới nơi tới chốn** — quăng cho nó một mục tiêu. Nó tự bẻ thành bước, gọi tool đúng, tự kiểm, rồi báo lại làm gì. Bớt trông, thêm hàng.
- **Model thì bạn chọn** — OpenAI, Claude, DeepSeek, Llama local, cái lạ hoắc mà team bạn thích. Cắm vào, agent dùng.
- **Vector DB thì bạn chọn** — pgvector, Milvus, Weaviate, Qdrant, Elasticsearch. Cái nào đang chạy thì dùng cái đó.
- **UI web không ghét** — console cho admin, chat cho người dùng, API cho kỹ sư thích gõ.

## Tại sao làm

Thử SaaS rồi. Thử "open-core" rồi. Thử tự dùng API OpenAI thuần để build, tới lần thứ tư viết lại cùng một đống boilerplate thì ngán.

Nên làm cái mà tự mình muốn dùng:

- **Tự host** — một box Linux là chạy, không cần Kubernetes.
- **Dữ liệu là của bạn** — không ra ngoài, mỗi lần gọi model đều audit được.
- **Không gọi sales** — open source, code ở đây.
- **Không hẹn "ra mắt Q3"** — feature làm khi có người cần.

## Chạy thử

Cách dễ (Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI/docker
cp .env.example .env
docker compose up -d
```

Tay không (không Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI
./dev/setup
./dev/start-api    # một terminal
./dev/start-web    # một cái nữa
```

Mở <http://localhost:3000>. Hướng dẫn đầy đủ ở [`docs/`](./docs/).

## Kiến trúc, một đoạn

Backend Python + Flask, tổ chức theo domain để dễ tìm. Frontend Next.js (bản mới, không phải 2018). PostgreSQL cho dữ liệu có cấu trúc. Vector DB bạn chọn cho embedding. Celery + Redis cho mọi thứ không nên chặn user. Hệ plugin để thêm model, tool, tích hợp mà không cần fork cả repo.

## Đóng góp

Nhận PR. Đọc [CONTRIBUTING.md](./CONTRIBUTING.md) trước, đừng phí thứ Bảy.

## Giấy phép

[Apache 2.0](./LICENSE). Muốn làm gì thì làm, giữ dòng copyright là được.

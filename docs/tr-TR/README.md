# DATA-AI

> Şirketinin verisini sonunda anlayan bir AI ajanı.

Bak. Sorunu biliyorsun. Her şirkette bir sürü mali rapor, iç doküman, müşteri kaydı, proje dosyası, kimsenin dokunmaya cesaret edemediği o klasör ve şirketin sinir sistemi gibi işleyen birkaç Excel sayfası var. Hiçbiri birbiriyle konuşmuyor, kimse bir şey bulamıyor, veriyi gerçekten anlayan insanlar taleplere boğulmuş.

**DATA-AI** tam da bunun için yapıldı.

**DATA-AI** kendi sunucunda çalışan bir AI ajanı; şirketinin verisinin — finans, iç bilgi, önemli olan her şey — yanı başında yaşar ve sıkıcı işleri senin yerine yapar. Soru sor, dosyaları karıştırır, kaynaklarıyla cevap verir. Bir görev ver, yapar. `/finance/2025-Q4/` için haftalık rapor mu? İki günde değil, iki dakikada hazır.

## Kutuda ne var

- **İşini gerçekten bilen bilgi tabanları** — PDF, Word, e-tablo, Notion dışa aktarımı, iç wiki, düz metin yığını at. İndeksler, öğrenir, on yıldır orada olan bir iş arkadaşı gibi cevap verir.
- **Kod değil, çizimle yapılan iş akışları** — birkaç blok sürükle, bağla, kaydet. Veri temizliği, aylık raporlar, "`/legal/` altındaki yenileri özetle", "bu çeyrekte süresi dolan sözleşmeleri işaretle", ne istersen.
- **İşi bitiren ajanlar** — bir hedef ver. Adımlara böler, doğru araçları çağırır, kendi işini kontrol eder, ne yaptığını söyler. Daha az başında bekleme, daha çok teslim.
- **Model, senin seçimin** — OpenAI, Claude, DeepSeek, yerel Llama, ekibinin yemin ettiği o egzotik olan. Tak, çalışsın.
- **Vector DB, senin seçimin** — pgvector, Milvus, Weaviate, Qdrant, Elasticsearch. Zaten çalışanı kullan.
- **İnsanın kapatası gelmeyen bir web arayüzü** — adminler için konsol, son kullanıcı için sohbet, tıklamayı sevmeyen mühendisler için API.

## Neden yaptık

SaaS seçeneklerini denedik. Sonra "açık çekirdek" seçeneklerini. Sonra ham OpenAI API çağrılarıyla kendimiz kurmayı denedik, dördüncü kez aynı şablonu yazınca bıktık.

Biz de gerçekten kullanacağımız bir şey yaptık:

- **Kendi sunucunda** — tek bir Linux kutusunda çalışır, Kubernetes gerekmez.
- **Verin senin kalır** — ağ dışına çıkmaz, her model çağrısı denetlenebilir.
- **Satış araması yok** — açık kaynak, kod burada.
- **"Q3'te ekleyeceğiz" yok** — birisi ihtiyaç duyduğunda özellik yapılır.

## Çalıştırmak

Kolay yol (Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI/docker
cp .env.example .env
docker compose up -d
```

Elle (Docker'sız):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI
./dev/setup
./dev/start-api    # bir terminal
./dev/start-web    # bir başkası
```

<http://localhost:3000> adresini aç. Tam kılavuz [`docs/`](./docs/) altında.

## Mimari, bir paragrafta

Backend Python + Flask, alanlara göre düzenlenmiş, bir şey ararken bulabilesin. Frontend Next.js (modern olan, 2018 modeli değil). Yapılandırılmış veri için PostgreSQL. Embedding için senin seçtiğin vector DB. Kullanıcıyı bloklamaması gereken her şey için Celery + Redis. Model, araç ve entegrasyon ekleyebileceğin bir plugin sistemi, repoyu fork etmene gerek kalmaz.

## Katkıda bulunmak

PR kabul ediyoruz. Önce [CONTRIBUTING.md](./CONTRIBUTING.md) oku, Cumartesini boşa harcama.

## Lisans

[Apache 2.0](./LICENSE). Dilediğini yap, sadece telif notu kalsın.

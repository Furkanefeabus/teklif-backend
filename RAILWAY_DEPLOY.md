# 🚂 Railway Deploy Rehberi

## 📦 Dosyalar Hazır

Bu klasörde Railway için gerekli tüm dosyalar var:
- ✅ `server.py` - Backend kodları
- ✅ `requirements_render.txt` - Python bağımlılıkları
- ✅ `railway.json` - Railway config
- ✅ `Procfile` - Start komutu
- ✅ `runtime.txt` - Python versiyonu

## 🚀 Railway'e Deploy Adımları

### 1. GitHub'a Yükle

**Seçenek A: GitHub Web (Kolay)**
1. https://github.com/new - Yeni repo oluştur
2. Repo adı: `teklif-backend`
3. **Add file** → **Upload files**
4. Bu klasördeki TÜM dosyaları sürükle-bırak:
   - server.py
   - requirements_render.txt
   - railway.json
   - Procfile
   - runtime.txt
5. **Commit changes**

**Seçenek B: GitHub Desktop**
1. GitHub Desktop aç
2. New Repository → `teklif-backend`
3. Backend dosyalarını kopyala
4. Commit & Publish

---

### 2. Railway'e Bağlan

1. https://railway.app adresine git
2. **Login with GitHub** (ücretsiz)
3. Dashboard açılacak

---

### 3. Yeni Proje Oluştur

1. **New Project** butonuna tıkla
2. **Deploy from GitHub repo** seç
3. `teklif-backend` repo'sunu seç
4. **Deploy Now** butonuna bas

---

### 4. Environment Variables Ekle

Deploy başladıktan sonra:

1. Projeye tıkla
2. **Variables** sekmesine git
3. Şu değişkenleri ekle:

```
SUPABASE_URL
https://oaodopwljgymtrjepsvp.supabase.co

SUPABASE_SERVICE_KEY
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9hb2RvcHdsamd5bXRyamVwc3ZwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NDc2NzUyOCwiZXhwIjoyMDgwMzQzNTI4fQ.5O6DK7p2xVgY6TG-tHLEYuwd3CXNr_5bmAGGRCiB-6U

SUPABASE_ANON_KEY
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9hb2RvcHdsamd5bXRyamVwc3ZwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ3Njc1MjgsImV4cCI6MjA4MDM0MzUyOH0.zVLDbYEHP-zsgVsEFkshsj2Ld7JWOFcDGnWGPMuMqvo

SECRET_KEY
super-secret-key-change-this-in-production-12345
```

4. Variables ekledikten sonra otomatik redeploy olacak

---

### 5. Domain/URL Al

Deploy tamamlandığında:

1. **Settings** → **Networking**
2. **Generate Domain** butonuna bas
3. URL benzeri: `https://teklif-backend-production.up.railway.app`
4. **Bu URL'yi kopyala!**

---

### 6. Health Check Yap

URL'i tarayıcıda aç ve `/health` ekle:
```
https://teklif-backend-production.up.railway.app/health
```

Şu cevabı görmeli sin:
```json
{"status":"healthy","database":"connected"}
```

---

### 7. Netlify'ı Güncelle

1. https://app.netlify.com → Siten
2. **Site settings** → **Environment variables**
3. `EXPO_PUBLIC_BACKEND_URL` variable'ını ekle/güncelle:
```
EXPO_PUBLIC_BACKEND_URL = https://teklif-backend-production.up.railway.app
```
4. **Deploys** → **Trigger deploy** → **Clear cache and deploy**

---

## ✅ Tamamlandı!

Artık:
- ✅ Frontend: Netlify (bartesteklif.netlify.app)
- ✅ Backend: Railway
- ✅ Database: Supabase

Her şey çalışıyor! 🎉

---

## 🐛 Sorun Giderme

**Deploy başarısız:** Logs sekmesinden hataları kontrol et
**Environment variables eksik:** Variables doğru girildiğinden emin ol
**Database bağlantısı yok:** Supabase URL ve key'leri kontrol et

## 💰 Ücretsiz Plan

Railway ücretsiz plan:
- $5 kredi/ay
- 500 saat çalışma
- Yeterli kullanım için

Kredi biterse kart eklemen lazım ya da proje durur.

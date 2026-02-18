# Deployment Guide - Hosting Opcije

📦 Kompletan vodič za deploy web2 aplikacije na različite hosting platforme.

---

## 🎯 Preduslovi

Pre deploy-a, proveri:
- ✅ Supabase je setup-ovan (SQL schema + podaci)
- ✅ `js/config.js` ima prave credentials
- ✅ **GeoServer WMS** – za produkciju postavi `geoserverWmsProduction` u config.js (v. ispod)
- ✅ Lokalno testiranje radi (`python -m http.server 8000`)
- ✅ Nema greška u browser console-u

### NDVI, NDMI, NDRE na mapi (GeoJSON – bez GeoServer-a)

Slojevi NDVI, NDMI, NDRE koriste **GeoJSON** fajlove iz `data/` (ndvi_zones_1427_2.geojson, ndmi_zones_1427_2.geojson, ndre_zones_1427_2.geojson). Radi **bez GeoServer-a** – samo uploaduj ceo `web2/` folder.

---

## 🌐 Opcija 1: Netlify (RECOMMENDED - Free & Easy)

### **Prednosti:**
- ✅ **Free tier** - dovoljno za mali projekat
- ✅ **CDN** - brz pristup globalno
- ✅ **HTTPS** - automatski SSL sertifikat
- ✅ **Custom domain** - može tvoj domen
- ✅ **CI/CD** - automatski deploy sa Git-a

### **Koraci:**

#### **A) Preko Web UI (Drag & Drop):**

1. Idi na https://www.netlify.com
2. Sign up (GitHub account)
3. **Sites → Add new site → Deploy manually**
4. **Drag & drop** `web2/` folder
5. ✅ Site je live! URL: `https://random-name-123.netlify.app`

#### **B) Preko CLI:**

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Login
netlify login

# Deploy
cd web2
netlify deploy

# Test deploy (draft URL)
# Proveri da sve radi

# Production deploy
netlify deploy --prod

# Done! URL: https://your-site.netlify.app
```

### **Custom Domain:**

```bash
# U Netlify Dashboard:
Domain settings → Add custom domain → your-domain.com

# Podesi DNS (npr. Cloudflare):
CNAME www your-site.netlify.app
A @ 75.2.60.5  # Netlify IP
```

---

## 🚀 Opcija 2: Vercel (Free & Fast)

### **Prednosti:**
- ✅ **Free tier** - unlimited static sites
- ✅ **Edge Network** - globalni CDN
- ✅ **GitHub integration** - auto deploy
- ✅ **Serverless functions** - može backend (ako treba kasnije)

### **Koraci:**

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Deploy
cd web2
vercel

# Production deploy
vercel --prod

# URL: https://kopernikus-gis.vercel.app
```

### **Konfiguracija (vercel.json):**

```json
{
  "version": 2,
  "builds": [
    {
      "src": "index.html",
      "use": "@vercel/static"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "/$1"
    }
  ]
}
```

---

## 📄 Opcija 3: GitHub Pages (Free)

### **Prednosti:**
- ✅ **Free** - unlimited static hosting
- ✅ **GitHub integration** - auto deploy sa push
- ✅ **Custom domain** - može tvoj domen

### **Koraci:**

```bash
# 1. Kreiraj GitHub repo
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/username/kopernikus-gis.git
git push -u origin main

# 2. Enable GitHub Pages
# GitHub repo → Settings → Pages
# Source: Deploy from branch → main → /web2
# Save

# 3. Wait ~2 min
# URL: https://username.github.io/kopernikus-gis/
```

### **Custom Domain:**

```bash
# GitHub repo → Settings → Pages → Custom domain
# Add: your-domain.com

# DNS settings:
CNAME www username.github.io
A @ 185.199.108.153
A @ 185.199.109.153
A @ 185.199.110.153
A @ 185.199.111.153
```

---

## 🖥️ Opcija 4: cPanel Shared Hosting

### **Prednosti:**
- ✅ Već imaš hosting
- ✅ Puna kontrola nad fajlovima
- ✅ Može PHP/database (ako dodaš kasnije)

### **Koraci:**

#### **A) Preko File Manager:**

1. Login u cPanel
2. **File Manager** → `public_html/`
3. Kreiraj folder `kopernikus-gis/`
4. Upload sve fajlove iz `web2/` foldera
5. ✅ URL: `https://your-domain.com/kopernikus-gis/`

#### **B) Preko FTP:**

```bash
# FTP client (FileZilla, WinSCP)
Host: ftp.your-domain.com
Username: your-username
Password: your-password

# Upload:
Local: C:\Kopernikus-GIS\web2\*
Remote: /public_html/kopernikus-gis/

# Done!
```

#### **C) Preko SSH (ako imaš pristup):**

```bash
ssh user@your-domain.com

cd public_html
mkdir kopernikus-gis
cd kopernikus-gis

# Upload via scp from local machine:
scp -r web2/* user@your-domain.com:~/public_html/kopernikus-gis/
```

---

## 🐳 Opcija 5: Docker + VPS

### **Prednosti:**
- ✅ Full control
- ✅ Može backend servisi (ako treba)
- ✅ Scalable

### **Koraci:**

#### **A) Kreiraj Dockerfile:**

```dockerfile
# web2/Dockerfile
FROM nginx:alpine

# Copy files
COPY . /usr/share/nginx/html/

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
```

#### **B) Build & Run:**

```bash
# Build image
docker build -t kopernikus-gis-web2 .

# Run container
docker run -d -p 80:80 kopernikus-gis-web2

# URL: http://your-vps-ip/
```

#### **C) Docker Compose:**

```yaml
# docker-compose.yml
version: '3.8'

services:
  web:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./web2:/usr/share/nginx/html
    restart: always
```

```bash
docker-compose up -d
```

---

## ☁️ Opcija 6: AWS S3 + CloudFront

### **Prednosti:**
- ✅ Globalni CDN (brzo svuda)
- ✅ Scalable (milioni korisnika)
- ✅ Pay-as-you-go (jeftino za mali traffic)

### **Koraci:**

```bash
# 1. Kreiraj S3 bucket
aws s3 mb s3://kopernikus-gis

# 2. Upload fajlovi
aws s3 sync web2/ s3://kopernikus-gis/ --acl public-read

# 3. Enable static hosting
aws s3 website s3://kopernikus-gis/ --index-document index.html

# 4. URL: http://kopernikus-gis.s3-website-us-east-1.amazonaws.com/

# 5. (Opciono) Setup CloudFront CDN za HTTPS
```

---

## 🔐 Security Checklist

Pre deploy-a u produkciju:

### **1. Environment Variables:**
- ✅ `js/config.js` ima **Anon Key** (ne Service Role Key!)
- ✅ `.env` fajl nije commit-ovan (proveri `.gitignore`)

### **2. Supabase Security:**
- ✅ Row Level Security (RLS) je enabled
- ✅ Public read policy je kreiran
- ✅ Service Role Key nije exposed client-side

### **3. HTTPS:**
- ✅ Uvek koristi HTTPS (Netlify/Vercel automatski)
- ✅ Proveri SSL sertifikat (klikni bravu u browser-u)

### **4. Content Security Policy (CSP):**

Dodaj u `index.html` `<head>`:
```html
<meta http-equiv="Content-Security-Policy" content="
    default-src 'self';
    script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net;
    style-src 'self' 'unsafe-inline' https://unpkg.com;
    img-src 'self' data: https://*.tile.openstreetmap.org;
    connect-src 'self' https://*.supabase.co;
    font-src 'self' data:;
">
```

---

## 📊 Performance Optimization

### **1. Minify CSS/JS:**

```bash
# Install minifier
npm install -g uglify-js clean-css-cli

# Minify JS
uglifyjs js/*.js -o js/bundle.min.js

# Minify CSS
cleancss css/style.css -o css/style.min.css
```

### **2. Enable Compression:**

#### **Netlify (_headers file):**
```
/*
  Cache-Control: public, max-age=31536000
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
```

#### **Vercel (vercel.json):**
```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=31536000" }
      ]
    }
  ]
}
```

#### **Apache (.htaccess):**
```apache
<IfModule mod_deflate.c>
    AddOutputFilterByType DEFLATE text/html text/plain text/xml text/css text/javascript application/javascript
</IfModule>

<IfModule mod_expires.c>
    ExpiresActive On
    ExpiresByType text/css "access plus 1 year"
    ExpiresByType application/javascript "access plus 1 year"
</IfModule>
```

### **3. Lazy Load Images (ako dodaš slike):**

```html
<img src="image.jpg" loading="lazy" alt="Description">
```

---

## 🧪 Testing Pre Deploy-a

```bash
# 1. Lokalni test
cd web2
python -m http.server 8000
# → http://localhost:8000

# 2. Proveri sve linkove
# → Klikni na sve dugmad, index selector, tabelu

# 3. Testiranje različitih browser-a
# → Chrome, Firefox, Safari, Edge

# 4. Mobile testiranje
# → Chrome DevTools → Toggle Device Toolbar (Ctrl+Shift+M)

# 5. Performance test
# → Lighthouse (Chrome DevTools → Lighthouse → Run)
# → Target: 90+ score

# 6. Security test
# → https://observatory.mozilla.org/
# → Target: A+ grade
```

---

## 📈 Monitoring (Opciono)

### **1. Google Analytics:**

Dodaj u `index.html` pre `</head>`:
```html
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

### **2. Sentry (Error Tracking):**

```html
<script src="https://browser.sentry-cdn.com/7.x.x/bundle.min.js"></script>
<script>
  Sentry.init({
    dsn: "https://xxxxx@sentry.io/xxxxx",
    environment: "production"
  });
</script>
```

---

## ✅ Post-Deploy Checklist

- [ ] Site je live (proveri URL)
- [ ] HTTPS radi (zelena brava u browser-u)
- [ ] Mapa se učitava
- [ ] Granice parcele su vidljive
- [ ] Podaci se učitavaju iz Supabase-a
- [ ] Grafikon se prikazuje
- [ ] Zona distribucija se prikazuje
- [ ] Tabela ima podatke
- [ ] Index selector radi (NDVI/NDMI/NDRE)
- [ ] NDVI/NDMI/NDRE zone na mapi rade (GeoJSON iz data/)
- [ ] Responsive na mobile-u (proveri sa telefonom)
- [ ] Performance >80 (Lighthouse score)
- [ ] Nema greška u console-u (F12)

---

## 🆘 Troubleshooting Deploy Issues

### **Problem: "404 Not Found"**
```
✅ Solution:
- Proveri da li je index.html u root folderu
- Proveri putanje u HTML (src="/css/style.css" → src="css/style.css")
```

### **Problem: "Mixed Content" (HTTP/HTTPS)**
```
✅ Solution:
- Promeni sve http:// linkove u https://
- Ili koristi // (protocol-relative): //unpkg.com/leaflet
```

### **Problem: "CORS Error"**
```
✅ Solution:
- Supabase automatski handluje CORS
- Ako hosting ima dodatne restrictions, dodaj CORS headers
```

### **Problem: "Site loads but no data"**
```
✅ Solution:
- Proveri js/config.js credentials (F12 → Console)
- Proveri Supabase dashboard → Database → Tables → index_results
- Proveri da li je export_to_supabase.py pokrenuto
```

### **Problem: "NDVI/NDMI/NDRE zone se ne prikazuju"**
```
✅ Solution:
- Slojevi koriste GeoJSON iz data/ (ndvi_zones_1427_2.geojson, ndmi_zones_1427_2.geojson, ndre_zones_1427_2.geojson)
- Proveri da su fajlovi uploadovani i da su putanje relativne (data/...)
```

---

## 📁 Šta je u web2 folderu

Sve potrebno za deploy je u `web2/`:
- `index.html` – glavna stranica
- `css/style.css` – stilovi
- `js/config.js` – konfiguracija (Supabase, GeoServer)
- `js/app.js`, `charts.js`, `map.js`, `supabase-client.js` – logika
- `data/parcela_1427_2.geojson` – fallback geometrija parcele

**Eksterni resursi** (učitavaju se sa interneta):
- Leaflet, Chart.js, Supabase – CDN (unpkg, jsdelivr) – rade svuda
- Supabase – URL u config – radi svuda
- NDVI/NDMI/NDRE – GeoJSON iz `data/` – radi bez GeoServer-a

---

**Ready to deploy!** 🚀🌐✨

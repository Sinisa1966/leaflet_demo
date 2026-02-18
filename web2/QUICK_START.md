# Quick Start - 5 Minuta do Live Demo

⚡ **Brzo testiranje bez Supabase setup-a**

---

## 🎯 Cilj

Prikazati web2 app sa **dummy podacima** za brzo testiranje pre nego što se setup-uje Supabase.

---

## 🚀 Koraci

### **1. Pokreni Lokalni Server**

```bash
cd web2
python -m http.server 8000

# Ili ako nemaš Python:
# - Windows: Double-click index.html (otvoriće u browser-u)
# - Linux/Mac: open index.html
```

Otvori: http://localhost:8000

---

### **2. Vidi Greške u Console**

Otvori Developer Tools (F12) → Console

Videćeš:
```
❌ Supabase credentials nisu konfigurisani!
Edituj js/config.js i dodaj svoje credentials.
```

**Ovo je OK!** Aplikacija pokazuje strukturu i UI, samo nema prave podatke.

---

### **3. Privremeno Zaobiđi Supabase (Opciono)**

Ako želiš da vidiš kako bi izgledalo sa podacima **BEZ** Supabase setup-a:

#### **A) Kreiraj dummy podatke u `js/app.js`:**

Dodaj na vrh `KopernikausApp.init()` metode:

```javascript
async init() {
    console.log('🚀 Initializing Kopernikus GIS App...');
    
    // DUMMY MODE - zaobiđi Supabase
    this.useDummyData = true;
    
    if (this.useDummyData) {
        await this.loadDummyData();
        this.setupEventListeners();
        return;
    }
    
    // ... existing code ...
}
```

#### **B) Dodaj `loadDummyData()` metodu:**

```javascript
async loadDummyData() {
    console.log('📦 Loading dummy data...');
    
    // Parcel info
    this.parcelData = {
        parcel_id: '1427/2',
        municipality: 'Kovin',
        area_ha: 0.5,
        geometry: {
            type: 'Polygon',
            coordinates: [[[
                [21.1986, 44.8142],
                [21.2021, 44.8142],
                [21.2021, 44.8182],
                [21.1986, 44.8182],
                [21.1986, 44.8142]
            ]]]
        }
    };
    
    // Index results
    this.indexResults = {
        NDRE: { mean_value: 0.168, min_value: 0.105, max_value: 0.255, std_dev: 0.024, acquisition_date: '2026-02-04' },
        NDVI: { mean_value: 0.277, min_value: 0.184, max_value: 0.430, std_dev: 0.052, acquisition_date: '2026-02-04' },
        NDMI: { mean_value: -0.019, min_value: -0.087, max_value: 0.118, std_dev: 0.043, acquisition_date: '2026-02-04' }
    };
    
    // Update UI
    this.updateParcelInfo(this.parcelData);
    mapManager.loadParcelGeometry(this.parcelData);
    
    // Load dummy zones
    const dummyZones = mapManager.createDummyZones(this.parcelData.geometry);
    mapManager.loadZoneGeometries(dummyZones);
    
    this.updateCurrentStats('NDRE');
    
    // Dummy time series data
    const dummyTimeSeries = [
        { acquisition_date: '2025-11-21', mean_value: 0.145, min_value: 0.10, max_value: 0.20 },
        { acquisition_date: '2025-12-15', mean_value: 0.152, min_value: 0.11, max_value: 0.21 },
        { acquisition_date: '2026-01-10', mean_value: 0.160, min_value: 0.12, max_value: 0.23 },
        { acquisition_date: '2026-02-04', mean_value: 0.168, min_value: 0.105, max_value: 0.255 }
    ];
    
    chartsManager.createTimeSeriesChart('timeSeriesChart', dummyTimeSeries, 'NDRE');
    
    // Dummy table data
    const dummyTable = [
        { acquisition_date: '2026-02-04', index_type: 'NDRE', mean_value: 0.168, min_value: 0.105, max_value: 0.255, valid_pixels: 810, cloud_pixels: 0 },
        { acquisition_date: '2026-02-04', index_type: 'NDVI', mean_value: 0.277, min_value: 0.184, max_value: 0.430, valid_pixels: 810, cloud_pixels: 0 },
        { acquisition_date: '2026-02-04', index_type: 'NDMI', mean_value: -0.019, min_value: -0.087, max_value: 0.118, valid_pixels: 810, cloud_pixels: 0 }
    ];
    
    this.updateDataTable(dummyTable);
    
    console.log('✅ Dummy data loaded');
}
```

---

### **4. Refresh Browser**

Sada ćeš videti **kompletnu aplikaciju sa dummy podacima**:
- ✅ Mapa sa parcel boundary
- ✅ NDRE zone overlay (crvena/žuta/zelena)
- ✅ Grafikon sa vremenskom serijom
- ✅ Stats cards
- ✅ Zone distribution bar
- ✅ Data table

**Ovo je samo za DEMO svrhe!** Za pravu aplikaciju, nastavi sa Supabase setup-om.

---

## 📋 Pravi Setup (sa Supabase)

Kada si zadovoljan sa UI/UX, nastavi sa pravim setup-om:

### **1. Kreiraj Supabase Projekt**
→ https://supabase.com → Sign up → New Project

### **2. Run SQL Schema**
→ Kopiraj `supabase_schema.sql` → Paste u SQL Editor → Run

### **3. Konfiguriši `js/config.js`**
→ Dodaj svoj `SUPABASE_URL` i `anonKey`

### **4. Export Podataka**
```bash
pip install supabase psycopg2-binary

export SUPABASE_URL='...'
export SUPABASE_KEY='...'  # Service role key

python web2/export_to_supabase.py
```

### **5. Ukloni Dummy Mode**
→ Obriši `useDummyData` kod iz `js/app.js`

### **6. Refresh i Uživaj!**
→ Sada vidiš **prave podatke** iz Supabase-a

---

## 🎨 Prilagodi Dizajn

### **Promeni Boje:**

Edituj `css/style.css` → `:root` sekcija:

```css
:root {
    --primary-color: #2C3E50;     /* Dark blue */
    --secondary-color: #3498DB;   /* Light blue */
    --success-color: #27AE60;     /* Green */
    --warning-color: #F39C12;     /* Orange */
    --danger-color: #E74C3C;      /* Red */
}
```

### **Promeni Gradient:**

```css
body {
    background: linear-gradient(135deg, #FF6B6B 0%, #FFD93D 100%);
    /* Ili: */
    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
}
```

---

## 🌐 Deploy na Netlify (1 minut)

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Login
netlify login

# Deploy
cd web2
netlify deploy --prod

# URL: https://your-site-name.netlify.app
```

**DONE!** 🎉

---

## 📊 Šta Dalje?

1. ✅ Dodaj više parcela
2. ✅ Implementiraj date picker za custom opseg
3. ✅ Dodaj export to PDF
4. ✅ Setup email alerts
5. ✅ Dodaj user authentication

Pogledaj `README.md` za više detalja.

---

**Happy coding!** 🚀

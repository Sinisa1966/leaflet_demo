# Podsetnik: kako dodati novi WFS sloj (kao Opštine / Katastarske opštine)

**Kad god dodaješ novi vektorski sloj iz foldera (npr. shapefile), uradi TAČNO ove korake. Nemoj se vrteti u krug sa XML greškom – sloj mora biti uvezen u PostGIS i objavljen u GeoServeru pre nego što WFS može vratiti JSON.**

---

## 1. Backend (jednom): setup skripta

U **`scripts/setup_geoserver_local.ps1`** (Windows) dodaj redom:

1. **Kopiranje foldera u kontejner**
   ```powershell
   docker cp NAZIV_FOLDERA gis_db:/tmp/NAZIV_FOLDERA
   ```

2. **Import u PostGIS** (ogr2ogr)
   - Izvor: `/tmp/NAZIV_FOLDERA/IME_SHAPEFILE.shp`
   - Tabela: `public.IME_TABELE` (npr. `katop_lat`, `kat_opstine`)
   - Koordinatni sistem: `-t_srs EPSG:4326`, `-nlt PROMOTE_TO_MULTI`, `-overwrite`

3. **GeoServer datastore**
   - Ime datastora = ime tabele (npr. `kat_opstine`)
   - Tip: PostGIS, konekcija na `db`, baza `moj_gis`, schema `public`

4. **GeoServer feature type (sloj)**
   - **name** (javno ime sloja): npr. `KatOp_Kat` – ovo ide u WFS typeName
   - **nativeName** = ime tabele (npr. `kat_opstine`)
   - SRS: EPSG:4326, nativeBoundingBox za Srbiju (minx 18, maxx 23, miny 42, maxy 47)

WFS za workspace već uključuje postojeći korak (enable_wfs_workspace.py); ne izmišljaj nove načine.

---

## 2. Frontend: leaflet_demo.html

1. **WFS URL**
   - `geoserverBase + "/moj_projekat/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=moj_projekat:IME_SLOJA&outputFormat=application/json&srsName=EPSG:4326&format_options=CHARSET:UTF-8"`
   - `IME_SLOJA` = **name** iz feature type (npr. `KatOp_Kat`).

2. **Varijable**
   - `var slojLayer;` i `var slojLoaded = false;`

3. **Stil** (funkcija kao `styleOpstina`)
   - npr. `color: "#2c5282", weight: 2, fillOpacity: 0, opacity: 0.8`

4. **onEachFeature**
   - Iz property-ja izvući ime (ImeKOLatV, Naziv, name, itd.), fallback kroz sva string polja; za prikaz: `fixSrpski(ime)`; popup samo ime; mouseover/mouseout sa `slojLayer.resetStyle(e.target)`.

5. **Kreiranje sloja**
   - `slojLayer = L.geoJSON(null, { style: styleSloj, onEachFeature: onEachFeatureSloj });`

6. **Kontrola slojeva**
   - `layerControl.addOverlay(slojLayer, "Naziv u meniju");`

7. **Učitavanje**
   - `function loadSloj() { if (slojLoaded) return; slojLoaded = true; fetchWfsJson(wfsUrlSloj).then(...).catch(...); }`

8. **overlayadd**
   - `} else if (e.layer === slojLayer) { loadSloj(); }`

---

## 3. Provera

| Šta proveriti | Gde |
|---------------|-----|
| Tabela u PostGIS | `docker exec gis_db psql -U admin -d moj_gis -c "\dt public.kat_opstine"` |
| Datastore u GeoServeru | Data → Stores → moj_projekat → kat_opstine |
| Feature type (sloj) | Data → Layers → KatOp_Kat (name = typeName u WFS) |
| WFS vraća JSON | Otvori u browseru: `.../ows?service=WFS&version=1.0.0&request=GetFeature&typeName=moj_projekat:KatOp_Kat&outputFormat=application/json&...` |

---

## 4. Ako i dalje dobijaš XML

- **Uvek prvo pokreni setup:** `.\scripts\setup_geoserver_local.ps1`
- XML znači: sloj ne postoji ili WFS nije uključen za workspace. Rešenje je **backend** (import + publish), ne menjanje frontenda u krug.

---

## Tabela: postojeći slojevi (za copy-paste logiku)

| Sloj u meniju        | typeName (WFS) | Tabela (PostGIS) | Folder / shapefile        |
|----------------------|----------------|------------------|---------------------------|
| Opštine              | KatOp_Lat      | katop_lat        | opstine/Op_Lat.shp        |
| Katastarske opštine  | KatOp_Kat      | kat_opstine      | kat-opstine/KatOp_Lat.shp |
| Pancevo-adrese       | pancevo_adrese | pancevo_adrese   | Pancevo-adrese/PancevoDKP.shp |
| DKP-Vrsac            | vrsac_dkp_pg   | vrsac_dkp_pg     | DKP-Vrsac/...             |

Isti pipeline za svaki novi sloj: **folder → ogr2ogr → tabela → datastore → feature type → WFS URL u mapi.**

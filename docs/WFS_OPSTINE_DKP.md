# Kako rade DKP i Opštine (WFS slojevi)

**→ Za dodavanje novog WFS sloja korak-po-korak v.** [PODSETNIK_NOVI_WFS_SLOJ.md](PODSETNIK_NOVI_WFS_SLOJ.md) **– da se ne vrtiš u krug sa XML greškom.**

Svi slojevi (DKP-Vrsac, DKP-Kovin, Opštine, Katastarske opštine, itd.) rade **na isti način**:

1. **Klik na sloj** u kontroli → poziva se npr. `loadDkp()` ili `loadOpstineLat()`.
2. **Frontend šalje WFS zahtev** na GeoServer, npr.:
   - DKP: `.../ows?service=WFS&version=1.0.0&request=GetFeature&typeName=moj_projekat:vrsac_dkp_pg&outputFormat=application/json&...`
   - Opštine: `.../ows?service=WFS&version=1.0.0&request=GetFeature&typeName=moj_projekat:KatOp_Lat&outputFormat=application/json&...`
3. **GeoServer** mora:
   - imati **WFS uključen** za workspace `moj_projekat` (inače vraća XML grešku "Service null is disabled"),
   - imati **sloj objavljen** (feature type sa tim imenom i tabelom u PostGIS).

Ako to nije urađeno, GeoServer vraća **XML** (ServiceException), a ne JSON – zato se javlja poruka "WFS je vratio XML umesto JSON".

---

## Zašto DKP radi, a Opštine ne?

- **DKP** – na serveru/localu je već pokrenut setup koji je: uvezao DKP shapefile-ove u PostGIS (tabele `vrsac_dkp_pg`, `kovin_dkp_pg`, `pancevo_dkp_pg`), kreirao GeoServer datastore i feature type za svaki, i (na serveru) uključio WFS za workspace. Zato WFS za `vrsac_dkp_pg` itd. vraća **JSON**.
- **Opštine** – sloj **KatOp_Lat** (tabela `katop_lat`, iz `opstine/Op_Lat.shp`) se kreira istim setup skriptama, ali setup **mora biti pokrenut** (lokalno ili na serveru). Ako nisi pokrenuo/ponovo pokrenuo setup posle dodavanja opština, tabela i sloj ne postoje → GeoServer vraća **XML** grešku.

---

## Šta uraditi da Opštine rade kao DKP

**Lokalno (Windows):**

1. U korenu projekta pokreni:
   ```powershell
   .\scripts\setup_geoserver_local.ps1
   ```
   To: kopira `opstine/` i `kat-opstine/` u kontejner, uvozi shapefile-ove u PostGIS (`katop_lat`, `kat_opstine`), kreira GeoServer datastore i objavljuje slojeve **KatOp_Lat** i **KatOp_Kat**, i uključuje WFS za workspace.
2. Osveži mapu i uključi sloj **Opštine** ili **Katastarske opštine**.

**Na serveru (Hetzner):**

- Pokreni na serveru (SSH):  
  `cd /root/kopernikus-gis && bash scripts/setup_geoserver_hetzner.sh`  
  (uvezi opštine i objavi KatOp_Lat; WFS je već uključen ako si ranije pokrenuo `enable_wfs_workspace.py`).

---

## Rezime

| Sloj                 | typeName u WFS   | Tabela u PostGIS | Izvor podataka              |
|----------------------|------------------|------------------|-----------------------------|
| DKP-Vrsac            | vrsac_dkp_pg     | vrsac_dkp_pg     | DKP-Vrsac/VrsacDKP.shp      |
| DKP-Kovin            | kovin_dkp_pg     | kovin_dkp_pg     | DKP-Kovin/KovinDKP.shp      |
| Opštine              | **KatOp_Lat**    | **katop_lat**    | **opstine/Op_Lat.shp**     |
| Katastarske opštine  | **KatOp_Kat**    | **kat_opstine**  | **kat-opstine/KatOp_Lat.shp** |
| Pancevo-adrese       | **pancevo_adrese** | **pancevo_adrese** | **Pancevo-adrese/PancevoDKP.shp** |

Isti mehanizam – razlika je samo u tome da li je za taj sloj urađen import i publish u setup skripti i da li je WFS uključen.

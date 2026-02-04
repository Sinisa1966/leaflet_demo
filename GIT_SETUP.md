# Git Setup - Kopernikus-GIS

## Trenutno stanje
- Git repozitorijum je inicijalizovan
- Commit je napravljen sa izmenama za NDVI/NDMI/NDRE display logiku

## Kako da povežeš sa GitHub repozitorijumom

### Opcija 1: Ako već imaš GitHub repozitorijum

```powershell
# Poveži sa postojećim GitHub repozitorijumom
git remote add origin https://github.com/TVOJ_USERNAME/Kopernikus-GIS.git

# Push-uj izmene
git push -u origin master
```

### Opcija 2: Ako treba da napraviš novi GitHub repozitorijum

1. Idi na https://github.com i napravi novi repozitorijum (npr. `Kopernikus-GIS`)
2. **NE** inicijalizuj README, .gitignore ili license (već imamo)
3. Zatim pokreni:

```powershell
# Poveži sa novim GitHub repozitorijumom
git remote add origin https://github.com/TVOJ_USERNAME/Kopernikus-GIS.git

# Push-uj izmene
git push -u origin master
```

### Opcija 3: Ako koristiš SSH

```powershell
git remote add origin git@github.com:TVOJ_USERNAME/Kopernikus-GIS.git
git push -u origin master
```

## Šta je urađeno u ovom commitu

- **leaflet_demo.html**: 
  - Vraćena originalna logika za NDMI i NDRE (prikazuje sve redove iz CSV-a)
  - Dodata posebna logika za NDVI (prikazuje sve podatke sortirane od najnovijeg ka starijim)
  - Ispravljen problem gde su NDMI i NDRE prikazivali prazno kada pickLatestGood vraća null

- **.gitignore**: 
  - Dodat .gitignore da ne commit-uje nepotrebne fajlove (cache, .env, __pycache__, itd.)

## Budući commit-i

Kada praviš nove izmene:

```powershell
# Proveri status
git status

# Dodaj izmenjene fajlove
git add <fajl1> <fajl2>

# Napravi commit
git commit -m "Opis izmena"

# Push-uj na GitHub
git push
```

## Važno!

- **NE commit-uj** `.env` fajlove (sadrže tajne)
- **NE commit-uj** velike CSV/TIFF fajlove ako nisu potrebni (dodati u .gitignore)
- **Commit-uj** samo izvorni kod i konfiguraciju

# Smart OCR — Guida all'Addestramento

> Questa guida descrive il processo completo per calibrare il sistema e addestrare il classificatore SVM per il riconoscimento automatico dei questionari CBCL 6-18.

---

## Prerequisiti

- Python 3.11 con virtual environment attivato
- Dipendenze installate (`pip install -r requirements.txt`)
- Almeno 1 foto di un questionario CBCL (vuoto o compilato) per la calibrazione
- Per il training: foto di questionari compilati oppure immagini generate da AI

```bash
cd smart_ocr
source venv/bin/activate
```

---

## Fase 1 — Calibrazione della Griglia (una sola volta)

La calibrazione mappa le posizioni delle 357 celle (119 item x 3 colonne) sul foglio CBCL. Si fa **una volta sola** e vale per tutti i questionari dello stesso formato.

### 1.1 Avvia il tool di calibrazione

```bash
streamlit run training/label_tool.py
```

### 1.2 Tab "Calibra"

1. Seleziona la pagina da calibrare (`page_4` o `page_5`)
2. Carica una foto del questionario CBCL (vuoto o compilato, ben illuminato)
3. **Clicca 5 punti** sulla foto nell'ordine:
   - **Punto 1**: centro della cella colonna 0 del **primo item** colonna sinistra (item 1 per page_4, item 57 per page_5)
   - **Punto 2**: centro della cella colonna 0 dell'**ultimo item** colonna sinistra (item 34 per page_4, item 90 per page_5)
   - **Punto 3**: centro della cella colonna 0 del **primo item** colonna destra (item 35 per page_4, item 91 per page_5)
   - **Punto 4**: centro della cella colonna 0 dell'**ultimo item** colonna destra (item 56h per page_4, item 112 per page_5)
   - **Punto 5**: centro della cella **colonna 2** dello stesso item del punto 1 (serve per calcolare la spaziatura tra le colonne 0, 1, 2)
4. Regola larghezza/altezza cella se necessario (i valori di default sono stime per A4)
5. Verifica l'**overlay** in anteprima: i rettangoli colorati devono coincidere con le celle reali
6. Clicca **"Salva calibrazione"**

### 1.3 Ripeti per l'altra pagina

Il CBCL 6-18 ha due pagine di risposte:
- `page_4`: items 1-34 (colonna sx) + items 35-55, 56a-56h (colonna dx) = 63 items
- `page_5`: items 57-90 (colonna sx) + items 91-112 (colonna dx) = 56 items

### 1.4 Verifica

Vai alla tab **"Verifica"**, carica una foto diversa e controlla che l'overlay sia allineato.

> **Nota**: Se cambi modello/formato di questionario CBCL, devi ricalibrare.

---

## Fase 2 — Uso Immediato (senza training)

Dopo la calibrazione, il sistema funziona **subito** con il metodo OMR (pixel-counting):

```bash
streamlit run app.py
```

oppure con l'app desktop:

```bash
python desktop_app.py
```

1. Carica una foto del questionario compilato
2. Seleziona la pagina
3. Clicca "Analizza"
4. Il sistema rileva automaticamente le risposte contando i pixel scuri in ogni cella

**Accuratezza stimata OMR**: 85-94% (dipende dalla qualità della foto e dalla calligrafia)

---

## Fase 3 — Raccolta Dati di Training

Per migliorare l'accuratezza, addestra il classificatore SVM. Servono **minimo 30 immagini per classe** (cerchio, x_rossa, vuoto). Ci sono 3 modi per ottenere i dati:

### Metodo A — Generazione automatica di celle sintetiche (il più veloce)

Il generatore crea celle 64x64 realistiche con cerchi, X e celle vuote.

```bash
# Genera 500 celle per classe (1500 totali)
python training/cell_generator.py --n 500

# Per generare e copiare direttamente nelle cartelle di training:
python training/cell_generator.py --n 500 --merge
```

Le celle vengono salvate in `data/generated/{cerchio,x_rossa,vuoto}/`.

### Metodo B — Auto-labeling da foto reali (il più accurato)

Fotografa questionari CBCL compilati e il sistema estrae e classifica le celle automaticamente.

```bash
# Metti le foto in una cartella, es: foto_cbcl/
python training/import_tool.py --auto-label foto_cbcl/ --page page_4
python training/import_tool.py --auto-label foto_cbcl/ --page page_5
```

Il sistema:
1. Preprocessa ogni foto
2. Estrae tutte le celle dalla griglia calibrata
3. Classifica ogni cella con OMR
4. Salva solo le celle con alta confidence in `data/raw_cells/{classe}/`
5. Scarta le celle ambigue

**Consiglio**: usa 5-10 foto di questionari diversi per avere varietà di calligrafie.

### Metodo C — Immagini generate da AI

Puoi usare DALL-E, Midjourney o qualsiasi AI per generare immagini di:
- Numeri cerchiati a mano (classe: `cerchio`)
- Segni X su numeri (classe: `x_rossa`)
- Celle vuote con numeri stampati (classe: `vuoto`)

Organizza le immagini in cartelle:

```
immagini_ai/
├── cerchio/     ← immagini di celle cerchiate
├── x_rossa/     ← immagini di celle con X
└── vuoto/       ← immagini di celle vuote
```

Poi importa:

```bash
python training/import_tool.py --from-ai immagini_ai/
```

Le immagini vengono ridimensionate a 64x64 e copiate in `data/raw_cells/`.

### Metodo D — Labeling manuale (il più preciso)

Usa il tool interattivo per etichettare cella per cella:

```bash
streamlit run training/label_tool.py
```

Tab **"Etichetta"**: carica foto, naviga tra gli item, per ogni cella seleziona la classe e salva.

### Combinare i metodi

I metodi si possono combinare liberamente. Per esempio:

```bash
# 1. Genera 200 celle sintetiche come base
python training/cell_generator.py --n 200 --merge

# 2. Aggiungi celle reali da 5 foto
python training/import_tool.py --auto-label foto_reali/ --page page_4

# 3. Aggiungi celle AI
python training/import_tool.py --from-ai immagini_ai/
```

### Verifica dataset

Per vedere quante celle hai per classe:

```bash
python training/import_tool.py --stats
```

Output esempio:
```
📊 Dataset di training corrente:
   cerchio     :   350 ████████████████████████████████████
                     (manual:20, generated:200, auto:80, ai:50)
   x_rossa     :   280 ████████████████████████████
                     (generated:200, auto:30, ai:50)
   vuoto       :   420 ██████████████████████████████████████████
                     (generated:200, auto:170, ai:50)

   Totale: 1050
   ✅ Dataset pronto per il training!
```

---

## Fase 4 — Data Augmentation (opzionale ma consigliato)

Dopo aver raccolto le celle base, genera varianti per rendere il modello più robusto:

```bash
python training/augmentor.py --n 15
```

Per ogni cella reale in `data/raw_cells/`, genera 15 varianti in `data/synthetic/` con:
- Rotazione ±15°
- Variazione luminosità/contrasto
- Sfocatura lieve
- Rumore gaussiano
- Distorsione prospettica
- Variazione spessore tratto

---

## Fase 5 — Training del Modello SVM

Quando hai almeno 30 celle per classe (idealmente 100+):

```bash
python training/train_svm.py
```

Il training:
1. Carica tutte le celle da `data/raw_cells/` + `data/synthetic/` + `data/generated/`
2. Estrae features HOG (1764 dimensioni) per ogni cella
3. Addestra un SVM con kernel RBF (C=10, gamma=scale, probability=True)
4. Esegue cross-validation 5-fold
5. Salva il modello in `models/model.pkl`
6. Salva il report in `models/training_report.json`

### Output atteso

```
📈 Risultati Cross-Validation:
   Accuracy media: 0.9234 ± 0.0156
   Per fold: ['0.9100', '0.9350', '0.9200', '0.9150', '0.9370']

✅ Accuracy 92.3% soddisfa il target 88.0%
✅ Modello salvato: models/model.pkl
```

### Se l'accuracy è bassa (< 88%)

- Aggiungi più celle reali (specialmente casi difficili)
- Aumenta il numero di varianti in augmentor (`--n 25`)
- Verifica la qualità delle etichette (errori di classificazione)
- Bilancia le classi (stesso numero circa per ogni classe)

---

## Fase 6 — Uso con Modello Addestrato

Dopo il training, l'app usa **automaticamente il modello SVM** al posto dell'OMR:

```bash
streamlit run app.py
# oppure
python desktop_app.py
```

Nella sidebar vedrai: **"🧠 Modello SVM caricato"** invece di "🤖 Modalità OMR".

---

## Fase 7 — Miglioramento Continuo

Il modello migliora nel tempo aggiungendo nuovi dati:

1. Quando trovi errori di riconoscimento, etichetta manualmente le celle problematiche
2. Rigenera dati sintetici
3. Ri-addestra il modello

```bash
# Aggiungi nuove foto
python training/import_tool.py --auto-label nuove_foto/

# Rigenera augmentation
python training/augmentor.py --n 15

# Ri-addestra
python training/train_svm.py
```

Il nuovo modello sovrascrive `models/model.pkl` e l'app lo usa immediatamente.

---

## Riepilogo Comandi

| Comando | Scopo |
|---------|-------|
| `streamlit run training/label_tool.py` | Calibrazione + labeling |
| `streamlit run app.py` | App principale (browser) |
| `python desktop_app.py` | App principale (finestra nativa) |
| `python training/cell_generator.py --n 500 --merge` | Genera celle sintetiche |
| `python training/import_tool.py --auto-label cartella/` | Auto-labeling da foto |
| `python training/import_tool.py --from-ai cartella/` | Import celle da AI |
| `python training/import_tool.py --stats` | Statistiche dataset |
| `python training/augmentor.py` | Data augmentation |
| `python training/train_svm.py` | Addestra modello SVM |

---

## Struttura Cartelle Dati

```
data/
├── raw_cells/          ← Celle etichettate (tutte le sorgenti)
│   ├── cerchio/        ← Celle con numero cerchiato
│   ├── x_rossa/        ← Celle con segno X
│   ├── vuoto/          ← Celle vuote
│   └── ambiguo/        ← Celle dubbie (non usate nel training)
├── synthetic/          ← Varianti augmented (generate da augmentor.py)
│   ├── cerchio/
│   ├── x_rossa/
│   └── vuoto/
└── generated/          ← Celle generate da cell_generator.py
    ├── cerchio/
    ├── x_rossa/
    └── vuoto/
```

---

*Smart OCR Training Guide v1.0 — Marzo 2026*

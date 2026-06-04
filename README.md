# Course Manager

Applicazione web interna per gestione semplificata di corsi, materiali didattici, iscritti, iscrizioni e stato di completamento. È pensata per server Linux on-premise, con SQLite locale e file salvati su filesystem.

## Funzionalità

- Login interna con utenti `admin` e `viewer`.
- Dashboard con conteggi principali e ultime attività.
- CRUD corsi, archiviazione e cancellazione bloccata se esistono iscrizioni.
- Gestione corsi su Excel con inserimento, modifica, archiviazione e cancellazione su un foglio dedicato `Corsi`.
- Upload, download ed eliminazione materiali per corso.
- CRUD iscritti con email univoca e cancellazione bloccata se esistono iscrizioni.
- Iscrizioni corso/iscritto con vincolo di unicità.
- Stato iscrizione `completato` / `non_completato`.
- Se un’iscrizione passa a `completato`, `data completamento` viene valorizzata se vuota.
- Se torna a `non_completato`, `data completamento` viene svuotata.
- Export CSV corsi, iscritti e iscrizioni.
- Import CSV iscritti e import CSV iscrizioni.
- API REST FastAPI con Swagger su `/docs`.

## Requisiti

- Python 3.11 o superiore
- Linux server o ambiente locale equivalente
- Nessun servizio esterno obbligatorio

## Installazione locale

```bash
cd course-manager
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Per sviluppo locale puoi modificare `.env` così:

```env
APP_ENV=development
SECRET_KEY=dev-secret-change-me
DATABASE_URL=sqlite:///./data/app.db
COURSE_FILES_DIR=./storage
EXCEL_COURSES_PATH=./data/corsi.xlsx
EXCEL_COURSES_SHEET=Corsi
```

## Configurazione produzione

Esempio `.env` per server on-premise:

```env
APP_NAME=Course Manager
APP_ENV=production
SECRET_KEY=imposta-una-stringa-lunga-casuale
DATABASE_URL=sqlite:////opt/course-manager/data/app.db
COURSE_FILES_DIR=/opt/course-manager/storage
MAX_UPLOAD_MB=50
ALLOWED_EXTENSIONS=pdf,doc,docx,ppt,pptx,xls,xlsx,png,jpg,jpeg,zip
EXCEL_COURSES_PATH=/opt/course-manager/data/corsi.xlsx
EXCEL_COURSES_SHEET=Corsi
ADMIN_DEFAULT_USERNAME=admin
ADMIN_DEFAULT_PASSWORD=change-me-on-first-login
```

Crea le directory e assegna permessi all’utente di servizio:

```bash
sudo mkdir -p /opt/course-manager/data /opt/course-manager/storage
sudo chown -R course-manager:course-manager /opt/course-manager
```

## Creazione database

Il progetto usa `Base.metadata.create_all`, quindi Alembic non è necessario per l’installazione iniziale.

```bash
source .venv/bin/activate
python -m app.cli init-db
```

## Creazione primo admin

Metodo interattivo:

```bash
python -m app.cli create-admin --username admin
```

Metodo non interattivo:

```bash
python -m app.cli create-admin --username admin --password 'password-molto-lunga'
```

Se l’utente esiste già, il comando lo promuove ad admin e aggiorna la password.

## Avvio in development

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Apri:

- UI: `http://127.0.0.1:8000`
- Swagger/OpenAPI: `http://127.0.0.1:8000/docs`

## Avvio in produzione

Con Gunicorn e worker Uvicorn:

```bash
source .venv/bin/activate
gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --workers 2
```

Per un servizio `systemd`, imposta `WorkingDirectory` sulla cartella `course-manager`, carica le variabili da `.env` oppure esportale nell’unità, e avvia il comando `gunicorn` sopra.

## Storage materiali

La variabile `COURSE_FILES_DIR` definisce la directory dei materiali. Ogni corso usa una sottocartella `course_<id>`.

Le protezioni implementate:

- uso del nome file originale solo come metadato;
- salvataggio con nome UUID;
- rimozione componenti di percorso dal nome originale;
- verifica che il file finale resti dentro `COURSE_FILES_DIR`;
- validazione estensione e dimensione massima.

## Gestione corsi Excel

La voce di menu `Corsi Excel` legge e scrive un foglio normalizzato nel workbook configurato con `EXCEL_COURSES_PATH`.

Il foglio usato dall'applicativo è `Corsi` per default e contiene queste colonne:

```csv
id,titolo,descrizione_breve,categoria,durata,stato,data_creazione,data_aggiornamento
```

Se il workbook esiste già ma il foglio `Corsi` non esiste, l'app lo crea senza cancellare gli altri fogli. Nel caso del file calendario fornito, i titoli presenti in `Foglio3` vengono usati per popolare la prima anagrafica corsi.

Per usare il file indicato localmente:

```env
EXCEL_COURSES_PATH=C:\Users\Utente\Downloads\Formazione dta 2024).xlsx
EXCEL_COURSES_SHEET=Corsi
```

Per popolare o aggiornare il database con corsi, iscritti e iscrizioni presenti nell'Excel:

```bash
python -m app.cli import-excel-courses
```

Il comando usa `EXCEL_COURSES_PATH` e `EXCEL_COURSES_SHEET`. Puoi anche passare il file esplicitamente:

```bash
python -m app.cli import-excel-courses --path "/percorso/Formazione dta 2024).xlsx"
```

Il comando è idempotente: abbina i corsi per titolo, crea quelli mancanti e aggiorna quelli già presenti. Legge anche i partecipanti in colonna A dei blocchi calendario, crea iscritti con email tecnica generata e crea le iscrizioni ai corsi. I valori del calendario come `GRIMANI`, `DOCENTE ESTERNO`, `ONLINE` e `PRESENZA` vengono salvati nelle note dell'iscrizione.

Per importare solo l'anagrafica corsi:

```bash
python -m app.cli import-excel-courses --only-courses
```

Per vedere cosa farebbe senza scrivere nel database:

```bash
python -m app.cli import-excel-courses --dry-run
```

Esempio dopo un `git pull` sul server:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m app.cli init-db
python -m app.cli import-excel-courses
```

## Import CSV

Import iscritti, colonne minime:

```csv
nome,cognome,email,telefono,azienda_ente,note
Mario,Rossi,mario.rossi@example.com,333123456,Azienda,Nota
```

Import iscrizioni:

```csv
corso_titolo,corso_id,email_iscritto,stato,note
Sicurezza,,mario.rossi@example.com,non_completato,
```

Puoi usare `corso_id` oppure `corso_titolo`. Gli stati validi sono `completato` e `non_completato`.

## API

Endpoint principali:

- `/api/auth`
- `/api/courses`
- `/api/students`
- `/api/enrollments`
- `/api/materials`
- `/api/export/*.csv`
- `/api/import/*`

Le API usano la stessa sessione cookie della UI. Swagger è disponibile su `/docs`.

## Backup

Ferma l’applicazione o assicurati che non siano in corso scritture, poi salva:

```bash
sqlite3 /opt/course-manager/data/app.db ".backup '/backup/course-manager/app-$(date +%F).db'"
tar -czf /backup/course-manager/storage-$(date +%F).tar.gz /opt/course-manager/storage
```

In alternativa puoi copiare l’intera directory `/opt/course-manager`, includendo `data` e `storage`.

## Test

```bash
source .venv/bin/activate
pytest
```

## Troubleshooting

- `no such table`: esegui `python -m app.cli init-db` dalla directory del progetto.
- Login non disponibile: crea l’admin con `python -m app.cli create-admin --username admin`.
- Upload fallito: verifica `COURSE_FILES_DIR`, permessi filesystem, estensione e `MAX_UPLOAD_MB`.
- Cookie non mantenuto in produzione: con `APP_ENV=production` il cookie è `https_only`; usa HTTPS oppure imposta `APP_ENV=development` solo in ambienti non produttivi.
- Database non scrivibile: controlla proprietario e permessi della directory configurata in `DATABASE_URL`.


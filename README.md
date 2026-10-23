Sound_pass/
├── README.md
├── CONTRIBUTING.md                 # Cómo trabajar en el proyecto paso a paso
├── docker-compose.yml
├── .github/
│   ├── ISSUE_TEMPLATE/             # Plantillas: historia, bug y feedback externo
│   └── workflows/
│       ├── ci.yml
│       ├── project-automation.yml
│       ├── commits.yml
│       └── deploy.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   └── src/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── models.py
│       ├── schemas.py
│       ├── spotify.py
│       ├── wikipedia.py
│       ├── ticketmaster.py
│       ├── ticket_pdf.py
│       ├── security.py
│       └── routers/
│           ├── auth.py
│           ├── concerts.py
│           ├── venues.py
│           ├── orders.py
│           └── tickets.py
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── database/
│   ├── schema.sql
│   ├── seed.sql
│   └── migrations/
│       └── 001_issued_tickets.sql
└── docs/
    ├── api-wikipedia.md
    ├── bitacora.md                 # Errores, causas, soluciones, pros y contras
    └── feedback-externo.md         # Pruebas con usuarios fuera del equipo

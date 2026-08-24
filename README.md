# AML Case Workflow Map

Interactive, collapsible workflow map for managing a high volume of AML cases.

## What it models

`Portfolio → Queue → Case → Workflow step`

- **Priority queues:** P1 urgent, P2 high-risk, P3 routine.
- **Stage gates:** intake, triage, investigation, decision, reporting and closure.
- **Ownership:** analysts, investigators, quality assurance and MLRO review.
- **Controls:** SLA, escalation and evidence requirements appear on every expanded step.

Read [the workflow design](WORKFLOW-DESIGN.md) for the case lifecycle, risk-based routing rules, performance measures, and regulatory-design references behind the map.

The displayed case references and values are fictional demonstration data. Do not put PII, account numbers, transaction details, SAR narratives, or production credentials in this repository.

## Run locally

Open `index.html` in a browser, or serve the folder:

```bash
python3 -m http.server 8080
```

Then visit `http://localhost:8080`.

## Update the workflow

Edit the `workflow` object at the top of `app.js`. Each node has `name`, `meta`, `status`, `children`, and optional `detail` fields. The visual automatically redraws when a node is expanded or collapsed.

## Push to GitHub

Create an empty GitHub repository, then run these commands from this folder:

```bash
git init
git add .
git commit -m "Add AML workflow map"
git branch -M main
git remote add origin https://github.com/YOUR-ORG/YOUR-REPO.git
git push -u origin main
```

For a team workflow, keep the workflow definition free of confidential data and connect it later to an approved internal case-management API.

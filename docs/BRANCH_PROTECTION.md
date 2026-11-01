# Schutz von `main` (einmalig in GitHub einzurichten)

Direkte Pushes auf `main` sind aktuell technisch möglich. Empfohlene Regel unter
Settings → Rules → Rulesets → New branch ruleset (Ziel: `main`):

- Require a pull request before merging
- Require status checks to pass: `audit-checks`
- Block force pushes
- Restrict deletions

Nachweis des Teststands: Der Job `audit-checks` schreibt die pytest-Zusammenfassung
(Anzahl bestandener Tests pro Commit) in die Job-Summary des jeweiligen Actions-Laufs.

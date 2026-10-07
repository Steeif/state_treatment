# state_treatment

Frappe app for state-funded treatment recommendations. Requires Frappe/ERPNext v14+ and the Healthcare app.

## Install

```bash
bench --site [site-name] install-app state_treatment
bench --site [site-name] migrate
bench restart
```

The migration imports the ministry-provided breast cancer protocol master data from `state_treatment/data/breast_cancer_protocols.json`. That file is intentionally excluded from Git and must be provisioned locally by an authorized administrator before migration.

The app provides the State Treatment Recommendation, Recommendation Protocol Item, and Administrative Letter DocTypes; recommendation workflow and official print format fixtures; and Sales Invoice validation against approved recommendations.

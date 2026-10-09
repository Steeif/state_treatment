# state_treatment

Frappe app for state-funded treatment recommendations. Target versions: Frappe Framework v15.117.0, ERPNext v15.97.0, and Healthcare v15.2.1.

## Install

```bash
bench --site [site-name] install-app state_treatment
bench restart
```

The restricted protocol master data is intentionally excluded from Git. Installation does not require it. An authorized administrator must provision the JSON file on the server and import it explicitly after installation:

```bash
bench --site [site-name] execute state_treatment.patches.v1_0.import_breast_cancer_protocols.execute --kwargs '{"file_path":"/secure/path/breast_cancer_protocols.json"}'
```

The default file path is `state_treatment/data/breast_cancer_protocols.json`, which is ignored by Git. Do not commit the source data or patient records to this public repository.

The app provides the State Treatment Recommendation, Recommendation Protocol Item, and Administrative Letter DocTypes; recommendation workflow and official print format fixtures; and Sales Invoice submission validation against approved recommendations. The linked Healthcare Service Unit DocType and Patient DocType must be available from the installed Healthcare app.

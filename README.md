# Class Git Forge

Class Git Forge is an internal Docker-hosted tool for helping authorised staff validate
and provision GitLab assignment repositories at scale.

The current base layer provides a Flask web app for validating CSV inputs. Destructive
GitLab provisioning is intentionally not implemented yet.

## Quick Start

```bash
scripts/dev init
scripts/dev up
```

The command prints the local app URL. Open that URL and upload a CSV using one of the
supported formats.

Set real GitLab credentials in `.env` before adding or using GitLab API validation:

```env
GITLAB_URL="https://gitlab.example.edu.au"
GITLAB_TOKEN="your_token_here"
```

## CSV Formats

Group-based projects:

```csv
project_path,project_name,student_id
team-01,PA2621 Team 01,22048668
team-01,PA2621 Team 01,22049321
team-01,PA2621 Team 01,22050119
team-02,PA2621 Team 02,22051234
team-02,PA2621 Team 02,22054567
team-02,PA2621 Team 02,22057890
```

Individual projects:

```csv
student_id,project_path,project_name
22048668,22048668,PA2621 - 22048668
22049321,22049321,PA2621 - 22049321
```

## Local Checks

```bash
python -m compileall app
pytest
```

Or run the Docker-backed check:

```bash
scripts/dev check
```

## Generated Data

Generated uploads, reports, and audit logs live under `data/`. Directory placeholders
are committed, but generated contents are ignored by git.

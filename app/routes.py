from __future__ import annotations

from flask import Blueprint, current_app, render_template, request

from app.audit import write_audit_event
from app.csv_parser import CsvParseError, parse_projects_csv
from app.provisioner import build_validation_preview
from app.reports import validation_response
from app.validators import validate_project_rows


bp = Blueprint("routes", __name__)


@bp.get("/")
def index():
    return render_template("validate.html", result=None, error=None)


@bp.get("/health")
def health():
    return {"status": "ok", "service": "class-git-forge"}


@bp.get("/validate")
def validate_form():
    return render_template("validate.html", result=None, error=None)


@bp.post("/validate")
def validate_upload():
    uploaded = request.files.get("csv_file")
    if uploaded is None or not uploaded.filename:
        return render_template("validate.html", result=None, error="CSV file is required."), 400

    try:
        content = uploaded.read().decode("utf-8-sig")
        rows = parse_projects_csv(content)
    except UnicodeDecodeError:
        return render_template("validate.html", result=None, error="CSV file must be UTF-8 text."), 400
    except CsvParseError as exc:
        return render_template("validate.html", result=None, error=str(exc)), 400

    report = validate_project_rows(rows)
    preview = build_validation_preview(rows)
    result = validation_response(report, preview)
    write_audit_event(current_app.config["APP_CONFIG"].data_dir, "validation", result)
    return render_template("validate.html", result=result, error=None), 200 if report.valid else 422

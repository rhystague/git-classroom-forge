from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, Response, abort, current_app, jsonify, render_template, request

from app.audit import write_audit_event
from app.csv_parser import CsvParseError, parse_projects_csv
from app.dry_run import (
    DryRunSelection,
    DryRunSnapshotError,
    build_dry_run_report,
    load_valid_dry_run_snapshot,
    persist_dry_run_snapshot,
)
from app.gitlab_client import GitLabClient
from app.provisioner import (
    build_validation_preview,
    persist_provisioning_report,
    provision_from_dry_run,
)
from app.reports import validation_response
from app.validators import validate_project_rows


bp = Blueprint("routes", __name__)


CSV_SAMPLES = {
    "group": {
        "filename": "group-assessment-sample.csv",
        "content": (
            "project_path,project_name,student_id\r\n"
            "team-01,Team 01,22048668\r\n"
            "team-01,Team 01,22049321\r\n"
            "team-02,Team 02,22051234\r\n"
        ),
    },
    "individual": {
        "filename": "individual-assessment-sample.csv",
        "content": (
            "student_id,project_path,project_name\r\n"
            "22048668,22048668,John Smith - 22048668\r\n"
            "22049321,22049321,Jane Doe - 22049321\r\n"
        ),
    },
}


@bp.get("/")
def index():
    return render_template("landing.html")


@bp.get("/gitlab-provision")
def gitlab_provision():
    return render_template("gitlab_provision.html")


@bp.get("/health")
def health():
    return {"status": "ok", "service": "class-git-forge"}


@bp.get("/validate")
def validate_form():
    return _render_validate()


@bp.get("/sample-csv/<assessment_mode>")
def sample_csv(assessment_mode: str):
    sample = CSV_SAMPLES.get(assessment_mode)
    if sample is None:
        abort(404)

    return Response(
        sample["content"],
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={sample['filename']}",
        },
    )


@bp.get("/groups")
def groups():
    config = current_app.config["APP_CONFIG"]
    if not config.gitlab_configured:
        return (
            jsonify(
                {
                    "groups": [],
                    "error": "GITLAB_URL and GITLAB_TOKEN must be set before browsing GitLab groups.",
                }
            ),
            503,
        )

    try:
        course_groups = _gitlab_client().browse_head_course_groups()
    except Exception as exc:  # pragma: no cover - exercised with integration credentials.
        return (
            jsonify(
                {
                    "groups": [],
                    "error": "GitLab group browse failed.",
                    "error_type": type(exc).__name__,
                    "error_detail": _safe_exception_detail(exc),
                }
            ),
            502,
        )

    return jsonify(
        {
            "groups": [asdict(group) for group in course_groups],
        }
    )


@bp.get("/groups/<path:course_path>/offerings")
def group_offerings(course_path: str):
    config = current_app.config["APP_CONFIG"]
    if not config.gitlab_configured:
        return (
            jsonify(
                {
                    "offerings": [],
                    "error": "GITLAB_URL and GITLAB_TOKEN must be set before browsing GitLab groups.",
                }
            ),
            503,
        )

    try:
        offerings = _gitlab_client().list_offerings(course_path.strip("/"))
    except Exception as exc:  # pragma: no cover - exercised with integration credentials.
        return (
            jsonify(
                {
                    "offerings": [],
                    "error": "GitLab offering browse failed.",
                    "error_type": type(exc).__name__,
                    "error_detail": _safe_exception_detail(exc),
                }
            ),
            502,
        )

    return jsonify({"offerings": [asdict(offering) for offering in offerings]})


@bp.get("/groups/<path:offering_path>/assessments")
def group_assessments(offering_path: str):
    config = current_app.config["APP_CONFIG"]
    if not config.gitlab_configured:
        return (
            jsonify(
                {
                    "assessments": [],
                    "error": "GITLAB_URL and GITLAB_TOKEN must be set before browsing GitLab groups.",
                }
            ),
            503,
        )

    try:
        assessments = _gitlab_client().list_assessments(offering_path.strip("/"))
    except Exception as exc:  # pragma: no cover - exercised with integration credentials.
        return (
            jsonify(
                {
                    "assessments": [],
                    "error": "GitLab assessment browse failed.",
                    "error_type": type(exc).__name__,
                    "error_detail": _safe_exception_detail(exc),
                }
            ),
            502,
        )

    return jsonify({"assessments": [asdict(assessment) for assessment in assessments]})


@bp.get("/groups/<path:course_path>/projects")
def group_projects(course_path: str):
    config = current_app.config["APP_CONFIG"]
    if not config.gitlab_configured:
        return (
            jsonify(
                {
                    "projects": [],
                    "error": "GITLAB_URL and GITLAB_TOKEN must be set before browsing GitLab projects.",
                }
            ),
            503,
        )

    try:
        projects = _gitlab_client().list_course_projects(course_path.strip("/"))
    except Exception as exc:  # pragma: no cover - exercised with integration credentials.
        return (
            jsonify(
                {
                    "projects": [],
                    "error": "GitLab project browse failed.",
                    "error_type": type(exc).__name__,
                    "error_detail": _safe_exception_detail(exc),
                }
            ),
            502,
        )

    return jsonify({"projects": [asdict(project) for project in projects]})


@bp.post("/validate")
def validate_upload():
    uploaded = request.files.get("csv_file")
    if uploaded is None or not uploaded.filename:
        return _render_validate(error="CSV file is required.", status=400)

    try:
        content = uploaded.read().decode("utf-8-sig")
        rows = parse_projects_csv(content, _assessment_mode_from_form())
    except UnicodeDecodeError:
        return _render_validate(error="CSV file must be UTF-8 text.", status=400)
    except CsvParseError as exc:
        return _render_validate(error=str(exc), status=400)

    report = validate_project_rows(rows)
    preview = build_validation_preview(rows)
    result = validation_response(report, preview)
    write_audit_event(current_app.config["APP_CONFIG"].data_dir, "validation", result)
    return _render_validate(result=result, status=200 if report.valid else 422)


@bp.post("/dry-run")
def dry_run_upload():
    uploaded = request.files.get("csv_file")
    if uploaded is None or not uploaded.filename:
        return _render_validate(error="CSV file is required.", status=400)

    config = current_app.config["APP_CONFIG"]
    if not config.gitlab_configured:
        return _render_validate(
            error="GITLAB_URL and GITLAB_TOKEN must be set before dry-run validation.",
            status=503,
        )
    try:
        content = uploaded.read().decode("utf-8-sig")
        rows = parse_projects_csv(content, _assessment_mode_from_form())
    except UnicodeDecodeError:
        return _render_validate(error="CSV file must be UTF-8 text.", status=400)
    except CsvParseError as exc:
        return _render_validate(error=str(exc), status=400)

    selection = _dry_run_selection_from_form()
    report = build_dry_run_report(
        rows=rows,
        selection=selection,
        gitlab=_gitlab_client(),
        student_email_domain=config.student_email_domain,
    )
    persist_dry_run_snapshot(config.data_dir, report)
    write_audit_event(config.data_dir, "dry-run", report)
    return _render_validate(dry_run=report, status=200 if report["valid"] else 422)


@bp.post("/provision")
def provision():
    config = current_app.config["APP_CONFIG"]
    if not config.gitlab_configured:
        return _render_validate(
            error="GITLAB_URL and GITLAB_TOKEN must be set before provisioning.",
            status=503,
        )

    try:
        dry_run = load_valid_dry_run_snapshot(
            config.data_dir,
            request.form.get("run_id", "").strip(),
        )
    except DryRunSnapshotError as exc:
        return _render_validate(error=str(exc), status=400)

    provisioning = provision_from_dry_run(dry_run, _gitlab_client())
    persist_provisioning_report(config.data_dir, provisioning)
    write_audit_event(config.data_dir, "provision", provisioning)
    return _render_validate(
        dry_run=dry_run,
        provisioning=provisioning,
        status=200 if provisioning["valid"] else 502,
    )


def _render_validate(
    result: dict[str, object] | None = None,
    dry_run: dict[str, object] | None = None,
    provisioning: dict[str, object] | None = None,
    error: str | None = None,
    status: int = 200,
):
    return (
        render_template(
            "validate.html",
            result=result,
            dry_run=dry_run,
            provisioning=provisioning,
            error=error,
            course_groups=[],
            browse_error=None,
            config=current_app.config["APP_CONFIG"],
        ),
        status,
    )


def _gitlab_client():
    return current_app.config.get("GITLAB_CLIENT") or GitLabClient(current_app.config["APP_CONFIG"])


def _safe_exception_detail(exc: Exception) -> str:
    config = current_app.config["APP_CONFIG"]
    detail = str(exc) or type(exc).__name__
    for secret in (config.gitlab_token,):
        if secret:
            detail = detail.replace(secret, "[redacted]")
    return detail


def _dry_run_selection_from_form() -> DryRunSelection:
    parent_group_path = request.form.get("parent_group_path", "").strip().strip("/")
    existing_assessment = request.form.get("existing_assessment_full_path", "").strip().strip("/")
    existing_offering = request.form.get("existing_offering_full_path", "").strip().strip("/")

    if existing_assessment:
        parent_group_path, offering_path, assessment_path = _split_existing_assessment_path(
            existing_assessment,
            parent_group_path,
        )
    else:
        if existing_offering:
            parent_group_path, offering_path = _split_existing_offering_path(
                existing_offering,
                parent_group_path,
            )
        else:
            offering_path = request.form.get("offering_path", "").strip().strip("/")
        assessment_path = request.form.get("assessment_path", "").strip().strip("/")

    return DryRunSelection(
        parent_group_path=parent_group_path,
        offering_path=offering_path,
        offering_name=request.form.get("offering_name", "").strip() or offering_path,
        assessment_path=assessment_path,
        assessment_name=request.form.get("assessment_name", "").strip() or assessment_path,
        base_repository_mode=request.form.get("base_repository_mode", "").strip(),
        base_repository_full_path=request.form.get("base_repository_full_path", "").strip().strip("/"),
    )


def _assessment_mode_from_form() -> str:
    return request.form.get("assessment_mode", "").strip()


def _split_existing_offering_path(
    full_path: str,
    selected_parent_path: str,
) -> tuple[str, str]:
    parts = full_path.split("/", maxsplit=1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return selected_parent_path, full_path


def _split_existing_assessment_path(
    full_path: str,
    selected_parent_path: str,
) -> tuple[str, str, str]:
    parts = full_path.split("/", maxsplit=2)
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    return selected_parent_path, request.form.get("offering_path", "").strip().strip("/"), full_path

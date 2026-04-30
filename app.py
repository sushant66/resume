#!/usr/bin/env python3

from __future__ import annotations

import base64
import copy
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from flask import Flask, Response, jsonify, request, send_file
from jsonschema import Draft202012Validator, FormatChecker
import yaml


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
TEX_DIR = ROOT / "tex"
BUILD_DIR = ROOT / "build"
RESUME_YAML = DATA_DIR / "resume.yaml"
EDITOR_SCHEMA = DATA_DIR / "editor_schema.json"
PDF_PATH = BUILD_DIR / "Sushant_Kadam.pdf"
GENERATED_FILES = [
    RESUME_YAML.relative_to(ROOT).as_posix(),
    "data/resume.json",
    "data/schema.json",
    "tex/generated/metadata.tex",
    "tex/sections/header.tex",
    "tex/sections/summary.tex",
    "tex/sections/experience.tex",
    "tex/sections/skills.tex",
    "tex/sections/projects.tex",
    "tex/sections/certifications.tex",
    "tex/sections/education.tex",
    "tex/sections/achievements.tex",
]
VERSION_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
GITHUB_API_BASE = os.environ.get("GITHUB_API_BASE", "https://api.github.com")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "").strip()
GITHUB_REPO = os.environ.get("GITHUB_REPO", "").strip()
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "").strip() or "main"

app = Flask(__name__, static_folder="static", static_url_path="/static")


@app.after_request
def add_no_cache_headers(response: Response) -> Response:
    if request.path == "/" or request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@dataclass
class CommandResult:
    ok: bool
    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def combined_output(self) -> str:
        output = []
        if self.stdout.strip():
            output.append(self.stdout.strip())
        if self.stderr.strip():
            output.append(self.stderr.strip())
        return "\n".join(output).strip()


def load_editor_schema() -> dict[str, Any]:
    return json.loads(EDITOR_SCHEMA.read_text(encoding="utf-8"))


def load_resume_data() -> dict[str, Any]:
    with RESUME_YAML.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_resume_data(data: dict[str, Any]) -> None:
    with RESUME_YAML.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=False)


def validate_resume_data(data: dict[str, Any]) -> list[dict[str, str]]:
    schema = load_editor_schema()
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.path)):
        path = "/" + "/".join(str(part) for part in error.absolute_path) if error.absolute_path else "/"
        errors.append({"path": path, "message": error.message})
    return errors


def run_command(args: list[str]) -> CommandResult:
    result = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return CommandResult(
        ok=result.returncode == 0,
        command=" ".join(args),
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def git_output(args: list[str]) -> str:
    if not has_git():
        raise RuntimeError("git is not installed or not available in PATH")
    result = run_command(["git", *args])
    if not result.ok:
        raise RuntimeError(result.combined_output or f"git {' '.join(args)} failed")
    return result.stdout.rstrip("\n")


def parse_git_status() -> list[dict[str, str]]:
    output = git_output(["status", "--porcelain"])
    entries: list[dict[str, str]] = []
    if not output:
        return entries
    for line in output.splitlines():
        status = line[:2]
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries.append({"status": status, "path": path})
    return entries


def get_current_branch() -> str:
    if github_env_configured():
        return GITHUB_BRANCH
    return git_output(["rev-parse", "--abbrev-ref", "HEAD"])


def get_origin_url() -> str:
    if github_env_configured():
        return f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
    try:
        return git_output(["remote", "get-url", "origin"])
    except RuntimeError:
        return ""


def normalize_repo_url(remote_url: str) -> str:
    if remote_url.startswith("git@github.com:"):
        repo = remote_url.removeprefix("git@github.com:").removesuffix(".git")
        return f"https://github.com/{repo}"
    if remote_url.startswith("https://github.com/"):
        return remote_url.removesuffix(".git")
    return remote_url


def get_preview_url() -> str | None:
    if not PDF_PATH.exists():
        return None
    return f"/api/preview/pdf?ts={int(PDF_PATH.stat().st_mtime)}"


def get_last_generated() -> str | None:
    if not PDF_PATH.exists():
        return None
    return PDF_PATH.stat().st_mtime_ns.__str__()


def get_status_payload() -> dict[str, Any]:
    tracked_dirty = [entry["path"] for entry in parse_git_status() if entry["status"] != "??"] if has_git() else []
    resume = load_resume_data()
    return {
        "branch": get_current_branch(),
        "origin": normalize_repo_url(get_origin_url()),
        "version": resume["meta"]["version"],
        "dirtyFiles": tracked_dirty,
        "previewAvailable": PDF_PATH.exists(),
        "previewUrl": get_preview_url(),
        "lastGenerated": get_last_generated(),
        "pushMode": get_push_mode(),
        "pushConfigured": push_is_configured(),
    }


def save_resume_payload(data: dict[str, Any]) -> tuple[bool, list[dict[str, str]]]:
    errors = validate_resume_data(data)
    if errors:
        return False, errors
    write_resume_data(data)
    return True, []


def run_generate_pipeline() -> tuple[bool, list[dict[str, Any]]]:
    command_results = [run_command(["make", "generate"]), run_command(["make", "compile"])]
    logs = [
        {
            "command": result.command,
            "ok": result.ok,
            "returncode": result.returncode,
            "output": result.combined_output,
        }
        for result in command_results
    ]
    return all(result.ok for result in command_results), logs


def bump_patch_version(version: str) -> str:
    match = VERSION_RE.match(version)
    if not match:
        raise ValueError("meta.version must follow vMAJOR.MINOR.PATCH")
    major, minor, patch = (int(part) for part in match.groups())
    return f"v{major}.{minor}.{patch + 1}"


def get_unrelated_dirty_files() -> list[str]:
    if not has_git():
        return []
    tracked_entries = [entry for entry in parse_git_status() if entry["status"] != "??"]
    return sorted(
        entry["path"]
        for entry in tracked_entries
        if entry["path"] not in GENERATED_FILES
    )


def stage_generated_files() -> None:
    existing_files = [path for path in GENERATED_FILES if (ROOT / path).exists()]
    if existing_files:
        result = run_command(["git", "add", *existing_files])
        if not result.ok:
            raise RuntimeError(result.combined_output or "Unable to stage generated files")


def ensure_commit_has_changes() -> None:
    result = run_command(["git", "diff", "--cached", "--quiet"])
    if result.returncode == 0:
        raise RuntimeError("No staged changes are available to commit.")
    if result.returncode != 1:
        raise RuntimeError(result.combined_output or "Unable to inspect staged changes")


def has_git() -> bool:
    return shutil.which("git") is not None


def github_env_configured() -> bool:
    return all([GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO])


def push_is_configured() -> bool:
    if github_env_configured():
        return True
    if not has_git():
        return False
    try:
        return bool(get_origin_url())
    except RuntimeError:
        return False


def get_push_mode() -> str:
    if github_env_configured():
        return "github_api"
    if has_git():
        return "git"
    return "unavailable"


def github_api_request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not github_env_configured():
        raise RuntimeError("GitHub env configuration is incomplete. Set GITHUB_TOKEN, GITHUB_OWNER, and GITHUB_REPO.")

    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    req = urllib_request.Request(
        f"{GITHUB_API_BASE}{path}",
        method=method,
        data=body,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "User-Agent": "resume-editor",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib_request.urlopen(req) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} failed: {exc.code} {detail}") from exc


def create_github_blob(relative_path: str) -> str:
    content = (ROOT / relative_path).read_bytes()
    payload = {
        "content": base64.b64encode(content).decode("ascii"),
        "encoding": "base64",
    }
    response = github_api_request(
        "POST",
        f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/blobs",
        payload,
    )
    return response["sha"]


def push_via_github_api(commit_message: str) -> tuple[str, str]:
    ref = github_api_request(
        "GET",
        f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/ref/heads/{GITHUB_BRANCH}",
    )
    head_sha = ref["object"]["sha"]

    commit = github_api_request(
        "GET",
        f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/commits/{head_sha}",
    )
    base_tree_sha = commit["tree"]["sha"]

    tree = []
    for relative_path in GENERATED_FILES:
        file_path = ROOT / relative_path
        if not file_path.exists():
            continue
        tree.append(
            {
                "path": relative_path,
                "mode": "100644",
                "type": "blob",
                "sha": create_github_blob(relative_path),
            }
        )

    created_tree = github_api_request(
        "POST",
        f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/trees",
        {"base_tree": base_tree_sha, "tree": tree},
    )
    created_commit = github_api_request(
        "POST",
        f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/commits",
        {
            "message": commit_message,
            "tree": created_tree["sha"],
            "parents": [head_sha],
        },
    )
    github_api_request(
        "PATCH",
        f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/refs/heads/{GITHUB_BRANCH}",
        {"sha": created_commit["sha"], "force": False},
    )
    return created_commit["sha"], normalize_repo_url(get_origin_url())


def push_via_git(commit_message: str) -> tuple[str, str, list[dict[str, Any]]]:
    stage_generated_files()
    ensure_commit_has_changes()

    commit_result = run_command(["git", "commit", "-m", commit_message])
    if not commit_result.ok:
        raise RuntimeError(commit_result.combined_output or "git commit failed")

    branch = get_current_branch()
    push_result = run_command(["git", "push", "origin", branch])
    if not push_result.ok:
        raise RuntimeError(push_result.combined_output or "git push failed")

    commit_sha = git_output(["rev-parse", "HEAD"])
    return commit_sha, branch, [
        {
            "command": commit_result.command,
            "ok": commit_result.ok,
            "returncode": commit_result.returncode,
            "output": commit_result.combined_output,
        },
        {
            "command": push_result.command,
            "ok": push_result.ok,
            "returncode": push_result.returncode,
            "output": push_result.combined_output,
        },
    ]


@app.get("/")
def index() -> Response:
    return send_file(ROOT / "static" / "index.html")


@app.get("/api/schema")
def api_schema() -> Response:
    return jsonify(load_editor_schema())


@app.get("/api/resume")
def api_resume() -> Response:
    return jsonify({"data": load_resume_data(), "status": get_status_payload()})


@app.get("/api/status")
def api_status() -> Response:
    return jsonify(get_status_payload())


@app.post("/api/resume")
def api_save_resume() -> Response:
    payload = request.get_json(force=True) or {}
    data = payload.get("data")
    if not isinstance(data, dict):
        return jsonify({"ok": False, "errors": [{"path": "/", "message": "Request body must include object data."}]}), 400
    ok, errors = save_resume_payload(data)
    if not ok:
        return jsonify({"ok": False, "errors": errors}), 400
    return jsonify({"ok": True, "data": load_resume_data(), "status": get_status_payload()})


@app.post("/api/generate")
def api_generate() -> Response:
    payload = request.get_json(force=True) or {}
    data = payload.get("data")
    if not isinstance(data, dict):
        return jsonify({"ok": False, "errors": [{"path": "/", "message": "Request body must include object data."}]}), 400

    ok, errors = save_resume_payload(data)
    if not ok:
        return jsonify({"ok": False, "errors": errors}), 400

    success, logs = run_generate_pipeline()
    response = {
        "ok": success,
        "logs": logs,
        "previewUrl": get_preview_url(),
        "artifacts": {
            "resumeJson": (DATA_DIR / "resume.json").exists(),
            "schemaJson": (DATA_DIR / "schema.json").exists(),
            "pdf": PDF_PATH.exists(),
        },
        "status": get_status_payload(),
    }
    if not success:
        return jsonify(response), 500
    return jsonify(response)


@app.get("/api/preview/pdf")
def api_preview_pdf() -> Response:
    if not PDF_PATH.exists():
        return jsonify({"ok": False, "message": "PDF preview not available yet."}), 404
    return send_file(PDF_PATH, mimetype="application/pdf")


@app.post("/api/push")
def api_push() -> Response:
    payload = request.get_json(force=True) or {}
    data = payload.get("data")
    custom_message = (payload.get("commitMessage") or "").strip()
    if not isinstance(data, dict):
        return jsonify({"ok": False, "errors": [{"path": "/", "message": "Request body must include object data."}]}), 400

    validation_errors = validate_resume_data(data)
    if validation_errors:
        return jsonify({"ok": False, "errors": validation_errors}), 400

    if not push_is_configured():
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Push is not configured. Provide local git remote access or set GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO, and optionally GITHUB_BRANCH.",
                }
            ),
            400,
        )

    unrelated_dirty_files = get_unrelated_dirty_files()
    if get_push_mode() == "git" and unrelated_dirty_files:
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Push blocked because unrelated tracked files have uncommitted changes.",
                    "unrelatedDirtyFiles": unrelated_dirty_files,
                }
            ),
            409,
        )

    next_data = copy.deepcopy(data)
    next_version = bump_patch_version(next_data["meta"]["version"])
    next_data["meta"]["version"] = next_version
    write_resume_data(next_data)

    success, logs = run_generate_pipeline()
    if not success:
        return jsonify({"ok": False, "logs": logs, "status": get_status_payload()}), 500

    try:
        commit_message = custom_message or f"resume: release {next_version}"
        if get_push_mode() == "github_api":
            commit_sha, origin = push_via_github_api(commit_message)
            branch = GITHUB_BRANCH
            push_logs = [
                {
                    "command": "github api create commit",
                    "ok": True,
                    "returncode": 0,
                    "output": f"Committed and updated {GITHUB_OWNER}/{GITHUB_REPO}@{GITHUB_BRANCH}",
                }
            ]
        else:
            commit_sha, branch, push_logs = push_via_git(commit_message)
            origin = normalize_repo_url(get_origin_url())

        return jsonify(
            {
                "ok": True,
                "version": next_version,
                "commitMessage": commit_message,
                "commitSha": commit_sha,
                "branch": branch,
                "origin": origin,
                "buildUrl": f"{origin}/actions",
                "logs": logs + push_logs,
                "status": get_status_payload(),
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc), "logs": logs, "status": get_status_payload()}), 500


if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG", "").lower() == "true",
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_PORT", "5000")),
    )

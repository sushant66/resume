#!/usr/bin/env python3

import json
import re
import shutil
import subprocess
import sys
from collections import OrderedDict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
TEX_DIR = ROOT / "tex"
SOURCE = DATA_DIR / "resume.yaml"
SECTIONS_DIR = TEX_DIR / "sections"
GENERATED_DIR = TEX_DIR / "generated"


def load_resume_data() -> dict:
    source_text = SOURCE.read_text(encoding="utf-8")
    try:
        return json.loads(source_text)
    except json.JSONDecodeError:
        pass

    try:
        import yaml

        return yaml.safe_load(source_text)
    except ModuleNotFoundError:
        pass

    if shutil.which("yq") is None:
        raise RuntimeError("Install PyYAML or yq to parse resume.yaml, then rerun make generate.")

    result = subprocess.run(
        ["yq", "-o=json", str(SOURCE)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def run_git(args: list[str]) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def source_last_modified() -> str:
    source_path = SOURCE.relative_to(ROOT).as_posix()
    diff_exit = subprocess.run(
        ["git", "diff", "--quiet", "--", source_path],
        cwd=ROOT,
        check=False,
    ).returncode
    if diff_exit == 1:
        return date.today().isoformat()

    commit_date = run_git(["log", "-1", "--format=%cs", "--", source_path])
    if commit_date:
        return commit_date

    return date.today().isoformat()


def tex_escape(value: str) -> str:
    replacements = OrderedDict(
        [
            ("\\", r"\textbackslash{}"),
            ("&", r"\&"),
            ("%", r"\%"),
            ("$", r"\$"),
            ("#", r"\#"),
            ("_", r"\_"),
            ("{", r"\{"),
            ("}", r"\}"),
            ("~", r"\textasciitilde{}"),
            ("^", r"\textasciicircum{}"),
        ]
    )
    escaped = value
    for old, new in replacements.items():
        escaped = escaped.replace(old, new)
    return escaped


INLINE_TOKEN_RE = re.compile(
    r"(\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|_([^_]+)_)"
)


def render_inline_markup(value: str) -> str:
    parts: list[str] = []
    cursor = 0
    for match in INLINE_TOKEN_RE.finditer(value):
        start, end = match.span()
        if start > cursor:
            parts.append(tex_escape(value[cursor:start]))

        link_label = match.group(2)
        link_url = match.group(3)
        bold_text = match.group(4)
        italic_text = match.group(5)

        if link_label is not None and link_url is not None:
            if link_label.startswith("**") and link_label.endswith("**"):
                label = rf"\textbf{{{tex_escape(link_label[2:-2])}}}"
            else:
                label = tex_escape(link_label)
            parts.append(rf"\projectlink{{{link_url}}}{{{label}}}")
        elif bold_text is not None:
            parts.append(rf"\textbf{{{tex_escape(bold_text)}}}")
        elif italic_text is not None:
            parts.append(rf"\textit{{{tex_escape(italic_text)}}}")

        cursor = end

    if cursor < len(value):
        parts.append(tex_escape(value[cursor:]))

    return "".join(parts)


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def render_header(data: dict) -> str:
    basics = data["basics"]
    email = basics["email"]
    phone = basics["phone"]
    location = tex_escape(basics["location"]["display"])
    profile_links = [rf"\href{{mailto:{email}}}{{{tex_escape(email)}}}"]
    profile_links.extend(
        rf"\href{{{profile['url']}}}{{{tex_escape(profile['url'].removeprefix('https://'))}}}"
        for profile in basics["profiles"]
    )
    profile_line = r" \\ ".join(profile_links)
    return "\n".join(
        [
            "% Generated from resume.yaml. Do not edit directly.",
            rf"\name{{{tex_escape(basics['name'])}}}",
            rf"\address{{{tex_escape(phone['display'])} \\ {location}}}",
            rf"\address{{{profile_line}}}",
        ]
    )


def render_summary(data: dict) -> str:
    return "\n".join(
        [
            "% Generated from resume.yaml. Do not edit directly.",
            r"\begin{rSection}{SUMMARY}",
            "",
            render_inline_markup(data["basics"]["summary"]),
            "",
            r"\end{rSection}",
        ]
    )


def render_experience(data: dict) -> str:
    lines = ["% Generated from resume.yaml. Do not edit directly.", r"\begin{rSection}{EXPERIENCE}", ""]
    for item in data["experience"]:
        date_display = f"{item['start_display']} -- {item['end_display']}"
        lines.append(
            rf"\experienceentry{{{tex_escape(item['company'])}}}{{{tex_escape(item['location']['display'])}}}{{{tex_escape(item['position'])}}}{{{tex_escape(date_display)}}}"
        )
        for bullet in item["bullets"]:
            lines.append(f"  \\item {render_inline_markup(bullet)}")
        lines.extend([r"\experienceentryend", ""])
    lines.append(r"\end{rSection}")
    return "\n".join(lines)


def render_skills(data: dict) -> str:
    skills = data["skills"]
    lines = [
        "% Generated from resume.yaml. Do not edit directly.",
        r"\begin{rSection}{SKILLS}",
        "",
        r"\begin{tabular}{ @{} >{\bfseries}l @{\hspace{6ex}} l }",
    ]
    for skill in skills:
        label = tex_escape(skill["name"])
        keywords = tex_escape(", ".join(skill["keywords"]))
        lines.append(rf"{label} & {keywords} \\")
    lines.extend([r"\end{tabular}", "", r"\end{rSection}"])
    return "\n".join(lines)


def render_projects(data: dict) -> str:
    lines = ["% Generated from resume.yaml. Do not edit directly.", r"\begin{rSection}{PROJECTS}", ""]
    for item in data["projects"]:
        project_url = item["url"] if item["link_label"] else ""
        lines.append(
            rf"\projectentry{{{tex_escape(item['name'])}}}{{}}{{{project_url}}}{{{tex_escape(item['link_label'])}}}"
        )
        for bullet in item["bullets"]:
            lines.append(f"  \\item {render_inline_markup(bullet)}")
        lines.extend([r"\projectentryend", ""])
    lines.append(r"\end{rSection}")
    return "\n".join(lines)


def render_education(data: dict) -> str:
    lines = ["% Generated from resume.yaml. Do not edit directly.", r"\begin{rSection}{EDUCATION}", ""]
    for item in data["education"]:
        lines.append(
            rf"\educationentry{{{tex_escape(item['institution'])}}}{{{tex_escape(item['short_study_type'])} in {tex_escape(item['area'])}}}{{{tex_escape(item['start_date'])} - {tex_escape(item['end_date'])}}}{{{tex_escape(item['score'])}}}"
        )
        lines.append("")
    lines.append(r"\end{rSection}")
    return "\n".join(lines)


def render_certifications(data: dict) -> str:
    if not data["certifications"]:
        return "% Generated from resume.yaml. Do not edit directly.\n"
    lines = ["% Generated from resume.yaml. Do not edit directly.", r"\begin{rSection}{CERTIFICATIONS}", ""]
    for item in data["certifications"]:
        lines.append(
            rf"\certificationentry{{{tex_escape(item['name'])}}}{{{tex_escape(item['issuer'])}}}{{{item['url']}}}"
        )
    lines.append(r"\end{rSection}")
    return "\n".join(lines)


def render_achievements(data: dict) -> str:
    if not data["achievements"]:
        return "% Generated from resume.yaml. Do not edit directly.\n"
    lines = [
        "% Generated from resume.yaml. Do not edit directly.",
        r"\begin{rSection}{ACHIEVEMENTS}",
        r"\begin{itemize}",
    ]
    for item in data["achievements"]:
        lines.append(f"  \\item {render_inline_markup(item)}")
    lines.append(r"\end{itemize}")
    lines.append(r"\end{rSection}")
    return "\n".join(lines)


def render_metadata(data: dict) -> str:
    basics = data["basics"]
    pdf = data["pdf"]
    meta = data["meta"]
    keywords = ",\n    ".join(tex_escape(keyword) for keyword in pdf["keywords"])
    name = tex_escape(basics["name"])
    address = tex_escape(basics["location"]["pdf_display"])
    license_url = meta["license_url"]
    return "\n".join(
        [
            "% Generated from resume.yaml. Do not edit directly.",
            rf"\newcommand{{\ResumeOwnerName}}{{{name}}}",
            rf"\newcommand{{\ResumeSchemaDescription}}{{Schema.org structured data - {name}}}",
            rf"\newcommand{{\ResumeJsonDescription}}{{JSON Resume - {name}}}",
            "",
            r"\hypersetup{",
            rf"  pdftitle={{{name}}},",
            rf"  pdfauthor={{{name}}},",
            rf"  pdfauthortitle={{{tex_escape(basics['label'])}}},",
            rf"  pdfsubject={{{tex_escape(pdf['subject'])}}},",
            "  pdfkeywords={",
            f"    {keywords}",
            "  },",
            rf"  pdfcreator={{{tex_escape(pdf['creator'])}}},",
            rf"  pdfproducer={{{tex_escape(pdf['producer'])}}},",
            rf"  pdflang={{{pdf['lang']}}},",
            rf"  pdfmetalang={{{pdf['lang']}}},",
            rf"  pdfcontactaddress={{{address}}},",
            rf"  pdfcontactemail={{{basics['email']}}},",
            rf"  pdfcontacturl={{{basics['website']}}},",
            rf"  pdfcopyright={{Copyright \the\year\ {name}. Licensed under Apache-2.0.}},",
            rf"  pdflicenseurl={{{license_url}}},",
            rf"  pdfurl={{{basics['website']}}},",
            rf"  pdfpubtype={{{pdf['pubtype']}}},",
            r"}",
        ]
    )


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            output.append(value)
            seen.add(value)
    return output


def build_resume_json(data: dict, last_modified: str) -> dict:
    basics = data["basics"]
    resume = {
        "$schema": "https://raw.githubusercontent.com/jsonresume/resume-schema/v1.0.0/schema.json",
        "basics": {
            "name": basics["name"],
            "label": basics["label"],
            "email": basics["email"],
            "url": basics["website"],
            "summary": basics["summary"],
            "location": {
                "city": basics["location"]["city"],
                "region": basics["location"]["region"],
                "countryCode": basics["location"]["country_code"],
            },
            "profiles": [
                {
                    "network": profile["network"],
                    "username": profile["username"],
                    "url": profile["url"],
                }
                for profile in basics["profiles"]
                if profile["network"] != "Portfolio"
            ],
        },
        "work": [],
        "education": [],
        "skills": [],
        "projects": [],
        "certificates": [],
        "meta": {
            "canonical": data["meta"]["canonical"],
            "version": data["meta"]["version"],
            "lastModified": last_modified,
        },
    }

    for item in data["experience"]:
        work = {
            "name": item["company"],
            "position": item["position"],
            "startDate": item["start_date"],
            "location": f"{item['location']['city']}, {item['location']['region']}, {item['location']['country']}",
        }
        if item.get("url"):
            work["url"] = item["url"]
        if item.get("end_date"):
            work["endDate"] = item["end_date"]
        resume["work"].append(work)

    for item in data["education"]:
        education = {
            "institution": item["institution"],
            "area": item["area"],
            "studyType": item["study_type"],
            "score": item["score"],
            "startDate": item["start_date"],
            "endDate": item["end_date"],
        }
        if item.get("url"):
            education["url"] = item["url"]
        resume["education"].append(education)

    for item in data["skills"]:
        resume["skills"].append({"name": item["name"], "keywords": item["keywords"]})

    for item in data["projects"]:
        resume["projects"].append(
            {
                "name": item["name"],
                "url": item["url"],
                "roles": item["roles"],
                "keywords": item["keywords"],
            }
        )

    for item in data["certifications"]:
        resume["certificates"].append(
            {
                "name": item["name"],
                "issuer": item["issuer"],
                "url": item["url"],
            }
        )

    return resume


def build_schema_json(data: dict, last_modified: str) -> dict:
    basics = data["basics"]
    meta = data["meta"]
    schema = data["schema"]
    skills = data["skills"]
    modified_year = last_modified[:4]
    knows_about = unique(
        [keyword for skill in skills for keyword in skill["keywords"]] + schema["additional_knows_about"]
    )

    occupations = []
    for item in data["experience"]:
        occupation = {
            "@type": "Occupation",
            "name": item["position"],
            "alternateName": item["alternate_names"],
            "occupationLocation": {
                "@type": "City",
                "name": item["location"]["city"],
            },
            "hiringOrganization": {
                "@type": "Organization",
                "name": item["company"],
            },
            "startDate": item["start_date"],
        }
        if item.get("url"):
            occupation["hiringOrganization"]["url"] = item["url"]
        if item.get("end_date"):
            occupation["endDate"] = item["end_date"]
        occupations.append(occupation)

    work_examples = [
        {
            "@type": "SoftwareSourceCode",
            "name": item["name"],
            "url": item["url"],
            "programmingLanguage": item["keywords"],
        }
        for item in data["projects"]
    ]

    skill_items = [
        {
            "@type": "ListItem",
            "position": index,
            "name": f"{item['name']}: {', '.join(item['keywords'])}",
        }
        for index, item in enumerate(skills, start=1)
    ]

    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Person",
                "@id": schema["person_id"],
                "name": basics["name"],
                "jobTitle": basics["label"],
                "email": basics["email"],
                "url": basics["website"],
                "sameAs": [profile["url"] for profile in basics["profiles"]],
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": basics["location"]["city"],
                    "addressRegion": basics["location"]["region"],
                    "addressCountry": basics["location"]["country_code"],
                },
                "alumniOf": {
                    "@type": "CollegeOrUniversity",
                    "name": data["education"][0]["institution"],
                },
                "knowsAbout": knows_about,
                "hasOccupation": occupations,
                "workExample": work_examples,
                "copyrightYear": meta["created_year"],
                "dateCreated": str(meta["created_year"]),
                "dateModified": modified_year,
                "copyrightHolder": {
                    "@type": "Person",
                    "name": basics["name"],
                },
                "license": meta["license_url"],
            },
            {
                "@type": "CreativeWork",
                "@id": schema["resume_id"],
                "name": f"{basics['name']} - Resume",
                "alternateName": [
                    f"{basics['name']} - CV",
                    f"{basics['name']} - Curriculum Vitae",
                ],
                "about": {
                    "@id": schema["person_id"],
                },
                "hasPart": [
                    {
                        "@type": "ItemList",
                        "name": "Work Experience",
                        "alternateName": [
                            "Experience",
                            "Employment History",
                            "Professional Experience",
                            "Career History",
                        ],
                        "itemListElement": [
                            {
                                "@type": "ListItem",
                                "position": index,
                                "name": f"{item['position']} at {item['company']}",
                            }
                            for index, item in enumerate(data["experience"], start=1)
                        ],
                    },
                    {
                        "@type": "ItemList",
                        "name": "Education",
                        "alternateName": [
                            "Academic Background",
                            "Qualifications",
                            "Academic History",
                        ],
                        "itemListElement": [
                            {
                                "@type": "ListItem",
                                "position": 1,
                                "name": f"{data['education'][0]['short_study_type']} {data['education'][0]['area']} - {data['education'][0]['institution']}",
                            }
                        ],
                    },
                    {
                        "@type": "ItemList",
                        "name": "Technical Skills",
                        "alternateName": [
                            "Skills",
                            "Core Competencies",
                            "Technologies",
                            "Tech Stack",
                            "Expertise",
                        ],
                        "itemListElement": skill_items,
                    },
                    {
                        "@type": "ItemList",
                        "name": "Projects",
                        "alternateName": [
                            "Personal Projects",
                            "Portfolio",
                            "Open Source Work",
                            "Side Projects",
                        ],
                        "itemListElement": [
                            {
                                "@type": "ListItem",
                                "position": index,
                                "name": item["name"],
                            }
                            for index, item in enumerate(data["projects"], start=1)
                        ],
                    },
                    {
                        "@type": "ItemList",
                        "name": "Certifications",
                        "alternateName": [
                            "Certificates",
                            "Professional Certifications",
                            "Credentials",
                        ],
                        "itemListElement": [
                            {
                                "@type": "ListItem",
                                "position": index,
                                "name": f"{item['name']} - {item['issuer']}",
                                "url": item["url"],
                            }
                            for index, item in enumerate(data["certifications"], start=1)
                        ],
                    },
                ],
            },
        ]
    }


def main() -> int:
    data = load_resume_data()
    last_modified = source_last_modified()

    write_file(SECTIONS_DIR / "header.tex", render_header(data))
    write_file(SECTIONS_DIR / "summary.tex", render_summary(data))
    write_file(SECTIONS_DIR / "experience.tex", render_experience(data))
    write_file(SECTIONS_DIR / "skills.tex", render_skills(data))
    write_file(SECTIONS_DIR / "projects.tex", render_projects(data))
    write_file(SECTIONS_DIR / "certifications.tex", render_certifications(data))
    write_file(SECTIONS_DIR / "education.tex", render_education(data))
    write_file(SECTIONS_DIR / "achievements.tex", render_achievements(data))
    write_file(GENERATED_DIR / "metadata.tex", render_metadata(data))
    write_file(DATA_DIR / "resume.json", json.dumps(build_resume_json(data, last_modified), indent=2))
    write_file(DATA_DIR / "schema.json", json.dumps(build_schema_json(data, last_modified), indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())

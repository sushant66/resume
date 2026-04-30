# User Guide

This guide is for anyone who wants to update and rebuild this resume without already knowing how the repository is organized.

## What You Edit

The only file you should edit for resume content is [`resume.yaml`](./data/resume.yaml).

That file is the single source of truth for:

- personal details
- work experience
- projects
- education
- achievements
- PDF metadata
- embedded `resume.json`
- embedded `schema.json`

Do not manually edit these generated files:

- [`sections/header.tex`](./tex/sections/header.tex)
- [`sections/experience.tex`](./tex/sections/experience.tex)
- [`sections/skills.tex`](./tex/sections/skills.tex)
- [`sections/projects.tex`](./tex/sections/projects.tex)
- [`sections/achievements.tex`](./tex/sections/achievements.tex)
- [`sections/education.tex`](./tex/sections/education.tex)
- [`generated/metadata.tex`](./tex/generated/metadata.tex)
- [`resume.json`](./data/resume.json)
- [`schema.json`](./data/schema.json)

## Prerequisites

Install these tools first:

- [Docker](https://docs.docker.com/)
- [yq](https://github.com/mikefarah/yq) or PyYAML
- `python3`
- [uv](https://docs.astral.sh/uv/)
- optionally: [Git](https://git-scm.com/) for local git-based push
- optionally: `exiftool`
- optionally: `pdfdetach`

Check that the required tools are available:

```sh
python3 --version
uv --version
python3 scripts/generate_resume.py
docker --version
make --version
```

## Editing Resume Content

Open [`resume.yaml`](./data/resume.yaml) and update the data you want.

Common sections:

- `basics`: name, email, links, location
- `pdf`: title/keywords/metadata fields
- `skills`: grouped skills
- `experience`: jobs and bullets
- `projects`: project entries and bullets
- `education`: education entries
- `achievements`: certifications, awards, coding profiles

### Supported Inline Formatting

Inside prose fields such as experience bullets, project bullets, and achievements, you can use:

- `**bold**`
- `_italic_`
- `[label](https://example.com)`

Example:

```yaml
bullets:
  - "Built an **internal platform** for _faster onboarding_."
  - "Published the project at [example.com](https://example.com)."
```

Do not put raw LaTeX like `\textbf{}` or `\href{}` into `resume.yaml`.

## Build Commands

### Recommended command

After editing [`resume.yaml`](./data/resume.yaml), run:

```sh
make compile
```

This will:

1. regenerate all derived TeX and JSON files
2. compile the final PDF

### Other useful commands

Generate derived files only:

```sh
make generate
```

Build the Docker image:

```sh
make docker
```

Build Docker image and compile:

```sh
make build
```

Remove generated PDF and LaTeX aux files:

```sh
make clean
```

Clean and recompile:

```sh
make dev
```

Show all available make targets:

```sh
make help
```

## Web UI Workflow

If you prefer not to edit YAML directly, use the included local web editor:

### Docker Compose option

```sh
cp .env.example .env
docker compose up --build
```

Open `http://127.0.0.1:5000`.

This starts the editor in a container, mounts the repository into it, mounts the host Docker socket so PDF compilation can still run, and auto-builds the `latex-builder` image if needed.

### uv option

Use this when you want to run the editor directly on your machine instead of in a container.

```sh
uv sync
uv run python app.py
```

Open `http://127.0.0.1:5000` and use the UI flow:

1. update the schema-driven form
2. click `Save / Update` to validate and write [`resume.yaml`](./data/resume.yaml)
3. click `Generate` to regenerate artifacts and compile the PDF
4. review the inline preview and logs
5. click `Push` to auto-bump the patch version, commit, and push to the current branch

The push flow blocks if unrelated tracked files are dirty.

If you want the editor to push using local git credentials instead of a GitHub token, also make sure these work on your machine:

```sh
git --version
git remote -v
```

### Optional GitHub Token Mode

If the app is running inside a container or on a machine without local git credentials, provide these environment variables:

```sh
export GITHUB_TOKEN=...
export GITHUB_OWNER=sushant66
export GITHUB_REPO=resume
export GITHUB_BRANCH=main
```

In this mode, the backend creates the commit and updates the branch through the GitHub API. The token must have write access to the target repository.

If these variables are not set, the app will use local git mode instead.

## Output

The generated PDF file is:

```sh
build/Sushant_Kadam.pdf
```

## Verifying the Output

Check embedded attachments:

```sh
pdfdetach -list build/Sushant_Kadam.pdf
```

Expected files:

- `resume.json`
- `schema.json`

Inspect XMP metadata:

```sh
exiftool -xmp:all build/Sushant_Kadam.pdf
```

## Troubleshooting

If `make compile` fails:

- ensure `resume.yaml` is valid JSON/YAML and `yq` or PyYAML is available if you move away from JSON-formatted YAML
- ensure Docker is running
- ensure the Docker image builds successfully with `make docker`
- check for YAML syntax mistakes in [`resume.yaml`](./data/resume.yaml)

If you changed [`resume.yaml`](./data/resume.yaml) and the PDF did not update:

- rerun `make compile`
- check whether the generated section files changed
- confirm the edited field is actually used by the generator

## Repository Structure

Useful files:

- [`resume.yaml`](./data/resume.yaml): source of truth
- [`scripts/generate_resume.py`](./scripts/generate_resume.py): generator
- [`main.tex`](./tex/main.tex): LaTeX entry point and PDF embedding
- [`resume.cls`](./tex/resume.cls): visual styling
- [`README.md`](./README.md): project overview

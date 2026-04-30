# Sushant Kadam Resume

This repository contains my resume in TeX, with a YAML source-of-truth layer that generates both the visible resume sections and the embedded metadata files.

If you are using this repository for the first time, start with the user-facing guide:

- [`USER_GUIDE.md`](./USER_GUIDE.md)

## Prerequisites

For the resume build pipeline:

- [Docker](https://docs.docker.com/)
- [yq](https://github.com/mikefarah/yq) or PyYAML

For local git-based push from the editor:

- [Git](https://git-scm.com/)

For running the editor without Docker Compose:

- [uv](https://docs.astral.sh/uv/)

## Contents

- [`tex/main.tex`](./tex/main.tex): The main TeX file for the resume.
- [`tex/resume.cls`](./tex/resume.cls): The resume class used by the Overleaf-compatible layout.
- [`resume.yaml`](./data/resume.yaml): The single source of truth for resume content and metadata.
- [`scripts/generate_resume.py`](./scripts/generate_resume.py): Generates LaTeX partials and embedded JSON files from [`resume.yaml`](./data/resume.yaml).
- [`tex/sections/`](./tex/sections/): Generated TeX files for each resume section.
- [`schema.json`](./data/schema.json): Schema.org JSON-LD structured data embedded in the PDF.
- [`resume.json`](./data/resume.json): JSON Resume structured data embedded in the PDF for ATS parsers.

> [!NOTE]
> This repository uses a custom Docker image for compiling the resume, ensuring consistency and reproducibility across environments.

## Quick Start

<p>1. <strong>Clone the repository</strong>:</p>

```sh
git clone git@github.com:sushant66/resume.git
```

Or via HTTPS:

```sh
git clone https://github.com/sushant66/resume.git
```

<p>2. <strong>Build the Docker image</strong>:</p>

```sh
docker build -t latex-builder .docker
```

<p>3. <strong>Generate the derived artifacts</strong>:</p>

```sh
make generate
```

<p>4. <strong>Compile the resume</strong>:</p>

```sh
docker run --rm -v "$(pwd):/data" -w /data/tex latex-builder -output-directory=/data/build -jobname="Sushant_Kadam" main.tex
```

You can also use:

```sh
make compile
```

> [!NOTE]
> `make compile` and `make build` regenerate all derived artifacts automatically before compiling.

## Web Editor

This repository now includes a local web editor for updating [`resume.yaml`](./data/resume.yaml), generating the derived artifacts, previewing the compiled PDF, and pushing a versioned commit.

### Docker Compose

For the simplest local setup, use Docker Compose:

```sh
cp .env.example .env
docker compose up --build
```

Then open:

```sh
http://127.0.0.1:5000
```

The compose setup mounts the repo into the app container, installs the Python app with `uv`, mounts the host Docker socket, and auto-builds the `latex-builder` image on startup if it is missing.

### Run without Docker

Use this if you want to run the Flask server directly on your machine.

<p>1. <strong>Install the local prerequisites</strong>:</p>

```sh
uv --version
python3 scripts/generate_resume.py
docker --version
```

If you want local git-based push from the app, also verify:

```sh
git --version
git remote -v
```

<p>2. <strong>Install the Python app dependencies with uv</strong>:</p>

```sh
uv sync
```

<p>3. <strong>Start the editor server</strong>:</p>

```sh
uv run python app.py
```

Then open:

```sh
http://127.0.0.1:5000
```

The backend uses the existing `make generate` and `make compile` flow, so Docker is still required for PDF compilation even when the web server itself runs outside Docker.

### Optional GitHub Env Push Mode

If you want the app to push from a container or from an environment without local git credentials, set these environment variables before starting the server:

```sh
export GITHUB_TOKEN=...
export GITHUB_OWNER=sushant66
export GITHUB_REPO=resume
export GITHUB_BRANCH=main
```

Or copy values from [`.env.example`](./.env.example) into your container/runtime environment or local `.env` file.

When these vars are present, the backend commits managed resume files through the GitHub API instead of relying on `git push`. This mode does not require local git auth, but it does require a token with repository write access.

If these vars are not set, the app falls back to local git mode and uses the checked-out repo's configured `origin`.

## Make Commands

Use the included `Makefile` targets for common workflows:

```sh
make help
```

Shows the available targets.

```sh
make generate
```

Regenerates the TeX partials and JSON metadata from [`resume.yaml`](./data/resume.yaml).

```sh
make docker
```

Builds the local Docker image used for LaTeX compilation.

```sh
make compile
```

Regenerates artifacts and compiles the resume PDF using the existing Docker image.

```sh
make build
```

Builds the Docker image and compiles the resume.

```sh
make clean
```

Removes generated PDF and LaTeX auxiliary files.

```sh
make dev
```

Cleans previous artifacts and recompiles the resume.

## Metadata

The compiled PDF contains embedded metadata across multiple standards, making it easier for ATS systems, semantic crawlers, and document parsers to consume:

| Standard           | Description                                                      |
| ------------------ | ---------------------------------------------------------------- |
| XMP / Dublin Core  | Title, author, keywords, rights, language, and dates             |
| IPTC Core          | Contact email, URL, and address                                  |
| Schema.org JSON-LD | Person, occupation, education, projects, and skills metadata     |
| JSON Resume        | Open standard resume data for ATS-compatible parsing             |

Verify the PDF metadata after compiling:

```sh
exiftool -xmp:all build/Sushant_Kadam.pdf
```

List embedded attachments:

```sh
pdfdetach -list build/Sushant_Kadam.pdf
```

## Customization

- **Content**: Update [`resume.yaml`](./data/resume.yaml).
- **Formatting**: Modify [`tex/resume.cls`](./tex/resume.cls) to change appearance and layout.
- **Document wiring**: [`main.tex`](./tex/main.tex) controls section order and PDF attachments.
- **Structured data**: [`resume.json`](./data/resume.json), [`schema.json`](./data/schema.json), and [`generated/metadata.tex`](./tex/generated/metadata.tex) are generated from [`resume.yaml`](./data/resume.yaml).

For step-by-step editing and verification instructions, see [`USER_GUIDE.md`](./USER_GUIDE.md).

## Releases

> [!IMPORTANT]
> GitHub Actions automatically builds and releases the resume on every push to `main`.

Download the latest compiled PDF from the [Releases](https://github.com/sushant66/resume/releases/latest) page.

## License

This project is licensed under the Apache-2.0 License. See [`LICENSE`](./LICENSE) for details.

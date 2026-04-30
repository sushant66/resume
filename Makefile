.PHONY: build clean compile dev docker generate help

help:
	@echo "Available targets:"
	@echo "  generate   - Generate TeX partials and JSON metadata from data/resume.yaml"
	@echo "  build      - Build Docker image and compile resume"
	@echo "  compile    - Compile resume only (requires Docker image)"
	@echo "  docker     - Build Docker image only"
	@echo "  clean      - Remove generated PDF files"
	@echo "  dev        - Clean and recompile the resume"

build: docker compile

docker:
	docker build -t latex-builder .docker

generate:
	python3 scripts/generate_resume.py

compile: generate
	mkdir -p build
	docker run --rm -v "$(PWD):/data" -w /data/tex latex-builder -output-directory=/data/build -jobname="Sushant_Kadam" main.tex

clean:
	rm -f build/*.pdf build/*.aux build/*.log build/*.out

dev:
	make clean && make compile

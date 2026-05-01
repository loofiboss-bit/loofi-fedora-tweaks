SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

NAME := loofi-fedora-tweaks
VERSION := $(shell python3 -c "exec(open('loofi-fedora-tweaks/version.py').read()); print(__version__)")
outdir ?= $(CURDIR)
spec ?= $(CURDIR)/$(NAME).spec

.PHONY: srpm
srpm:
	BUILD_DIR="$$(mktemp -d)"; \
	trap 'rm -rf "$$BUILD_DIR"' EXIT; \
	mkdir -p "$$BUILD_DIR/rpmbuild"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}; \
	STAGE="$$BUILD_DIR/temp_build/$(NAME)-$(VERSION)"; \
	mkdir -p "$$STAGE/$(NAME)"; \
	cp -r loofi-fedora-tweaks/* "$$STAGE/$(NAME)/"; \
	cp $(NAME).desktop "$$STAGE/"; \
	cp $(NAME)-api.service "$$STAGE/"; \
	cp $(NAME).metainfo.xml "$$STAGE/"; \
	cp LICENSE "$$STAGE/"; \
	cp README.md "$$STAGE/"; \
	cp $(NAME).1 "$$STAGE/"; \
	find "$$STAGE" -type d -name "__pycache__" -prune -exec rm -rf {} +; \
	find "$$STAGE" -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete; \
	tar -czf "$$BUILD_DIR/rpmbuild/SOURCES/$(NAME)-$(VERSION).tar.gz" -C "$$BUILD_DIR/temp_build" "$(NAME)-$(VERSION)"; \
	cp "$(spec)" "$$BUILD_DIR/rpmbuild/SPECS/$(NAME).spec"; \
	sed -i 's/\r$$//' "$$BUILD_DIR/rpmbuild/SPECS/$(NAME).spec"; \
	rpmbuild --define "_topdir $$BUILD_DIR/rpmbuild" -bs "$$BUILD_DIR/rpmbuild/SPECS/$(NAME).spec"; \
	mkdir -p "$(outdir)"; \
	cp "$$BUILD_DIR"/rpmbuild/SRPMS/*.src.rpm "$(outdir)/"

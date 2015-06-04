.PHONY: help push

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  push	       Push master branch to origin"

push:
	git push github master

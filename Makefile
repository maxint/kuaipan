.PHONY: clean install build test

all: test

clean:
	@rm -rf build
	@rm -rf dist
	@rm -rf kpfuse.egg-info

build:
	python setup.py bdist


install:
	python setup.py install

test:
	python kpfs.py -h

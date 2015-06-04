.PHONY: clean install build test

all: test

clean:
	@rm -rf build
	@rm -rf dist
	@rm -rf kpfuse.egg-info

build:
	python2 setup.py bdist

install:
	python2 setup.py install

test:
	rm -f /tmp/kpfuse.log
	mkdir -p /tmp/kpfuse_mnt
	python2 kpfs.py /tmp/kpfuse_mnt -D
	ls /tmp/kpfuse_mnt
	echo 'hi' > /tmp/kpfuse_mnt/__test__.txt
	cat /tmp/kpfuse_mnt/__test__.txt
	sudo umount /tmp/kpfuse_mnt
	rmdir /tmp/kpfuse_mnt

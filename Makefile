PREFIX = /usr/local
BINDIR = $(PREFIX)/bin
MANDIR = $(PREFIX)/share/man/man1
DOCDIR = $(PREFIX)/share/doc/nrrdbook
BSHDIR = /etc/bash_completion.d

.PHONY: all install uninstall

all:

install:
	install -m755 -d $(BINDIR)
	install -m755 -d $(MANDIR)
	install -m755 -d $(DOCDIR)
	install -m755 -d $(BSHDIR)
	gzip -c doc/nrrdbook.1 > nrrdbook.1.gz
	install -m755 nrrdbook/nrrdbook.py $(BINDIR)/nrrdbook
	install -m644 nrrdbook.1.gz $(MANDIR)
	install -m644 README.md $(DOCDIR)
	install -m644 CHANGES $(DOCDIR)
	install -m644 LICENSE $(DOCDIR)
	install -m644 CONTRIBUTING.md $(DOCDIR)
	install -m644 auto-completion/bash/nrrdbook-completion.bash $(BSHDIR)
	rm -f nrrdbook.1.gz

uninstall:
	rm -f $(BINDIR)/nrrdbook
	rm -f $(MANDIR)/nrrdbook.1.gz
	rm -f $(BSHDIR)/nrrdbook-completion.bash
	rm -rf $(DOCDIR)


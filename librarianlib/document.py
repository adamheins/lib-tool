import datetime
import hashlib
import os

import textract


HASH_FILE_BUFFER_SIZE = 65536


def _hash_pdf(pdf_path):
    ''' Generate an MD5 hash of a PDF file. '''
    md5 = hashlib.md5()

    with open(pdf_path, 'rb') as f:
        while True:
            data = f.read(HASH_FILE_BUFFER_SIZE)
            if not data:
                break
            md5.update(data)

    return md5.hexdigest()


def _parse_pdf_text(pdf_path):
    ''' Extract plaintext content of a PDF file. '''
    # Try using pdftotext and fallback to pdfminer if that doesn't work.
    try:
        text = textract.process(pdf_path, method='pdftotext')
    except (TypeError, UnicodeDecodeError):
        try:
            text = textract.process(pdf_path, method='pdfminer')
        except (TypeError, UnicodeDecodeError, textract.exceptions.ShellError):
            return None
    return text.decode('utf-8')


class DocumentPaths(object):
    ''' Directory structure of a document in the archive. '''
    def __init__(self, parent, key):
        self.key_path = os.path.join(parent, key)
        self.pdf_path = os.path.join(self.key_path, key + '.pdf')
        self.bib_path = os.path.join(self.key_path, key + '.bib')

        self.metadata_path = os.path.join(self.key_path, '.metadata')

        self.hash_path = os.path.join(self.metadata_path, 'hash.md5')
        self.text_path = os.path.join(self.metadata_path, 'text.txt')
        self.accessed_path = os.path.join(self.metadata_path, 'accessed.txt')
        self.added_path = os.path.join(self.metadata_path, 'added.txt')


class ArchivalDocument(object):
    ''' A document in an archive. '''
    # path contains key
    def __init__(self, key, paths):
        self.key = key
        self.paths = paths

        # Read the bibtex.
        with open(self.paths.bib_path) as f:
            self.bibtex = f.read().strip()

        # Sanity checks.
        if not os.path.exists(self.paths.metadata_path):
            os.mkdir(self.paths.metadata_path)

        # Dates.
        self.added_date = self._read_date('added.txt')
        self.accessed_date = self._read_date('accessed.txt')

    def _read_date(self, fname):
        path = os.path.join(self.paths.metadata_path, fname)
        if os.path.exists(path):
            with open(path) as f:
                date = f.read()
            try:
                return datetime.datetime.strptime(date, '%Y-%m-%d')
            # Malformed date.
            except ValueError:
                pass

        date = datetime.date.today()
        with open(path, 'w') as f:
            f.write(date.isoformat())
        return date

    def text(self):
        ''' Retrieve the plain text of the PDF file.
            Returns a tuple (text, new) : (str, bool)'''
        current_hash = _hash_pdf(self.paths.pdf_path)

        if os.path.exists(self.paths.hash_path):
            with open(self.paths.hash_path) as f:
                old_hash = f.read()
        else:
            old_hash = None

        # If either the text or hash file is missing, or the old hash doesn't
        # match the current hash, we must reparse the PDF.
        if (not os.path.exists(self.paths.text_path)
                or not os.path.exists(self.paths.hash_path)
                or current_hash != old_hash):
            new = True
            text = _parse_pdf_text(self.paths.pdf_path)

            # Save the hash.
            with open(self.paths.hash_path, 'w') as f:
                f.write(current_hash)

            # TODO it may be worth saving an indication of failure so as to
            # avoid reparsing all the time
            if text is not None:
                with open(self.paths.text_path, 'w') as f:
                    f.write(text)
        else:
            new = False
            with open(self.paths.text_path) as f:
                text = f.read()

        return text, new

    def access(self):
        ''' Update the access date to today. '''
        self.accessed_date = datetime.date.today()
        with open(self.paths.accessed_path, 'w') as f:
            f.write(self.accessed_date.isoformat())

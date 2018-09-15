import datetime
import hashlib
import os
import re

import textract
import bibtexparser

from .exceptions import LibraryException


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


def _bibtex_customizations(record):
    ''' Customizations to apply to bibtex record. '''
    record = bibtexparser.customization.convert_to_unicode(record)

    # Make author names more consistent.
    # TODO I would like to embrace the paradigm that this tool is not
    # responsible for formatting your bibtex files.
    names = record['author'].split(' and ')
    authors = []
    for name in names:
        # Change order to: first middle last
        if ',' in name:
            parts = name.split(',')
            parts.reverse()
            name = ' '.join(parts)

        subnames = name.split()
        name = []
        for subname in subnames:
            if subname.isupper():
                subname = subname.replace('.', '')
                for c in subname:
                    name.append(c + '.')
            else:
                name.append(subname)
        authors.append(' '.join(name))
    record['author'] = ' and '.join(authors)

    return record


def _load_bibtex(bib_path):
    ''' Load bibtex information as a dictionary. '''

    with open(bib_path) as f:
        text = f.read().strip()

    # common_strings=True lets us parse the month field as "jan",
    # "feb", etc.
    parser = bibtexparser.bparser.BibTexParser(
            customization=_bibtex_customizations,
            common_strings=True)
    try:
        bibtex = bibtexparser.loads(text, parser=parser).entries_dict
    except:
        msg = 'Encountered an error while processing {}.'.format(bib_path)
        raise LibraryException(msg)

    key = list(bibtex.keys())[0]
    return bibtex[key], text


def _parse_bibtex(bibtex):
    ''' Parse the bibtex. All documents must have at least a title, author, and
        year. '''
    key = bibtex['ID']
    entrytype = bibtex['ENTRYTYPE']

    try:
        title = bibtex['title']
    except KeyError:
        raise LibraryException('No title field in bibtex of {}.'.format(key))

    try:
        authors = bibtex['author'].split(' and ')
    except KeyError:
        raise LibraryException('No author field in bibtex of {}.'.format(key))

    try:
        year = bibtex['year']
    except KeyError:
        raise LibraryException('No year field in bibtex of {}.'.format(key))

    if entrytype == 'journal':
        venue = bibtex['journal']
    elif entrytype == 'inproceedings':
        venue = bibtex['booktitle']
    else:
        venue = None

    return title, authors, year, venue, entrytype


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

        self.bibtex, self.bibtex_str = _load_bibtex(paths.bib_path)
        info = _parse_bibtex(self.bibtex)
        self.title, self.authors, self.year, self.venue, self.entrytype = info

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

    def matches(self, key_pattern=None, title_pattern=None,
                author_pattern=None, year_pattern=None, venue_pattern=None,
                entrytype_pattern=None, text_pattern=None):
        ''' Return True if the document matches the patterns supplied for key,
            title, author, year, and venue. False otherwise. '''

        num_matches = 0

        if key_pattern and not re.search(key_pattern, self.key, re.IGNORECASE):
            return False, num_matches

        if title_pattern and not re.search(title_pattern, self.title,
                                           re.IGNORECASE):
            return False, num_matches

        # Author can be a space-separated list.
        if author_pattern:
            for author in author_pattern.split(' '):
                if not re.search(author, ' '.join(self.authors),
                                 re.IGNORECASE):
                    return False, num_matches

        # Year can be a single number or a range NNNN-NNNN.
        if year_pattern:
            if '-' in year_pattern:
                years = year_pattern.split('-')
                first = int(years[0])
                last  = int(years[1])
                years = list(range(first, last + 1))
                if int(self.year) not in years:
                    return False, num_matches
            elif year_pattern != self.year:
                return False, num_matches

        if venue_pattern:
            if not self.venue or not re.search(venue_pattern, self.venue,
                                               re.IGNORECASE):
                return False, num_matches

        # Entry type is a simple field so we just do a simple substring check.
        if entrytype_pattern:
            if entrytype_pattern not in self.entrytype:
                return False, num_matches

        if text_pattern:
            text, _ = self.text()
            num_matches = len(re.findall(text_pattern, text, re.IGNORECASE))
            if num_matches == 0:
                return False, num_matches

        return True, num_matches


def _pattern_to_regex(pattern):
    if pattern:
        return re.compile(pattern, re.IGNORECASE)
    return None


def _parse_author_pattern(pattern):
    if pattern:
        authors = pattern.split(' ')
        regexes = [re.compile(author, re.IGNORECASE) for author in authors]
        return regexes
    return None


def _parse_year_pattern(pattern):
    if pattern:
        if '-' in pattern:
            years = pattern.split('-')
            first = int(years[0])
            last  = int(years[1])
            years = [str(year) for year in range(first, last + 1)]
            return years
        return [pattern]
    return None


class DocumentTemplate(object):
    def __init__(self, key_pattern=None, title_pattern=None,
                 author_pattern=None, year_pattern=None, venue_pattern=None,
                 entrytype_pattern=None, text_pattern=None):
        # Syntax: _pattern = string type, _regex = regex type
        self.key_regex = _pattern_to_regex(key_pattern)
        self.title_regex = _pattern_to_regex(title_pattern)
        self.author_regexes = _parse_author_pattern(author_pattern)
        self.years = _parse_year_pattern(year_pattern)
        self.venue_regex = _pattern_to_regex(venue_pattern)
        self.entrytype_pattern = entrytype_pattern
        self.text_regex = _pattern_to_regex(text_pattern)

    def key(self, key):
        return not self.key_regex or self.key_regex.search(key)

    def title(self, title):
        return not self.title_regex or self.title_regex.search(title)

    def authors(self, authors):
        authors = ' '.join(authors)
        for regex in self.author_regexes:
            if not regex.search(authors):
                return False
        return True

    def year(self, year):
        return not self.years or year in self.years

    def venue(self, venue):
        return not self.venue_regex or self.venue_regex.search(venue)

    def entrytype(self, entrytype):
        return not self.entrytype_pattern or self.entrytype_pattern in entrytype

    def text(self, text):
        if not self.text_regex:
            return True, 0
        count = self.text_regex.findall(text)
        if count == 0:
            return False, 0
        return True, count

    # TODO don't include this: Document's responsibility
    # def all(self, key, title, author, year, venue, entrytype, text):
    #     pass

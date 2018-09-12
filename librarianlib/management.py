import datetime
import hashlib
import os
import shutil
import yaml

import bibtexparser
import bibtexparser.customization as customization
from bibtexparser.bwriter import BibTexWriter
import textract

from .exceptions import LibraryException


HASH_FILE_BUFFER_SIZE = 65536


def find_config(search_dirs, config_name):
    ''' Find the path to the configuration file. '''
    for search_dir in search_dirs:
        path = os.path.join(search_dir, config_name)
        if os.path.exists(path):
            return path
    return None


def hash_pdf(pdf_path):
    ''' Generate an MD5 hash of a PDF file. '''
    md5 = hashlib.md5()

    with open(pdf_path, 'rb') as f:
        while True:
            data = f.read(HASH_FILE_BUFFER_SIZE)
            if not data:
                break
            md5.update(data)

    return md5.hexdigest()


def parse_pdf_text(pdf_path):
    ''' Extract plaintext content of a PDF file. '''
    return textract.process(pdf_path).decode('utf-8')


def key_from_bibtex(bib_path):
    ''' Extract the document key from a bibtex file. '''
    with open(bib_path) as bib_file:
        bib_info = bibtexparser.load(bib_file)

    keys = list(bib_info.entries_dict.keys())
    if len(keys) > 1:
        raise LibraryException('More than one entry in bibtex file.')

    return keys[0]


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

        # Dates.
        self.added_date = self._read_date('added.txt')
        self.accessed_date = self._read_date('accessed.txt')

    def _read_date(self, fname):
        path = os.path.join(self.paths.metadata_path, fname)
        if os.path.exists(path):
            with open(path) as f:
                date = f.read()
            return datetime.date.strptime(date, '%Y-%m-%d')
        else:
            date = datetime.date.today()
            with open(path, 'w') as f:
                f.write(date.isoformat())
            return date

    def text(self):
        ''' Retrieve the plain text of the PDF file. '''
        current_hash = hash_pdf(self.paths.pdf_path)

        if os.path.exists(self.paths.hash_path):
            with open(self.paths.hash_path) as f:
                old_hash = f.read()
        else:
            old_hash = None

        if (not os.path.exists(self.paths.text_path)
                or not os.path.exists(self.paths.hash_path)
                or current_hash != old_hash):
            text = parse_pdf_text(self.pdf_path)
            with open(self.paths.hash_path, 'w') as f:
                f.write(current_hash)
            with open(self.paths.text_path, 'w') as f:
                f.write(text)

        return text

    def access(self):
        ''' Update the access date to today. '''
        self.accessed_date = datetime.date.today()
        with open(self.paths.accessed_path, 'w') as f:
            f.write(self.accessed.isoformat())


class Archive(object):
    ''' Provides convenience functions to interact with the library's archive.
        '''
    def __init__(self, path):
        self.path = path

    def add(self, pdf_path, bib_path):
        ''' Create a new document in the archive. '''
        key = key_from_bibtex(bib_path)

        if self.contains(key):
            msg = 'Archive already contains key {}. Aborting.'.format(key)
            raise LibraryException(msg)

        # Create document structure.
        paths = DocumentPaths(self.path, key)
        os.mkdir(paths.key_path)
        os.mkdir(paths.metadata_path)
        shutil.copy(pdf_path, paths.pdf_path)
        shutil.copy(bib_path, paths.bib_path)

        return ArchivalDocument(key, paths)

    def rekey(self, old_key, new_key):
        ''' Rename a document in the archive. '''
        old_paths = self.retrieve(old_key).paths

        # If a new key has not been supplied, we take the key from the bibtex
        # file.
        if new_key is None:
            new_key = key_from_bibtex(old_paths.bib_path)

        if self.contains(new_key):
            msg = 'Archive already contains key {}. Aborting.'.format(new_key)
            raise LibraryException(msg)

        new_paths = DocumentPaths(self.path, new_key)

        shutil.move(old_paths.pdf_path, new_paths.pdf_path)
        shutil.move(old_paths.bib_path, new_paths.bib_path)
        shutil.move(old_paths.key_path, new_paths.key_path)

        # Write the new_key to the bibtex file
        with open(new_paths.bib_path, 'r+') as f:
            bib_info = bibtexparser.load(f)
            bib_info.entries[0]['ID'] = new_key
            bib_writer = BibTexWriter()
            f.write(bib_writer.write(bib_info))

    def retrieve(self, key=None):
        ''' Retrieve documents from the archive. '''
        # If the key is a string, return the single document.
        if type(key) == str:
            if not self.contains(key):
                raise Exception('Key {} not found in archive.'.format(key))
            return ArchivalDocument(self.path, key)

        if key is None:
            keys = os.listdir(self.path)
        else:
            keys = key

        docs = []
        for key in keys:
            if not self.contains(key):
                raise Exception('Key {} not found in archive.'.format(key))
            paths = DocumentPaths(self.path, key)
            doc = ArchivalDocument(key, paths)
            docs.append(doc)

        return docs

    def contains(self, key):
        ''' Returns True if the key is in the archive, false otherwise. '''
        path = os.path.join(self.path, key)
        return os.path.isdir(path)


class LibraryManager(object):
    def __init__(self, search_dirs, config_name):
        config_file_path = find_config(search_dirs, config_name)
        if config_file_path is None:
            raise LibraryException('Could not find config file.')

        with open(config_file_path) as f:
            config = yaml.load(f)

        self.root = os.path.expanduser(config['library'])

        self.paths = {
            'root': self.root,
            'archive': os.path.join(self.root, 'archive'),
            'shelves': os.path.join(self.root, 'shelves'),
            'bookmarks': os.path.join(self.root, 'bookmarks'),
        }

        self.archive = Archive(self.paths['archive'])

        # Check if each of these directories exist.
        # TODO perhaps just make the directory rather than raising an error
        for key in ['root', 'archive', 'shelves']:
            if not os.path.isdir(self.paths[key]):
                message = '{} does not exist!'.format(self.paths[key])
                raise LibraryException(message)

    def bibtex_dict(self, extra_customization=None):
        ''' Load bibtex information as a dictionary. '''
        def _bibtex_customizations(record):
            record = customization.convert_to_unicode(record)

            # Make authors semicolon-separated rather than and-separated.
            record['author'] = record['author'].replace(' and', ';')

            # Apply extra customization function is applicable.
            if extra_customization:
                record = extra_customization(record)
            return record

        # We parse each string of bibtex separately and then merge the
        # resultant dictionaries together, so that we can handle malformed
        # bibtex files individually.
        entries_dict = {}
        for doc in self.archive.retrieve():
            bib_text = doc.bibtex
            # common_strings=True lets us parse the month field as "jan",
            # "feb", etc.
            parser = bibtexparser.bparser.BibTexParser(
                    customization=_bibtex_customizations,
                    common_strings=True)
            try:
                d = bibtexparser.loads(bib_text, parser=parser).entries_dict
            except:
                bib_file = os.path.basename(doc.paths.bib_path)
                print('Encountered an error while processing {}.'.format(bib_file))
                continue
            entries_dict.update(d)
        return entries_dict

    def add(self, pdf_src_path, bib_src_path):
        ''' Add a new document to the archive. Returns the document. '''
        return self.archive.add(pdf_src_path, bib_src_path)

    def rekey(self, old_key, new_key):
        ''' Change the key of an existing document in the archive. '''
        self.archive.rekey(old_key, new_key)

    def link(self, key, path):
        ''' Create a symlink to a document in the archive. '''
        path = path if path is not None else key

        src = self.archive.retrieve(key).paths.key_path

        if os.path.isabs(path):
            dest = path
        else:
            dest = os.path.join(os.getcwd(), path)

        if os.path.exists(dest):
            message = 'Symlink {} already exists. Aborting.'.format(path)
            raise LibraryException(message)

        os.symlink(src, dest)

    def fix_link(self, link):
        ''' Fix a link that has broken due to the library being moved. '''
        if not os.path.islink(link):
            raise LibraryException('{} is not a symlink.'.format(link))

        key = os.path.basename(os.readlink(link))

        if not self.archive.contains(key):
            print('{} does not point to a document in the archive.'.format(link))
            return 1

        # Recreate the link, pointing to the correct location.
        os.remove(link)
        self.link(key, link)

    def fix_links(self, directory):
        ''' Fix all broken links in the directory. '''
        files = os.listdir(directory)
        for link in filter(os.path.islink, files):
            self.fix_link(link)

    def bookmark(self, key, name):
        ''' Create a bookmark 'name' pointing to the key. '''
        # Create the bookmarks directory if it doesn't already exist.
        if not os.path.isdir(self.paths['bookmarks']):
            os.mkdir(self.paths['bookmarks'])
            print('Created bookmarks directory at: {}'.format(self.paths['bookmarks']))

        name = name if name is not None else key
        path = os.path.join(self.paths['bookmarks'], name)
        self.link(key, path)

import datetime
import hashlib
import glob
import os
import shutil
import yaml

import bibtexparser
import bibtexparser.customization as customization
import textract

from .exceptions import LibraryException


def find_config(search_dirs, config_name):
    ''' Find the path to the configuration file. '''
    for search_dir in search_dirs:
        path = os.path.join(search_dir, config_name)
        if os.path.exists(path):
            return path
    return None


def parse_key(key):
    ''' Clean up a user-supplied document key. '''
    # When completing, the user may accidentally include a trailing slash.
    if key[-1] == '/':
        key = key[:-1]

    # If a nested path is given, we just want the last piece.
    return key.split(os.path.sep)[-1]


# class Document(object):
#     def __init__(self, pdf_path, bib_path):
#         self.pdf_path = pdf_path
#         self.bib_path = bib_path
#
#         with open(bib_path) as bib_file:
#             bib_info = bibtexparser.load(bib_file)
#
#         keys = list(bib_info.entries_dict.keys())
#         if len(keys) > 1:
#             raise Exception('More than one entry in bibtex file.')
#         self.key = keys[0]


BUF_SIZE = 65536


def hash_pdf(fname):
    md5 = hashlib.md5()

    with open(fname, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            md5.update(data)

    return md5.hexdigest()


def parse_pdf_text(pdf_path):
    return textract.process(pdf_path).decode('utf-8')


def key_from_bibtex(bib_path):
    with open(bib_path) as bib_file:
        bib_info = bibtexparser.load(bib_file)

    keys = list(bib_info.entries_dict.keys())
    if len(keys) > 1:
        raise LibraryException('More than one entry in bibtex file.')

    return keys[0]


class ArchivalDocument(object):
    ''' A document in an archive. '''
    # path contains key
    def __init__(self, path, key):
        self.path = path
        self.key = key

        self.pdf_path = os.path.join(self.path, key + '.pdf')
        self.bib_path = os.path.join(self.path, key + '.bib')

        with open(self.bib_path) as f:
            self.bibtex = f.read().strip()

        def _read_date(fname):
            metadata_path = os.path.join(self.key_path, '.metadata')
            path = os.path.join(metadata_path, fname)
            if os.path.exists(path):
                with open(path) as f:
                    date = f.read()
                return datetime.date.strptime(date, '%Y-%m-%d')
            else:
                date = datetime.date.today()
                with open(path, 'w') as f:
                    f.write(date.isoformat())
                return date

        # Dates.
        self.added = _read_date('added.txt')
        self.accessed = _read_date('accessed.txt')

    def text(self):
        ''' Retrieve the plain text of the PDF file. '''
        metadata_path = os.path.join(self.key_path, '.metadata')
        hash_path = os.path.join(metadata_path, 'hash.md5')
        text_path = os.path.join(metadata_path, 'text.txt')

        current_hash = hash_pdf(self.pdf_path)
        if os.path.exists(hash_path):
            with open(hash_path) as f:
                old_hash = f.read()
        else:
            old_hash = None

        if (not os.path.exists(text_path) or not os.path.exists(hash_path)
                or current_hash != old_hash):
            text = parse_pdf_text(self.pdf_path)
            with open(hash_path, 'w') as f:
                f.write(current_hash)
            with open(text_path, 'w') as f:
                f.write(text)

        return text

    def access(self):
        ''' Update the access date to today. '''
        self.accessed = datetime.date.today()
        accessed_path = os.path.join(self.key_path, '.metadata', 'accessed.txt')
        with open(accessed_path, 'w') as f:
            f.write(self.accessed.isoformat())

    def files(self):
        ''' Convenient list of files. '''
        # TODO is this needed?
        return self.path, self.pdf_path, self.bib_path

    @staticmethod
    def load(archive, key):
        return ArchivalDocument(os.path.join(archive.path, key), key)


class Archive(object):
    ''' Provides convenience functions to interact with the library's archive.
        '''
    def __init__(self, path):
        self.path = path

    def add(self, pdf_path, bib_path):
        key = key_from_bibtex(bib_path)

        if self.contains(key):
            msg = 'Archive already contains key {}. Aborting.'.format(key)
            raise LibraryException(msg)

        doc_path = os.path.join(self.path, key)
        pdf_dest_path = os.path.join(doc_path, key + '.pdf')
        bib_dest_path = os.path.join(doc_path, key + '.bib')

        # Create directory and copy in PDF and bibtex files.
        os.mkdir(doc_path)
        os.mkdir(os.path.join(doc_path, '.metadata'))
        shutil.copy(pdf_path, pdf_dest_path)
        shutil.copy(bib_path, bib_dest_path)

        return ArchivalDocument(doc_path, key)

    # TODO this should just be rekey, from below
    def update(self, key, doc):
        # Update doc pointed to by key with data from doc
        pass

    def retrieve(self, key='*'):
        if type(key) == str:
            if not self.contains(key):
                raise Exception('Key {} not found in archive.'.format(key))
            return ArchivalDocument(os.path.join(self.path, key), key)

        if key == '*':
            keys = os.listdir(self.path)
        else:
            keys = key

        docs = []
        for key in keys:
            if not self.contains(key):
                raise Exception('Key {} not found in archive.'.format(key))
            docs.append(ArchivalDocument(os.path.join(self.path, key), key))

        return docs

    def contains(self, key):
        ''' Returns True if the key is in the archive, false otherwise. '''
        path = os.path.join(self.path, key)
        return os.path.isdir(path)

    def has_key(self, key):
        ''' Returns True if the key is in the archive, false otherwise. '''
        path = os.path.join(self.path, key)
        return os.path.isdir(path)

    def all_keys(self):
        ''' Returns a list of all keys in the archive. '''
        return os.listdir(self.path)

    def all_bibtex_files(self):
        ''' Returns a list of paths of all bibtex files in the archive. '''
        return glob.glob(self.path + '/**/*.bib')

    def all_pdf_files(self):
        ''' Returns a list of paths of all PDF files in the archive. '''
        return glob.glob(self.path + '/**/*.pdf')

    def key_path(self, key):
        ''' Returns the path to the key. '''
        return os.path.join(self.path, key)

    def bib_path(self, key):
        ''' Returns the path to the bibtex file of the key. '''
        return os.path.join(self.key_path(key), key + '.bib')

    def pdf_path(self, key):
        ''' Returns the path to the PDF file of the key. '''
        return os.path.join(self.key_path(key), key + '.pdf')

    def pdf_to_key(self, pdf):
        ''' Convert a PDF path to its key name. '''
        base = os.path.basename(pdf)
        return base.split('.')[0]

    def pdfs():
        pass

    def keys():
        pass


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

    def bibtex_list(self):
        ''' Create a list of the contents of all bibtex files in the archive. '''
        bib_list = []
        bib_files = self.archive.all_bibtex_files()

        for bib_path in bib_files:
            with open(bib_path) as bib_file:
                bib_list.append(bib_file.read().strip())

        return zip(bib_list, bib_files)

    def bibtex_dict(self, extra_customization=None):
        ''' Load bibtex information as a dictionary. '''
        def customizations(record):
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
        bibtex = self.bibtex_list()
        for bibstr, bibfile in bibtex:
            # common_strings=True lets us parse the month field as "jan",
            # "feb", etc.
            parser = bibtexparser.bparser.BibTexParser(
                    customization=customizations,
                    common_strings=True)
            try:
                d = bibtexparser.loads(bibstr, parser=parser).entries_dict
            except:
                print('Encountered an error while processing {}.'.format(bibfile))
                continue
            entries_dict.update(d)
        return entries_dict

    def add(self, key, pdf_src_path, bib_src_path):
        key = parse_key(key)

        if self.archive.has_key(key):
            message = 'Archive {} already exists! Aborting.'.format(key)
            raise LibraryException(message)

        os.mkdir(self.archive.key_path(key))

        pdf_dest_path = self.archive.pdf_path(key)
        bib_dest_path = self.archive.bib_path(key)

        shutil.copy(pdf_src_path, pdf_dest_path)
        shutil.copy(bib_src_path, bib_dest_path)

    def rekey(self, key, new_key):
        pdf_src_path = self.archive.pdf_path(key)
        bib_src_path = self.archive.bib_path(key)

        # First rename the PDF and bibtex files.
        key_path = self.archive.key_path(key)
        pdf_dest_path = os.path.join(key_path, new_key + '.pdf')
        bib_dest_path = os.path.join(key_path, new_key + '.bib')

        shutil.move(pdf_src_path, pdf_dest_path)
        shutil.move(bib_src_path, bib_dest_path)

        # Rename the directory.
        new_key_path = self.archive.key_path(new_key)
        shutil.move(key_path, new_key_path)

    def link(self, key, path):
        key = parse_key(key)
        path = path if path is not None else key

        src = self.archive.retrieve(key).path

        if os.path.isabs(path):
            dest = path
        else:
            dest = os.path.join(os.getcwd(), path)

        if os.path.exists(dest):
            message = 'Symlink {} already exists. Aborting.'.format(path)
            raise LibraryException(message)

        os.symlink(src, dest)

    def bookmark(self, key, name):
        # Create the bookmarks directory if it doesn't already exist.
        if not os.path.isdir(self.paths['bookmarks']):
            os.mkdir(self.paths['bookmarks'])
            print('Created bookmarks directory at: {}'.format(self.paths['bookmarks']))

        name = name if name is not None else key
        path = os.path.join(self.paths['bookmarks'], name)
        self.link(key, path)

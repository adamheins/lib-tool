# Built-in.
import os
import shutil
import yaml

# Third party.
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
import pyparsing

# Ours.
from .document import DocumentPaths, ArchivalDocument, DocumentTemplate
from .exceptions import LibraryException


def _find_config(search_dirs, config_name):
    ''' Find the path to the configuration file. '''
    for search_dir in search_dirs:
        path = os.path.join(search_dir, config_name)
        if os.path.exists(path):
            return path
    return None


def _key_from_bibtex(bib_path):
    ''' Extract the document key from a bibtex file. '''
    with open(bib_path) as bib_file:
        try:
            bib_info = bibtexparser.load(bib_file)
        except pyparsing.ParseException:
            raise LibraryException('Failed to parse bibtex file.')

    keys = list(bib_info.entries_dict.keys())
    if len(keys) > 1:
        raise LibraryException('More than one entry in bibtex file.')

    return keys[0]


class LibraryManager(object):
    ''' Manager for the library. Handles all interactions with it. '''
    def __init__(self, search_dirs, config_name):
        config_file_path = _find_config(search_dirs, config_name)
        if config_file_path is None:
            raise LibraryException('Could not find config file.')

        with open(config_file_path) as f:
            config = yaml.load(f)

        self.path = os.path.expanduser(config['library'])
        self.archive_path = os.path.join(self.path, 'archive')

        # Check that the archive exists.
        if not os.path.isdir(self.archive_path):
            msg = '{} does not exist!'.format(self.archive_path)
            raise LibraryException(msg)

    def has_key(self, key):
        ''' Returns True if the key is in the archive, false otherwise. '''
        return os.path.isdir(os.path.join(self.archive_path, key))

    def all_docs(self):
        ''' Return all documents in the library. '''
        docs = []
        for key in os.listdir(self.archive_path):
            paths = DocumentPaths(self.archive_path, key)
            docs.append(ArchivalDocument(key, paths))
        return docs

    def all_keys(self):
        ''' List all keys without the overhead of creating full documents for
            each. '''
        return os.listdir(self.archive_path)

    def get_doc(self, key):
        ''' Return a single document from the library. '''
        if not self.has_key(key):
            raise Exception('Key {} not found in archive.'.format(key))
        paths = DocumentPaths(self.archive_path, key)
        return ArchivalDocument(key, paths)

    def add(self, pdf_src_path, bib_src_path):
        ''' Add a new document to the archive. Returns the document. '''
        key = _key_from_bibtex(bib_src_path)

        if self.has_key(key):
            msg = 'Archive already contains key {}. Aborting.'.format(key)
            raise LibraryException(msg)

        # Create document structure.
        paths = DocumentPaths(self.archive_path, key)
        os.mkdir(paths.key_path)
        os.mkdir(paths.metadata_path)
        shutil.copy(pdf_src_path, paths.pdf_path)
        shutil.copy(bib_src_path, paths.bib_path)

        return ArchivalDocument(key, paths)

    def rekey(self, old_key, new_key):
        ''' Change the key of an existing document in the archive. '''
        old_paths = self.get_doc(old_key).paths

        # If a new key has not been supplied, we take the key from the bibtex
        # file.
        if new_key is None:
            new_key = _key_from_bibtex(old_paths.bib_path)

        if self.has_key(new_key):
            msg = 'Archive already contains key {}. Aborting.'.format(new_key)
            raise LibraryException(msg)

        new_paths = DocumentPaths(self.archive_path, new_key)

        # Rename PDF and bibtex file and then rename the whole directory.
        shutil.move(old_paths.bib_path,
                    os.path.join(old_paths.key_path, new_key + '.bib'))
        shutil.move(old_paths.pdf_path,
                    os.path.join(old_paths.key_path, new_key + '.pdf'))
        shutil.move(old_paths.key_path, new_paths.key_path)

        # Write the new_key to the bibtex file
        with open(new_paths.bib_path, 'r') as f:
            bib_info = bibtexparser.load(f)

        bib_info.entries[0]['ID'] = new_key
        bib_writer = BibTexWriter()
        with open(new_paths.bib_path, 'w') as f:
            f.write(bib_writer.write(bib_info))

        return new_key

    def link(self, key, path):
        ''' Create a symlink to a document in the archive. '''
        path = path if path is not None else key

        src = self.get_doc(key).paths.key_path

        if os.path.isabs(path):
            dest = path
        else:
            dest = os.path.join(os.getcwd(), path)

        if os.path.exists(dest):
            msg = 'Symlink {} already exists. Aborting.'.format(path)
            raise LibraryException(msg)

        os.symlink(src, dest)

    def fix_link(self, link):
        ''' Fix a link that has broken due to the library being moved. '''
        if not os.path.islink(link):
            raise LibraryException('{} is not a symlink.'.format(link))

        key = os.path.basename(os.readlink(link))

        if not self.has_key(key):
            msg = 'No document with key {} is in the archive.'.format(link)
            raise LibraryException(msg)

        # Recreate the link, pointing to the correct location.
        os.remove(link)
        self.link(key, link)

    def fix_links(self, directory):
        ''' Fix all broken links in the directory. '''
        files = os.listdir(directory)
        for link in filter(os.path.islink, files):
            self.fix_link(link)

    def tag(self, key, tags):
        ''' Apply one or more tags to a document.
            Params:
                key - Key for document to tag.
                tags - Comma-separated string of tags.
            Returns:
                None '''
        self.get_doc(key).tag(tags)

    def get_tags(self):
        ''' Get a list of (tag, count) tuples, ordered from most to least
            frequent. '''
        tag_count_map = {}
        for doc in self.all_docs():
            for tag in doc.tags:
                if tag in tag_count_map:
                    tag_count_map[tag] += 1
                else:
                    tag_count_map[tag] = 1
        tag_count_list = [(tag, count) for tag, count in tag_count_map.items()]
        tag_count_list.sort(key=lambda x: x[1], reverse=True)
        return tag_count_list

    def rename_tag(self, current_tag, new_tag):
        ''' Rename all instances of a tag.
            Params:
                current_tag - Current name of the tag.
                new_tag - New tag name.
            Returns:
                None '''
        for doc in self.all_docs():
            doc.rename_tag(current_tag, new_tag)

    def search_docs(self, key=None, title=None, author=None, year=None,
                    venue=None, entrytype=None, text=None, tags=None,
                    sort=None, reverse=False):
        ''' Search documents for those that match the provided filters and
            produce a summary of the results. '''
        # Find documents matching the criteria.
        tmpl = DocumentTemplate(key, title, author, year, venue, entrytype,
                                text, tags)
        docs = []
        counts = []
        for doc in self.all_docs():
            result, count = doc.matches(tmpl)
            if result:
                docs.append(doc)
                counts.append(count)

        # Sort the matching documents.
        if sort:
            def _doc_sort_key(doc_count_tuple):
                doc, count = doc_count_tuple

                if sort == 'key':
                    return doc.key
                if sort == 'title':
                    return doc.bibtex['title'].lower()
                if sort == 'year':
                    return doc.bibtex['year']
                if sort == 'added':
                    return doc.added_date
                if sort == 'accessed':
                    return doc.accessed_date
                if sort == 'matches':
                    return count
                return doc.bibtex['year']

            if sort not in ['key', 'title']:
                reverse = not reverse
            docs_counts = sorted(zip(docs, counts), key=_doc_sort_key,
                                 reverse=reverse)
            docs, counts = tuple(zip(*docs_counts))

        return zip(docs, counts)

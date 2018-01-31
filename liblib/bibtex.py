import glob

import bibtexparser
import bibtexparser.customization as bibcust


def compile_bib_info(archive_root):
    ''' Compile all bibtex information into a single string. '''
    bib_list = glob.glob(archive_root + '/**/*.bib')
    bib_info_list = []

    for bib_path in bib_list:
        with open(bib_path) as bib_file:
            bib_info_list.append(bib_file.read().strip())

    return '\n\n'.join(bib_info_list)


def load_bib_dict(archive_path, extra_cust=None):
    ''' Load bibtex information as a dictionary. '''
    def customizations(record):
        record = bibcust.convert_to_unicode(record)

        # Make authors semicolon-separated rather than and-separated.
        record['author'] = record['author'].replace(' and', ';')

        # Apply extra customization function is applicable.
        if extra_cust:
            record = extra_cust(record)
        return record

    parser = bibtexparser.bparser.BibTexParser()
    parser.customization = customizations

    bib_info = compile_bib_info(archive_path)
    return bibtexparser.loads(bib_info, parser=parser).entries_dict

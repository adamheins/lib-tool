import hashlib
import os

import textract

from . import style


BUF_SIZE = 65536


def hash_file(fname):
    md5 = hashlib.md5()

    with open(fname, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            md5.update(data)

    return md5.hexdigest()


def text_file_name(manager, key):
    fname = '.' + key + '.txt'
    key_path = manager.archive.key_path(key)
    return os.path.join(key_path, fname)


def hash_file_name(manager, key):
    fname = '.' + key + '.md5'
    key_path = manager.archive.key_path(key)
    return os.path.join(key_path, fname)


def read_file_hash(fname):
    if os.path.exists(fname):
        with open(fname, 'r') as f:
            return f.read()
    return None


def write_file_hash(fname, fhash):
    with open(fname, 'w') as f:
        f.write(fhash)


def read_text_file(fname):
    with open(fname, 'r') as f:
        return f.read()


def write_text_file(fname, text):
    with open(fname, 'w') as f:
        f.write(text)


def parse_pdf_text(pdf):
    return textract.process(pdf).decode('utf-8')


def highlighter(match):
    return style.yellow(match.group(0))


def count_message(key, count):
    if count == 1:
        return '{}: 1 match'.format(style.bold(key))
    elif count > 1:
        return '{}: {} matches'.format(style.bold(key), count)


def search_text(manager, regex, oneline, verbose=False):
    ''' Search for the regex in the PDF documents. '''
    # We assume that we want to search the whole corpus. For single document
    # searches, open the doc in a PDF viewer.
    results = []

    for pdf in manager.archive.all_pdf_files():
        key = manager.archive.pdf_to_key(pdf)

        hash_fname = hash_file_name(manager, key)
        text_fname = text_file_name(manager, key)

        old_hash = read_file_hash(hash_fname)
        current_hash = hash_file(pdf)

        # If the document has changed (as indicated by a different or
        # non-preexisting hash), we need to extract it's text.
        if current_hash != old_hash:
            write_file_hash(hash_fname, current_hash)
            text = parse_pdf_text(pdf)
            write_text_file(text_fname, text)

            if verbose:
                print('Indexed {}.'.format(key))
        else:
            text = read_text_file(text_fname)

        count = len(regex.findall(text))
        if count > 0:
            results.append({'key': key, 'count': count, 'detail': ''})

    # Sort and parse the results.
    output = []
    for result in sorted(results, key=lambda result: result['count'],
                         reverse=True):
        file_output = count_message(result['key'], result['count'])
        output.append(file_output)

    if len(output) == 0:
        return 'No matches in text.'
    elif oneline:
        return '\n'.join(output)
    else:
        return '\n'.join(output) # TODO when more detail is given, use two \n\n


def search_bibtex(manager, regex, oneline):
    ''' Search for the regex in bibtex file. '''
    results = []

    for key, info in manager.bibtex_dict().items():
        count = 0
        detail = []
        for field, value in info.items():
            # Skip the ID field; it's already a composition of parts of
            # other fields.
            if field == 'ID':
                continue

            # Find all the matches.
            matches = regex.findall(value)
            count += len(matches)
            if len(matches) == 0:
                continue

            # Highlight the matches.
            s = regex.sub(highlighter, value)
            detail.append('  {}: {}'.format(field, s))

        if count > 0:
            results.append({'key': key, 'count': count, 'detail': detail})

    # Sort and parse the results.
    output = []
    for result in sorted(results, key=lambda result: result['count'],
                         reverse=True):
        file_output = [count_message(result['key'], result['count'])]
        if not oneline:
            file_output.append('\n'.join(result['detail']))
        output.append('\n'.join(file_output))

    if len(output) == 0:
        return 'No matches in bibtex.'
    elif oneline:
        return '\n'.join(output)
    else:
        return '\n\n'.join(output)

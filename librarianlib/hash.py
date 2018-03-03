import hashlib


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

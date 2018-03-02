# librarian
A simple CLI-based document organization tool.

Documents should be organized in the following manner:
```
library/
  archive/
  shelves/
```
The `archive` directory contains all of the documents, each of which has its
own directory containing the actual PDF file and an associated bibtex file. The
name of the directory and each of the two files (ignoring file extensions)
should be named after the the key in the bibtex file.

The `shelves` directory may contain an arbitrary directory structure with
symlinks into the archive, such that the documents can be organized in any way.

The `lib` tool provides a convenient way to interact with this structure. It
currently has the following commands:
* `add` - Add a PDF and bibtex file to the archive.
* `ln` - Create a symlink to a document in the archive.
* `index` - Generate an HTML file listing all documents.
* `compile` - Compile a single directory of every PDF or a single bibtex file
  for all documents.
* `open` - Open a document or bibtex file.
* `where` - Print library paths.

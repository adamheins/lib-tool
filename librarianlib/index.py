import os


ENTRY_TEMPLATE = '''
<div class="post">
    <h2><a href={path}>{title}</a></h2>
    <div class="date">{year}</div>
    <p class="description">{authors}</p>
</div>'''


ARCHIVE_TEMPLATE = '''
<html>
    <head>
        <title>Archive</title>
        <link rel="stylesheet" href="https://static.adamheins.com/css/layout.css"/>
        <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Open+Sans:400,300,300italic"/>
    </head>
    <body>
        <div class="container">
            <div class="content">
                <section>
                    <h1>Archive</h1>
                </section>
                <section>{entries}</section>
            </div>
        </div>
    </body>
</html>
'''


def entry_html(data, pdf_path):
    return ENTRY_TEMPLATE.format(path=pdf_path, title=data['title'],
                                 year=data['year'], authors=data['author'])


def html(manager, bib_dict):
    # Sort the documents by year, with most recent first.
    def entry_year(item):
        return item[1]['year']
    entries = sorted(bib_dict.items(), key=entry_year, reverse=True)

    # Generate HTML for each entry.
    def entry_to_html(item):
        # item[0] is the bibtex key, item[1] is the bibtex data
        return entry_html(item[1], manager.archive.pdf_path(item[0]))
    entries = map(entry_to_html, entries)

    return ARCHIVE_TEMPLATE.format(entries=''.join(entries))

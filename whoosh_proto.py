import whoosh.query
from whoosh.fields import ID, Schema, TEXT
from whoosh.index import create_in
from whoosh.qparser import QueryParser


schema = Schema(index=ID(stored=True), content=TEXT(stored=True))
ix = create_in("search", schema)

writer = ix.writer()
writer.add_document(
    index='1',
    content='spawned items',
)
writer.add_document(
    index='2',
    content='xp generation',
)
writer.add_document(
    index='3',
    content='xp buckets',
)
writer.commit()

while True:
    user_string = input('Enter search query: ')
    with ix.searcher() as searcher:
        # query = QueryParser("content", ix.schema).parse('spawn')
        query = whoosh.query.Variations('content', user_string)
        results = searcher.search(query)

        for i, hit in zip(range(1, 100000), results):
            print(i, hit.fields()['content'])
        print(results.has_matched_terms())
        # for hit in results:
        #     print(hit.matched_terms())
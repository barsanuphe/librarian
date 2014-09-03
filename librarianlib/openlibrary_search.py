import requests, json
from .epub import Epub

class OpenLibrarySearch(object):

    def __init__(self):
        self.search_url = "http://openlibrary.org/search.json?%s"
        self.works_url = "https://openlibrary.org/works/%s.json"

    def display_hit(self, hits, i):
        assert i < len(hits)
        hit = hits[i]
        print("Author:", ",".join(hit["author_name"]))
        print("Title:", hit["title"])
        print("First published:", hit.get("first_publish_year", "XXXX"))
        #print("\n".join(hit.get("first_sentence", [])))
        about = requests.get(self.works_url%hit["key"])
        about_json = about.json()
        description = about_json.get("description", None)
        if description is not None:
            print("Description:", description.get("value", "no description found."))
        rep = input("(A)ccept, (N)ext, (P)revious? ").lower()
        if rep == "a":
            return hit
        elif rep == "n" and i < len(hits)-1:
            return self.display_hit(hits, i+1) #TODO test i
        elif rep == "p" and i != 0:
            return self.display_hit(hits, i-1) #TODO test i
        else:
            print("what?")

    def search(self, ebook):
        query = "author=%s&title=%s"%(ebook.metadata.author, ebook.metadata.title)
        #print(self.search_url%query.replace(" ", "+").replace("-", "+"))
        t = requests.get(self.search_url%query.replace(" ", "+").replace("-", "+"))
        hits = t.json().get("docs", None)
        if hits is not None and hits != []:
            chosen_hit = self.display_hit(hits, 0)

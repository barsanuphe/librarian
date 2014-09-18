import requests
from .epub import unread, reading, read


class SearchResult(object):
    def __init__(self, hit, description):
        self.author = ",".join(hit["author_name"])
        self.title = hit["title"]
        self.year = hit.get("first_publish_year", "XXXX")
        self.description = description

    def __str__(self):
        return "  Author: %s\n  Title: %s\n  First published: %s\n  Description: %s" % (self.author, self.title, self.year, self.description)

    def _diff(self, field, ebook):
        modified = "%s:\n    %s -> %s"
        values = ebook.metadata.get_values(field)
        if values == []:
            values = ["(not found)"]
        if ",".join(values) != getattr(self, field):
            print(modified % (reading(field.title()), unread(",".join(values)),
                            read(str(getattr(self, field)))))
            return True
        return False

    def compare_to_source(self, ebook):
        a = self._diff("author", ebook)
        t = self._diff("title", ebook)
        y = self._diff("year", ebook)
        d = self._diff("description", ebook)
        return (a or t or y or d)

    def copy_to_source(self, ebook):
        pass  # TODO


class OpenLibrarySearch(object):

    def __init__(self):
        self.search_url = "http://openlibrary.org/search.json?%s"
        self.works_url = "https://openlibrary.org/works/%s.json"

    def display_hit(self, hits, i):
        assert i < len(hits)
        hit = hits[i]
        about = requests.get(self.works_url % hit["key"])
        about_json = about.json()
        description = about_json.get("description", None)
        description_str = ""
        if description is not None:
            description_str = description.get("value", "no description found.")
        sr = SearchResult(hit, description_str)
        print(sr)
        rep = input("(A)ccept, (N)ext, (P)revious? ").lower()
        if rep == "a":
            return sr
        elif rep == "n" and i < len(hits)-1:
            return self.display_hit(hits, i+1)  # TODO test i
        elif rep == "p" and i != 0:
            return self.display_hit(hits, i-1)  # TODO test i
        else:
            print("what?")

    def search(self, ebook):
        query = "author=%s&title=%s" % (ebook.metadata.get_values("author")[0],
                                        ebook.metadata.get_values("title")[0])
        t = requests.get(self.search_url %
                         query.replace(" ", "+").replace("-", "+"))
        hits = t.json().get("docs", None)
        if hits is not None and hits != []:
            chosen_hit = self.display_hit(hits, 0)
        return chosen_hit

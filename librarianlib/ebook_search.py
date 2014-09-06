from collections import defaultdict

from .epub import Epub, ReadStatus

def fuzzy_search_in_list(searched, string_list, exact = False):
    for string in string_list:
        if not exact and searched in string:
            return True
        if exact and searched == string:
            return True
    return False

def is_ebook_a_match(search_string, ebook_field_list, exact = False):
    for field in ebook_field_list:
        if exact and search_string.strip() == field.lower():
            return True
        elif not exact and search_string.strip() in field.lower():
            return True
    return False


class EbookSearch(object):

    def __init__(self, all_ebooks):
        self.all_ebooks = all_ebooks

    def search_ebooks(self, search_string, exact_search = False):
        filtered = []
        search_string = search_string.lower()
        for eb in self.all_ebooks:
            if search_string.startswith("series:"):
                if is_ebook_a_match( search_string.split("series:")[1], eb.metadata.get_values("series"), exact_search):
                    filtered.append(eb)
            elif search_string.startswith("author:"):
                if is_ebook_a_match( search_string.split("author:")[1], eb.metadata.get_values("author"), exact_search):
                    filtered.append(eb)
            elif search_string.startswith("title:"):
                if is_ebook_a_match( search_string.split("title:")[1], eb.metadata.get_values("title"), exact_search):
                    filtered.append(eb)
            elif search_string.startswith("tag:"):
                if fuzzy_search_in_list(search_string.split("tag:")[1].strip(), eb.tags, exact_search):
                    filtered.append(eb)
            elif search_string.startswith("progress:"):
                if fuzzy_search_in_list(ReadStatus[search_string.split("progress:")[1].strip()], [eb.read], True):
                    filtered.append(eb)
            elif is_ebook_a_match( search_string, eb.metadata.get_values("series") + eb.metadata.get_values("author") + eb.metadata.get_values("title"), exact_search) or fuzzy_search_in_list(search_string, eb.tags, exact_search):
                filtered.append(eb)
        return sorted(filtered, key=lambda x: x.filename)

    def exclude_ebooks(self, ebooks_list, exclude_term):
        filtered = []
        exclude_term = exclude_term.lower()
        for eb in ebooks_list:
            if exclude_term.startswith("series:"):
                if not is_ebook_a_match( exclude_term.split("series:")[1], eb.metadata.get_values("series")):
                    filtered.append(eb)
            elif exclude_term.startswith("author:"):
                if not is_ebook_a_match( exclude_term.split("author:")[1], eb.metadata.get_values("author")):
                    filtered.append(eb)
            elif exclude_term.startswith("title:"):
                if not is_ebook_a_match( exclude_term.split("title:")[1], eb.metadata.get_values("title")) :
                    filtered.append(eb)
            elif exclude_term.startswith("tag:"):
                if not fuzzy_search_in_list(exclude_term.split("tag:")[1].strip(), eb.tags):
                    filtered.append(eb)
            elif exclude_term.startswith("progress:"):
                if not fuzzy_search_in_list(ReadStatus[exclude_term.split("progress:")[1].strip()], [eb.read], True):
                    filtered.append(eb)
            elif not is_ebook_a_match( exclude_term, eb.metadata.get_values("series") + eb.metadata.get_values("author") + eb.metadata.get_values("title")) and not fuzzy_search_in_list(exclude_term, eb.tags):
                filtered.append(eb)
        return sorted(filtered, key=lambda x: x.filename)

    def search(self, search_list, exclude_list, additive=False):
        complete_filtered_list = []

        if search_list == []:
            complete_filtered_list = self.all_ebooks
        else:
            for library_filter in search_list:
                # hits for this filter
                filtered = self.search_ebooks(library_filter)
                if additive:
                    # master list if f1 AND f2
                    if complete_filtered_list == []:
                        complete_filtered_list = filtered
                    else:
                        complete_filtered_list = [el for el in complete_filtered_list if el in filtered]
                else:
                    # master list if f1 OR f2
                    complete_filtered_list.extend([el for el in filtered if el not in complete_filtered_list])

        if exclude_list is not None:
            for exclude in exclude_list:
                complete_filtered_list = self.exclude_ebooks(complete_filtered_list, exclude)

        return sorted(complete_filtered_list, key=lambda x: x.filename)

    def list_tags(self):
        all_tags = defaultdict(lambda: 0)
        for ebook in self.all_ebooks:
            if ebook.tags == []:
                all_tags["untagged"] += 1
            else:
                for tag in ebook.tags:
                    all_tags[tag] += 1
        return all_tags
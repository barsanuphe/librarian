from .ebook import Ebook

class EbookSearch(object):

    def __init__(self, all_ebooks):
        self.all_ebooks = all_ebooks

    def search_ebooks(self, search_string, exact_search = False):
        filtered = []
        search_string = search_string.lower()
        for eb in self.all_ebooks:
            if search_string.startswith("series:"):
                if (not exact_search and search_string.split("series:")[1].strip() in eb.series.lower()) \
                    or (exact_search and search_string.split("series:")[1].strip() == eb.series.lower()):   #TODO: not ideal for exact search..
                    filtered.append(eb)
            elif search_string.startswith("author:"):
                if (not exact_search and search_string.split("author:")[1].strip() in eb.author.lower()) \
                    or (exact_search and search_string.split("author:")[1].strip() == eb.author.lower()):
                    filtered.append(eb)
            elif search_string.startswith("title:"):
                if (not exact_search and search_string.split("title:")[1].strip() in eb.title.lower()) \
                    or (exact_search and search_string.split("title:")[1].strip() == eb.title.lower()):
                    filtered.append(eb)
            elif search_string.startswith("tag:"):
                tag_to_search_for = search_string.split("tag:")[1].strip()
                for tag in eb.tags:
                    if (not exact_search and tag_to_search_for in tag) \
                        or (exact_search and tag_to_search_for == tag):
                        filtered.append(eb)
                        break # at least one match is good enough
            elif (not exact_search and (search_string.lower() in eb.series.lower() or search_string.lower() in eb.author.lower() or search_string.lower() in eb.title.lower() or search_string.lower() in eb.tags)) \
                or (exact_search and (search_string.lower() == eb.series.lower() or search_string.lower() == eb.author.lower() or search_string.lower() == eb.title.lower() or search_string.lower() in eb.tags)):
                filtered.append(eb)
        return sorted(filtered, key=lambda x: x.filename)

    def exclude_ebooks(self, ebooks_list, exclude_term):
        filtered = []
        exclude_term = exclude_term.lower()
        for eb in ebooks_list:
            if exclude_term.startswith("series:"):
                if exclude_term.split("series:")[1].strip() not in eb.series.lower():
                    filtered.append(eb)
            elif exclude_term.startswith("author:"):
                if exclude_term.split("author:")[1].strip() not in eb.author.lower():
                    filtered.append(eb)
            elif exclude_term.startswith("title:"):
                if exclude_term.split("title:")[1].strip() not in eb.title.lower():
                    filtered.append(eb)
            elif exclude_term.startswith("tag:"):
                tag_to_search_for = exclude_term.split("tag:")[1].strip()
                not_found = True
                for tag in eb.tags:
                    if tag_to_search_for in tag:
                        not_found = False
                        break
                if not_found:
                    filtered.append(eb)
            elif exclude_term.lower() not in eb.author.lower() and exclude_term.lower() not in eb.title.lower() and exclude_term.lower() not in eb.tags:
                filtered.append(eb)
        return sorted(filtered, key=lambda x: x.filename)

    def search(self, search_list, exclude_list, additive=False):
        complete_filtered_list_or = []
        complete_filtered_list_and = []
        out = []

        if search_list == []:
            out = self.all_ebooks
        else:
            for library_filter in search_list:
                filtered = self.search_ebooks(library_filter)
                complete_filtered_list_or.extend([el for el in filtered if el not in complete_filtered_list_or])
                if complete_filtered_list_and == []:
                    complete_filtered_list_and = filtered
                else:
                    complete_filtered_list_and = [el for el in complete_filtered_list_and if el in filtered]
            if additive:
                out =  complete_filtered_list_and
            else:
                out =  complete_filtered_list_or

        if exclude_list is not None:
            for exclude in exclude_list:
                out = self.exclude_ebooks(out, exclude)

        return sorted(out, key=lambda x: x.filename)

    def list_tags(self):
        all_tags = {}
        all_tags["untagged"] = 0
        for ebook in self.all_ebooks:
            if ebook.tags == []:
                all_tags["untagged"] += 1
            else:
                for tag in ebook.tags:
                    if tag in list(all_tags.keys()):
                        all_tags[tag] += 1
                    else:
                        all_tags[tag] = 1
        return all_tags
from collections import defaultdict
import re

from .epub import Epub, ReadStatus


def list_tags(ebooks):
    all_tags = defaultdict(lambda: 0)
    for ebook in ebooks:
        if ebook.tags == []:
            all_tags["untagged"] += 1
        else:
            for tag in ebook.tags:
                all_tags[tag] += 1
    return all_tags


class Search(object):
    """ This class builds a EvaluateMatch object from input conditions,
    then loops on all ebooks to pick out the ones who match. """
    def __init__(self, everything, is_exact=False):
        self.everything = everything
        self.is_exact = is_exact
        self.evaluate_match = EvaluateMatch()
        self.field_search = re.compile("^([^:]*):(.*)$")

    def excludes(self, exclude_list):
        for exclude_term in exclude_list:
            fields = self.field_search.findall(exclude_term)
            if fields == []:
                self.evaluate_match.add_exclude_condition(exclude_term, None,
                                                          self.is_exact)
            else:
                field, value = fields[0]
                self.evaluate_match.add_exclude_condition(value, field,
                                                          self.is_exact)

    def filters(self, filter_list):
        for filter_term in filter_list:
            fields = self.field_search.findall(filter_term)
            if fields == []:
                self.evaluate_match.add_condition(filter_term, None,
                                                  self.is_exact)
            else:
                field, value = fields[0]
                self.evaluate_match.add_condition(value, field, self.is_exact)

    # EvaluateMatch.OR / EvaluateMatch.AND
    def run_search(self, and_or):
        filtered = []
        for ebook in self.everything:
            if self.evaluate_match.is_a_match(ebook, and_or):
                filtered.append(ebook)
        return filtered

    @property
    def number_of_results(self):
        return len(self.filtered)


def match_this(ebook, value, field=None, exact=False):
    """ Try to see if an Epub object matches the condition given by value,
    optionnally restricted to a field. """
    value = value.lower()
    if field is None:
        # search everywhere
        result = False  # OR search
        for key in ebook.metadata.keys:
            field_value = [el for el in ebook.metadata.get_values(key)
                           if el is not None]
            is_list = (type(field_value) == list)
            if exact:
                result = result \
                    or (not is_list and value == field_value.lower()) \
                    or (is_list and value in field_value.lower())
            else:
                result = result or \
                         (not is_list and any([(value == val.lower())
                                               for val in field_value])) or\
                         (is_list and any([(value in val.lower())
                                           for val in field_value]))
        # tags
        if exact:
            result = result or any([(value == tag.lower())
                                    for tag in ebook.tags])
        else:
            result = result or any([(value in tag.lower())
                                    for tag in ebook.tags])

        return result

    else:
        if field == "tag":
            if exact:
                return any([(value == tag.lower()) for tag in ebook.tags])
            else:
                return any([(value in tag.lower()) for tag in ebook.tags])
        else:
            field_value = ebook.metadata.get_values(field)
            is_list = (type(field_value) == list)
            if exact:
                return (not is_list and value == field_value.lower()) or \
                    (is_list and any([(value == val.lower())
                                      for val in field_value]))
            else:
                return (not is_list and value in field_value.lower()) or \
                    (is_list and any([(value in val.lower())
                                      for val in field_value]))


class EvaluateMatch(object):
    """ This class builds a list of conditions, that are evaluated when
    is_a_match is passed with an actual Epub object. """
    OR = 1
    AND = 2

    def __init__(self):
        self.full_expression = []
        self.exclude_expression = []

    def add_condition(self, value, field=None, is_exact=False):
        self.full_expression.append(lambda x:
                                    match_this(x, value, field, is_exact))

    def add_exclude_condition(self, value, field=None, is_exact=False):
        self.exclude_expression.append(lambda x:
                                       not match_this(x, value, field,
                                                      is_exact))

    def _evaluate(self, epub):
        evaluated = [f(epub) for f in self.full_expression]
        exclude_evaluated = [f(epub) for f in self.exclude_expression]
        return evaluated, exclude_evaluated

    def apply_and_condition_to_epub(self, epub):
        evaluated, exclude_evaluated = self._evaluate(epub)
        return all(evaluated) and all(exclude_evaluated)

    def apply_or_condition_to_epub(self, epub):
        evaluated, exclude_evaluated = self._evaluate(epub)
        return any(evaluated) and all(exclude_evaluated)

    def is_a_match(self, epub, and_or):
        if and_or == self.AND:
            return self.apply_and_condition_to_epub(epub)
        elif and_or == self.OR:
            return self.apply_or_condition_to_epub(epub)
        else:
            print("What?")

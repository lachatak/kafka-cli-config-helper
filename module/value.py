from jsonpath_ng.ext import parse
from mergedeep import Strategy, merge
from nested_lookup import nested_delete
from unflatten import unflatten

KEY = 'value'


def resolve_inline_values(app_config):
    resolved = {}
    jsonpath_expr = parse(f'$..{KEY}.`parent`')
    [merge(resolved, unflatten({f'{match.full_path}': match.value[KEY]}), strategy=Strategy.ADDITIVE)
     for match in jsonpath_expr.find(app_config)]
    return merge(nested_delete(app_config, KEY), resolved, strategy=Strategy.ADDITIVE)



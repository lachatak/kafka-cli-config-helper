from jsonpath_ng.ext import parse
from mergedeep import Strategy, merge
from nested_lookup import nested_delete
from unflatten import unflatten


def resolve_inline_values(app_config):
    resolved = {}
    jsonpath_expr = parse('$..value.`parent`')
    [merge(resolved, unflatten({f'{match.full_path}': match.value['value']}), strategy=Strategy.ADDITIVE)
     for match in jsonpath_expr.find(app_config)]
    return merge(nested_delete(app_config, 'value'), resolved, strategy=Strategy.ADDITIVE)



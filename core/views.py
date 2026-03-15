import json
import re
from itertools import combinations, zip_longest

from django.http import HttpResponseNotAllowed
from django.shortcuts import render
from epiinfo.LinearRegression import LinearRegression
from epiinfo.LogBinomialRegression import LogBinomialRegression
from epiinfo.LogisticRegression import LogisticRegression
from epiinfo.Frequencies import Frequencies as FreqClass
from epiinfo.Means import Means
from epiinfo.TablesAnalysis import TablesAnalysis


# ---------------------------------------------------------------------------
# Filter helpers
# ---------------------------------------------------------------------------

OPERATOR_LABELS = {
    'is_missing':     'is missing',
    'is_not_missing': 'is not missing',
    'eq':             'is equal to',
    'neq':            'is not equal to',
    'lt':             'less than',
    'lte':            'less than or equal to',
    'gte':            'greater than or equal to',
    'gt':             'greater than',
}


def _is_numeric_variable(data, variable):
    """Return True if all non-empty values of variable can be parsed as float."""
    for row in data:
        val = row.get(variable)
        if val is None or val == '':
            continue
        try:
            float(val)
        except (ValueError, TypeError):
            return False
    return True


def _unique_values(data, variable):
    """Return sorted list of distinct non-empty string values for variable."""
    return sorted(set(
        str(row[variable])
        for row in data
        if variable in row and row[variable] is not None and row[variable] != ''
    ))


def _row_matches_condition(row, variable, operator, value):
    """Return True if the row satisfies a single filter condition."""
    raw = row.get(variable)
    is_missing = raw is None or raw == ''
    if operator == 'is_missing':
        return is_missing
    if operator == 'is_not_missing':
        return not is_missing
    if operator == 'eq':
        return not is_missing and str(raw) == value
    if operator == 'neq':
        return not is_missing and str(raw) != value
    if operator in ('lt', 'lte', 'gte', 'gt'):
        try:
            row_val = float(raw)
            cmp_val = float(value)
            return (
                (operator == 'lt'  and row_val <  cmp_val) or
                (operator == 'lte' and row_val <= cmp_val) or
                (operator == 'gte' and row_val >= cmp_val) or
                (operator == 'gt'  and row_val >  cmp_val)
            )
        except (ValueError, TypeError):
            return False
    return False


def _apply_filter_definition(data, conditions):
    """Keep rows that satisfy ANY condition in conditions (OR logic)."""
    return [
        row for row in data
        if any(_row_matches_condition(row, c['variable'], c['operator'], c['value'])
               for c in conditions)
    ]


def _compute_frequency_table(data, variable, weight_variable=''):
    """Return frequency rows and metadata for one variable/stratum."""
    sorted_data = sorted(data, key=lambda d: d.get(variable, ''))
    vals_and_freqs = {}
    total = 0.0
    for row in sorted_data:
        if variable not in row:
            continue
        val = str(row[variable])
        weight = float(row[weight_variable]) if weight_variable and weight_variable in row else 1.0
        total += weight
        vals_and_freqs[val] = vals_and_freqs.get(val, 0.0) + weight

    freq_obj = FreqClass()
    rows = []
    cum_pct = 0.0
    for val, freq in vals_and_freqs.items():
        pct = (freq / total * 100) if total > 0 else 0.0
        cum_pct += pct
        cl = freq_obj.GetConfLimit(val, freq, total)
        rows.append({
            'value': val,
            'frequency': freq,
            'percent': pct,
            'cum_percent': cum_pct,
            'lcl': cl[1] * 100,
            'ucl': cl[2] * 100,
        })

    ci_method = 'Exact' if total < 300 else 'Wilson'
    return {'rows': rows, 'total': total, 'ci_method': ci_method}


def index(request):
    return render(request, 'core/index.html')


def upload_json(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    uploaded_file = request.FILES.get('json_file')
    if not uploaded_file:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'No file was submitted.'},
            status=400,
        )

    raw = uploaded_file.read()
    if not raw:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'The uploaded file is empty.'},
            status=400,
        )

    try:
        text = raw.decode('utf-8')
        # Repair lone backslashes that aren't valid JSON escape sequences.
        # Valid JSON escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
        data = json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': f'Invalid JSON: {exc}'},
            status=400,
        )

    if not isinstance(data, list):
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'JSON must be a list (array) of objects.'},
            status=400,
        )

    if not all(isinstance(item, dict) for item in data):
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'Every item in the JSON array must be an object (not a nested array or value).'},
            status=400,
        )

    request.session['data'] = data
    request.session['original_data'] = data
    request.session['filters'] = []
    request.session['data_filename'] = uploaded_file.name

    columns = list(data[0].keys()) if data else []
    return render(
        request,
        'core/partials/data_summary.html',
        {
            'filename': uploaded_file.name,
            'row_count': len(data),
            'columns': columns,
        },
    )


def tables_form(request):
    data = request.session.get('data')
    if not data:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'No data loaded. Please upload a JSON file first.'},
            status=400,
        )

    columns = sorted(data[0].keys(), key=str.casefold) if data else []
    return render(
        request,
        'core/partials/tables_form.html',
        {'columns': columns},
    )


def run_analysis(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    data = request.session.get('data')
    if not data:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'No data loaded. Please upload a JSON file first.'},
            status=400,
        )

    outcome = request.POST.get('outcome_variable', '').strip()
    exposures = request.POST.getlist('exposure_variables')

    if not outcome:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'Please select an Outcome Variable.'},
            status=400,
        )
    if not exposures:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'Please select at least one Exposure Variable.'},
            status=400,
        )

    input_variable_list = {
        'outcomeVariable': outcome,
        'exposureVariables': exposures,
    }

    ta = TablesAnalysis()
    result = ta.Run(input_variable_list, data)

    # Build a structured context so the template stays logic-free
    tables = []
    for i, variable in enumerate(result['Variables']):
        row_labels = result['VariableValues'][i][0]
        col_labels = result['VariableValues'][i][1]
        raw_table = result['Tables'][i]
        row_totals = result['RowTotals'][i]
        col_totals = result['ColumnTotals'][i]
        stats = result['Statistics'][i]

        # raw_table is indexed [exposure_idx][outcome_idx].
        # RowTotals = totals per exposure (visual row totals).
        # ColumnTotals = totals per outcome (visual column totals).
        # Layout: exposure values down the left, outcome values across the top.
        rows = [
            {
                'label': col_labels[j],  # exposure value
                'cells': raw_table[j],   # counts indexed by outcome
                'total': row_totals[j],  # total for this exposure row
            }
            for j in range(len(col_labels))
        ]

        grand_total = sum(row_totals)
        is_two_by_two = len(row_labels) == 2 and len(col_labels) == 2

        tables.append({
            'variable': variable,
            'col_labels': row_labels,   # outcome values become column headers
            'rows': rows,
            'col_totals': col_totals,   # ColumnTotals = per-outcome column totals
            'grand_total': grand_total,
            'stats': stats,
            'is_two_by_two': is_two_by_two,
        })

    summary = sorted(
        [
            {
                'variable': t['variable'],
                'OR': t['stats'].get('OR'),
                'ORLL': t['stats'].get('ORLL'),
                'ORUL': t['stats'].get('ORUL'),
                'RiskRatio': t['stats'].get('RiskRatio'),
                'RiskRatioLL': t['stats'].get('RiskRatioLL'),
                'RiskRatioUL': t['stats'].get('RiskRatioUL'),
            }
            for t in tables
            if t['is_two_by_two']
        ],
        key=lambda x: x['variable'].casefold(),
    )

    return render(
        request,
        'core/partials/tables_results.html',
        {
            'outcome': outcome,
            'exposures': exposures,
            'tables': tables,
            'summary': summary,
        },
    )


def linear_form(request):
    data = request.session.get('data')
    if not data:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'No data loaded. Please upload a JSON file first.'},
            status=400,
        )

    columns = sorted(data[0].keys(), key=str.casefold) if data else []
    return render(request, 'core/partials/linear_form.html', {'columns': columns})


def run_linear(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    data = request.session.get('data')
    if not data:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'No data loaded. Please upload a JSON file first.'},
            status=400,
        )

    outcome = request.POST.get('outcome_variable', '').strip()
    exposures = request.POST.getlist('exposure_variables')
    interaction_variables = request.POST.getlist('interaction_variables')

    if not outcome:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'Please select an Outcome Variable.'},
            status=400,
        )
    if not exposures:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'Please select at least one Exposure Variable.'},
            status=400,
        )

    interaction_terms = [
        f'{a}*{b}' for a, b in combinations(interaction_variables, 2)
    ] if len(interaction_variables) >= 2 else []

    if interaction_terms:
        data_for_regression = []
        for record in data:
            row = dict(record)
            for term in interaction_terms:
                a, b = term.split('*')
                try:
                    row[term] = float(record[a]) * float(record[b])
                except (ValueError, TypeError, KeyError):
                    row[term] = None
            data_for_regression.append(row)
    else:
        data_for_regression = data

    lr = LinearRegression()
    results = lr.doRegression(
        {'dependvar': outcome, 'exposureVariables': exposures + interaction_terms},
        data_for_regression,
    )

    terms = []
    stats = {}
    for res in results:
        if isinstance(res, dict) and 'variable' in res:
            terms.append({
                'name': res['variable'],
                'is_constant': res['variable'] == 'CONSTANT',
                'beta': res['beta'],
                'lcl': res['lcl'],
                'ucl': res['ucl'],
                'se': res['stderror'],
                'f': res['ftest'],
                'p': res['pvalue'],
            })
        elif isinstance(res, dict) and 'r2' in res:
            stats = res

    return render(
        request,
        'core/partials/linear_results.html',
        {
            'outcome': outcome,
            'exposures': exposures,
            'interaction_variables': interaction_variables,
            'terms': terms,
            'r2': stats.get('r2'),
            'regression_df': stats.get('regressionDF'),
            'regression_ss': stats.get('sumOfSquares'),
            'regression_ms': stats.get('meanSquare'),
            'regression_f': stats.get('fStatistic'),
            'residuals_df': stats.get('residualsDF'),
            'residuals_ss': stats.get('residualsSS'),
            'residuals_ms': stats.get('residualsMS'),
            'total_df': stats.get('totalDF'),
            'total_ss': stats.get('totalSS'),
        },
    )


def logistic_form(request):
    data = request.session.get('data')
    if not data:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'No data loaded. Please upload a JSON file first.'},
            status=400,
        )

    columns = sorted(data[0].keys(), key=str.casefold) if data else []
    return render(request, 'core/partials/logistic_form.html', {'columns': columns})


def run_logistic(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    data = request.session.get('data')
    if not data:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'No data loaded. Please upload a JSON file first.'},
            status=400,
        )

    outcome = request.POST.get('outcome_variable', '').strip()
    exposures = request.POST.getlist('exposure_variables')
    match_variable = request.POST.get('match_variable', '').strip()
    interaction_variables = request.POST.getlist('interaction_variables')

    if not outcome:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'Please select an Outcome Variable.'},
            status=400,
        )
    if not exposures:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'Please select at least one Exposure Variable.'},
            status=400,
        )

    # Build pairwise interaction terms
    interaction_terms = [
        f'{a}*{b}' for a, b in combinations(interaction_variables, 2)
    ] if len(interaction_variables) >= 2 else []

    input_variable_list = {
        outcome: 'dependvar',
        'exposureVariables': exposures + interaction_terms,
    }
    if match_variable:
        input_variable_list[match_variable] = 'matchvar'

    lr = LogisticRegression()
    results = lr.doRegression(input_variable_list, data)

    # Build structured terms list for the template
    variables = results.Variables
    n_non_const = len(results.OR)  # OR list excludes CONSTANT
    terms = []
    for i, var in enumerate(variables):
        is_constant = (var == 'CONSTANT')
        terms.append({
            'name': var,
            'is_constant': is_constant,
            'beta': results.Beta[i],
            'se': results.SE[i],
            'z': results.Z[i],
            'p': results.PZ[i],
            'or': results.OR[i] if i < n_non_const else None,
            'or_lcl': results.ORLCL[i] if i < n_non_const else None,
            'or_ucl': results.ORUCL[i] if i < n_non_const else None,
        })

    # Group interaction ORs by term name for the template
    interaction_groups = {}
    for ior in results.InteractionOR:
        key = ior[0]
        if key not in interaction_groups:
            interaction_groups[key] = []
        interaction_groups[key].append({
            'label': ior[1],
            'or': ior[2],
            'lcl': ior[3],
            'ucl': ior[4],
        })

    return render(
        request,
        'core/partials/logistic_results.html',
        {
            'outcome': outcome,
            'exposures': exposures,
            'match_variable': match_variable,
            'interaction_variables': interaction_variables,
            'is_conditional': bool(match_variable),
            'terms': terms,
            'iterations': results.Iterations,
            'minus_two_ll': results.MinusTwoLogLikelihood,
            'cases_included': results.CasesIncluded,
            'score': results.Score,
            'score_df': results.ScoreDF,
            'score_p': results.ScoreP,
            'lr': results.LikelihoodRatio,
            'lr_df': results.LikelihoodRatioDF,
            'lr_p': results.LikelihoodRatioP,
            'interaction_groups': interaction_groups,
        },
    )


def logbinomial_form(request):
    data = request.session.get('data')
    if not data:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'No data loaded. Please upload a JSON file first.'},
            status=400,
        )

    columns = sorted(data[0].keys(), key=str.casefold) if data else []
    return render(request, 'core/partials/logbinomial_form.html', {'columns': columns})


def run_logbinomial(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    data = request.session.get('data')
    if not data:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'No data loaded. Please upload a JSON file first.'},
            status=400,
        )

    outcome = request.POST.get('outcome_variable', '').strip()
    exposures = request.POST.getlist('exposure_variables')
    interaction_variables = request.POST.getlist('interaction_variables')

    if not outcome:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'Please select an Outcome Variable.'},
            status=400,
        )
    if not exposures:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'Please select at least one Exposure Variable.'},
            status=400,
        )

    interaction_terms = [
        f'{a}*{b}' for a, b in combinations(interaction_variables, 2)
    ] if len(interaction_variables) >= 2 else []

    input_variable_list = {
        outcome: 'dependvar',
        'exposureVariables': exposures + interaction_terms,
    }

    lb = LogBinomialRegression()
    results = lb.doRegression(input_variable_list, data)

    n_non_const = len(results.RR)
    terms = []
    for i, var in enumerate(results.Variables):
        is_constant = (var == 'CONSTANT')
        terms.append({
            'name': var,
            'is_constant': is_constant,
            'beta': results.Beta[i],
            'se': results.SE[i],
            'z': results.Z[i],
            'p': results.PZ[i],
            'rr': results.RR[i] if i < n_non_const else None,
            'rr_lcl': results.RRLCL[i] if i < n_non_const else None,
            'rr_ucl': results.RRUCL[i] if i < n_non_const else None,
        })

    interaction_groups = {}
    for irr in results.InteractionRR:
        key = irr[0]
        if key not in interaction_groups:
            interaction_groups[key] = []
        interaction_groups[key].append({
            'label': irr[1],
            'rr': irr[2],
            'lcl': irr[3],
            'ucl': irr[4],
        })

    return render(
        request,
        'core/partials/logbinomial_results.html',
        {
            'outcome': outcome,
            'exposures': exposures,
            'interaction_variables': interaction_variables,
            'terms': terms,
            'iterations': results.Iterations,
            'log_likelihood': results.LogLikelihood,
            'cases_included': results.CasesIncluded,
            'interaction_groups': interaction_groups,
        },
    )


def means_form(request):
    data = request.session.get('data')
    if not data:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'No data loaded. Please upload a JSON file first.'},
            status=400,
        )

    columns = sorted(data[0].keys(), key=str.casefold) if data else []
    return render(request, 'core/partials/means_form.html', {'columns': columns})


def run_means(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    data = request.session.get('data')
    if not data:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'No data loaded. Please upload a JSON file first.'},
            status=400,
        )

    means_variable = request.POST.get('means_variable', '').strip()
    crosstab_variable = request.POST.get('crosstab_variable', '').strip()

    if not means_variable:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'Please select a Means Of variable.'},
            status=400,
        )

    cols = {'meanVariable': means_variable}
    if crosstab_variable:
        cols['crosstabVariable'] = crosstab_variable

    m = Means()
    result = m.Run(cols, data)

    if crosstab_variable:
        anova = result[-1]
        ttest = result[-2]
        group_stats = result[:-2]
        show_ttest = len(group_stats) == 2
    else:
        group_stats = result
        ttest = None
        anova = None
        show_ttest = False

    return render(
        request,
        'core/partials/means_results.html',
        {
            'means_variable': means_variable,
            'crosstab_variable': crosstab_variable,
            'group_stats': group_stats,
            'ttest': ttest,
            'anova': anova,
            'show_ttest': show_ttest,
        },
    )


def frequencies_form(request):
    data = request.session.get('data')
    if not data:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'No data loaded. Please upload a JSON file first.'},
            status=400,
        )
    columns = sorted(data[0].keys(), key=str.casefold) if data else []
    return render(request, 'core/partials/frequencies_form.html', {'columns': columns})


def run_frequencies(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    data = request.session.get('data')
    if not data:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'No data loaded. Please upload a JSON file first.'},
            status=400,
        )

    freq_variables = request.POST.getlist('freq_variables')
    stratify_variable = request.POST.get('stratify_variable', '').strip()
    weight_variable = request.POST.get('weight_variable', '').strip()

    if not freq_variables:
        return render(
            request,
            'core/partials/upload_error.html',
            {'error': 'Please select at least one Frequency Of variable.'},
            status=400,
        )

    if stratify_variable:
        strata_values = sorted(set(str(row.get(stratify_variable, '')) for row in data))
        strata = [(sv, [r for r in data if str(r.get(stratify_variable, '')) == sv]) for sv in strata_values]
    else:
        strata = [('', data)]

    tables = []
    for stratum_label, stratum_data in strata:
        for var in freq_variables:
            result = _compute_frequency_table(stratum_data, var, weight_variable)
            tables.append({
                'variable': var,
                'stratum': stratum_label,
                'stratify_variable': stratify_variable,
                'weight_variable': weight_variable,
                'rows': result['rows'],
                'total': result['total'],
                'ci_method': result['ci_method'],
            })

    return render(
        request,
        'core/partials/frequencies_results.html',
        {
            'tables': tables,
            'freq_variables': freq_variables,
            'stratify_variable': stratify_variable,
            'weight_variable': weight_variable,
        },
    )


def filter_form(request):
    data = request.session.get('data')
    if not data:
        return render(request, 'core/partials/upload_error.html',
                      {'error': 'No data loaded. Please upload a JSON file first.'}, status=400)
    columns = sorted(data[0].keys(), key=str.casefold)
    filters = request.session.get('filters', [])
    return render(request, 'core/partials/filter_form.html', {
        'columns': columns,
        'filters': filters,
        'row_count': len(data),
    })


def filter_options(request):
    variable = request.GET.get('variable', '')
    index = request.GET.get('index', '0')
    data = request.session.get('data', [])
    if not variable or not data:
        return render(request, 'core/partials/filter_options.html', {'index': index})
    is_numeric = _is_numeric_variable(data, variable)
    return render(request, 'core/partials/filter_options.html', {
        'variable': variable,
        'is_numeric': is_numeric,
        'index': index,
    })


def filter_value_input(request):
    variable = request.GET.get('variable', '')
    operator = request.GET.get('operator', '')
    data = request.session.get('data', [])
    if operator in ('is_missing', 'is_not_missing') or not variable:
        return render(request, 'core/partials/filter_value_input.html', {'show_input': False})
    unique_vals = _unique_values(data, variable)
    use_select = operator in ('eq', 'neq') and len(unique_vals) <= 5
    return render(request, 'core/partials/filter_value_input.html', {
        'show_input': True,
        'use_select': use_select,
        'unique_vals': unique_vals if use_select else [],
    })


def run_filter(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    data = request.session.get('data')
    if not data:
        return render(request, 'core/partials/upload_error.html',
                      {'error': 'No data loaded. Please upload a JSON file first.'}, status=400)
    variables = request.POST.getlist('variable')
    operators = request.POST.getlist('operator')
    values = request.POST.getlist('value')
    conditions = []
    for variable, operator, value in zip_longest(variables, operators, values, fillvalue=''):
        variable, operator, value = variable.strip(), operator.strip(), value.strip()
        if variable and operator:
            conditions.append({
                'variable': variable,
                'operator': operator,
                'operator_label': OPERATOR_LABELS.get(operator, operator),
                'value': value,
            })
    if not conditions:
        return render(request, 'core/partials/upload_error.html',
                      {'error': 'Please select a variable and operator.'}, status=400)
    filtered = _apply_filter_definition(data, conditions)
    filters = request.session.get('filters', [])
    filters.append(conditions)
    request.session['data'] = filtered
    request.session['filters'] = filters
    request.session.modified = True
    return render(request, 'core/partials/filter_status.html', {
        'filters': filters,
        'row_count': len(filtered),
    })


def clear_filters(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    original = request.session.get('original_data')
    if original is None:
        return render(request, 'core/partials/upload_error.html',
                      {'error': 'No data loaded. Please upload a JSON file first.'}, status=400)
    request.session['data'] = original
    request.session['filters'] = []
    request.session.modified = True
    return render(request, 'core/partials/filter_status.html', {
        'filters': [],
        'row_count': len(original),
    })


def filter_condition_row(request):
    data = request.session.get('data', [])
    index = request.GET.get('index', '1')
    columns = sorted(data[0].keys(), key=str.casefold) if data else []
    return render(request, 'core/partials/filter_condition_row.html', {
        'columns': columns,
        'index': index,
    })

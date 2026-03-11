import json
from itertools import combinations

from django.http import HttpResponseNotAllowed
from django.shortcuts import render
from epiinfo.LogisticRegression import LogisticRegression
from epiinfo.TablesAnalysis import TablesAnalysis


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
        data = json.loads(raw.decode('utf-8'))
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

        rows = [
            {'label': row_labels[j], 'cells': raw_table[j], 'total': row_totals[j]}
            for j in range(len(row_labels))
        ]

        grand_total = sum(row_totals)
        is_two_by_two = len(row_labels) == 2 and len(col_labels) == 2

        tables.append({
            'variable': variable,
            'col_labels': col_labels,
            'rows': rows,
            'col_totals': col_totals,
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

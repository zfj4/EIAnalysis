import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

# ---------------------------------------------------------------------------
# Sample dataset shared across analysis tests
# ---------------------------------------------------------------------------
SAMPLE_DATA = [
    {'outcome': 'Yes', 'exposure': 'High', 'age': '30'},
    {'outcome': 'Yes', 'exposure': 'Low',  'age': '25'},
    {'outcome': 'No',  'exposure': 'High', 'age': '45'},
    {'outcome': 'No',  'exposure': 'Low',  'age': '50'},
    {'outcome': 'Yes', 'exposure': 'High', 'age': '28'},
    {'outcome': 'No',  'exposure': 'Low',  'age': '33'},
]

# Realistic mock result from TablesAnalysis.Run()
MOCK_TABLES_RESULT = {
    'Variables': ['outcome * exposure'],
    'VariableValues': [[['Yes', 'No'], ['High', 'Low']]],
    'Tables': [[[2, 1], [1, 2]]],
    'RowTotals': [[3, 3]],
    'ColumnTotals': [[3, 3]],
    'Statistics': [{
        'OR': 4.0,
        'ORLL': 0.134,
        'ORUL': 119.2,
        'MidPOR': 3.8,
        'MidPORLL': 0.120,
        'MidPORUL': 115.0,
        'FisherORLL': 0.110,
        'FisherORUL': 120.5,
        'RiskRatio': 2.0,
        'RiskRatioLL': 0.33,
        'RiskRatioUL': 11.97,
        'RiskDifference': 33.33,
        'RiskDifferenceLL': -42.1,
        'RiskDifferenceUL': 108.77,
        'UncorrectedX2': 0.667,
        'UncorrectedX2P': 0.414,
        'CorrectedX2': 0.0,
        'CorrectedX2P': 1.0,
        'MHX2': 0.556,
        'MHX2P': 0.456,
        'FisherExact2Tail': 1.0,
        'FisherExact1Tail': 0.5,
    }],
}


# ===========================================================================
# IndexViewTests
# ===========================================================================

class IndexViewTests(TestCase):
    """TDD tests for the core index (SPA shell) view."""

    def test_index_returns_200(self):
        """GET / must return HTTP 200."""
        response = self.client.get(reverse('core:index'))
        self.assertEqual(response.status_code, 200)

    def test_index_uses_correct_template(self):
        """GET / must render index.html."""
        response = self.client.get(reverse('core:index'))
        self.assertTemplateUsed(response, 'core/index.html')

    def test_index_contains_htmx_script(self):
        """index.html must include the HTMX CDN script tag."""
        response = self.client.get(reverse('core:index'))
        self.assertContains(response, 'htmx.org')

    def test_index_contains_tailwind_script(self):
        """index.html must include the Tailwind CDN script tag."""
        response = self.client.get(reverse('core:index'))
        self.assertContains(response, 'tailwindcss')

    def test_index_contains_main_content_div(self):
        """index.html must have a #main-content div for HTMX swaps."""
        response = self.client.get(reverse('core:index'))
        self.assertContains(response, 'id="main-content"')

    def test_index_contains_file_navigator(self):
        """The initial page must contain a JSON file input for the file navigator."""
        response = self.client.get(reverse('core:index'))
        self.assertContains(response, 'type="file"')
        self.assertContains(response, '.json')


# ===========================================================================
# UploadJsonViewTests
# ===========================================================================

class UploadJsonViewTests(TestCase):
    """TDD tests for the JSON file upload view."""

    URL = 'core:upload_json'

    def _upload(self, payload, filename='data.json', content_type='application/json'):
        content = json.dumps(payload).encode()
        f = SimpleUploadedFile(filename, content, content_type=content_type)
        return self.client.post(
            reverse(self.URL),
            {'json_file': f},
            format='multipart',
        )

    def test_get_returns_405(self):
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 405)

    def test_valid_upload_returns_200(self):
        response = self._upload([{'a': 1}, {'a': 2}])
        self.assertEqual(response.status_code, 200)

    def test_valid_upload_uses_summary_template(self):
        response = self._upload([{'a': 1}])
        self.assertTemplateUsed(response, 'core/partials/data_summary.html')

    def test_valid_upload_stores_data_in_session(self):
        data = [{'name': 'Alice', 'age': 30}, {'name': 'Bob', 'age': 25}]
        self._upload(data)
        self.assertEqual(self.client.session['data'], data)

    def test_valid_upload_stores_filename_in_session(self):
        self._upload([{'x': 1}], filename='results.json')
        self.assertEqual(self.client.session['data_filename'], 'results.json')

    def test_summary_shows_row_count(self):
        response = self._upload([{'a': 1}, {'a': 2}, {'a': 3}])
        self.assertContains(response, '3')

    def test_summary_shows_filename(self):
        response = self._upload([{'a': 1}], filename='mydata.json')
        self.assertContains(response, 'mydata.json')

    def test_invalid_json_returns_400(self):
        f = SimpleUploadedFile('bad.json', b'{not valid json', 'application/json')
        response = self.client.post(reverse(self.URL), {'json_file': f})
        self.assertEqual(response.status_code, 400)

    def test_non_list_json_returns_400(self):
        response = self._upload({'key': 'value'})
        self.assertEqual(response.status_code, 400)

    def test_empty_file_returns_400(self):
        f = SimpleUploadedFile('empty.json', b'', 'application/json')
        response = self.client.post(reverse(self.URL), {'json_file': f})
        self.assertEqual(response.status_code, 400)

    def test_missing_file_returns_400(self):
        response = self.client.post(reverse(self.URL), {})
        self.assertEqual(response.status_code, 400)

    def test_error_response_uses_error_template(self):
        f = SimpleUploadedFile('bad.json', b'not json', 'application/json')
        response = self.client.post(reverse(self.URL), {'json_file': f})
        self.assertTemplateUsed(response, 'core/partials/upload_error.html')

    def test_list_of_non_dicts_returns_400(self):
        """A JSON array of non-objects (e.g. scalars) must be rejected."""
        response = self._upload([1, 2, 3])
        self.assertEqual(response.status_code, 400)

    def test_nested_list_returns_400(self):
        """A JSON array of arrays (nested) must be rejected."""
        response = self._upload([[1, 2], [3, 4]])
        self.assertEqual(response.status_code, 400)


# ===========================================================================
# TablesFormViewTests
# ===========================================================================

class TablesFormViewTests(TestCase):
    """TDD tests for the tables analysis variable-selection form view."""

    URL = 'core:tables_form'

    def _set_session_data(self):
        session = self.client.session
        session['data'] = SAMPLE_DATA
        session['data_filename'] = 'sample.json'
        session.save()

    def test_requires_session_data(self):
        """GET without loaded data must return 400."""
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 400)

    def test_returns_200_with_session_data(self):
        """GET with data in session must return 200."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        """Must render the tables_form partial template."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertTemplateUsed(response, 'core/partials/tables_form.html')

    def test_all_columns_in_outcome_dropdown(self):
        """Every column name from the data must appear in the outcome select."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        for col in ['outcome', 'exposure', 'age']:
            self.assertContains(response, col)

    def test_all_columns_as_exposure_checkboxes(self):
        """Every column name must appear as an exposure checkbox option."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, 'type="checkbox"')

    def test_columns_sorted_alphabetically_case_insensitive(self):
        """Columns must appear in case-insensitive alphabetical order."""
        session = self.client.session
        session['data'] = [{'Zebra': 1, 'apple': 1, 'Mango': 1, 'banana': 1}]
        session.save()
        response = self.client.get(reverse(self.URL))
        content = response.content.decode()
        positions = [content.index(col) for col in ['apple', 'banana', 'Mango', 'Zebra']]
        self.assertEqual(positions, sorted(positions))

    def test_form_posts_to_run_analysis_url(self):
        """The form action must point to the run_analysis endpoint."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, reverse('core:run_analysis'))


# ===========================================================================
# RunAnalysisViewTests
# ===========================================================================

class RunAnalysisViewTests(TestCase):
    """TDD tests for the run_analysis view (calls epiinfo.TablesAnalysis)."""

    URL = 'core:run_analysis'

    def _set_session_data(self):
        session = self.client.session
        session['data'] = SAMPLE_DATA
        session.save()

    def _run(self, outcome='outcome', exposures=None):
        if exposures is None:
            exposures = ['exposure']
        return self.client.post(
            reverse(self.URL),
            {'outcome_variable': outcome, 'exposure_variables': exposures},
        )

    # --- method guard ---

    def test_get_returns_405(self):
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 405)

    # --- session guard ---

    def test_requires_session_data(self):
        """POST without loaded data must return 400."""
        response = self._run()
        self.assertEqual(response.status_code, 400)

    # --- input validation ---

    def test_missing_outcome_returns_400(self):
        self._set_session_data()
        response = self.client.post(
            reverse(self.URL),
            {'exposure_variables': ['exposure']},
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_exposures_returns_400(self):
        self._set_session_data()
        response = self.client.post(
            reverse(self.URL),
            {'outcome_variable': 'outcome'},
        )
        self.assertEqual(response.status_code, 400)

    # --- happy path (mocked TablesAnalysis) ---

    @patch('core.views.TablesAnalysis')
    def test_valid_run_returns_200(self, MockTA):
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        response = self._run()
        self.assertEqual(response.status_code, 200)

    @patch('core.views.TablesAnalysis')
    def test_valid_run_uses_results_template(self, MockTA):
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        response = self._run()
        self.assertTemplateUsed(response, 'core/partials/tables_results.html')

    @patch('core.views.TablesAnalysis')
    def test_calls_tables_analysis_with_correct_args(self, MockTA):
        """Run() must be called with the correct inputVariableList and session data."""
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        self._run(outcome='outcome', exposures=['exposure'])

        expected_iv = {
            'outcomeVariable': 'outcome',
            'exposureVariables': ['exposure'],
        }
        MockTA.return_value.Run.assert_called_once_with(expected_iv, SAMPLE_DATA)

    @patch('core.views.TablesAnalysis')
    def test_results_contain_table_element(self, MockTA):
        """Response HTML must contain a <table> element."""
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, '<table')

    @patch('core.views.TablesAnalysis')
    def test_results_contain_variable_name(self, MockTA):
        """Response must display the 'outcome * exposure' variable label."""
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, 'outcome * exposure')

    @patch('core.views.TablesAnalysis')
    def test_results_contain_odds_ratio(self, MockTA):
        """Results page must display the Odds Ratio value."""
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, '4.0')

    @patch('core.views.TablesAnalysis')
    def test_results_contain_exact_or_estimates(self, MockTA):
        """Results page must display MidPOR (MLE) and Fisher OR confidence limits."""
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        response = self._run()
        # Odds Ratio (MLE) point estimate
        self.assertContains(response, '3.8')
        # Fisher exact CI limits
        self.assertContains(response, '0.1100')
        self.assertContains(response, '120.5')


# ===========================================================================
# SummaryTableTests
# ===========================================================================

class SummaryTableTests(TestCase):
    """TDD tests for the summary table at the top of Tables Analysis results."""

    URL = 'core:run_analysis'

    def _set_session_data(self):
        session = self.client.session
        session['data'] = SAMPLE_DATA
        session.save()

    def _run(self, **kwargs):
        return self.client.post(
            reverse(self.URL),
            {'outcome_variable': 'outcome', 'exposure_variables': ['exposure'], **kwargs},
        )

    @patch('core.views.TablesAnalysis')
    def test_summary_section_is_present(self, MockTA):
        """Results must include a summary table section."""
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, 'Summary')

    @patch('core.views.TablesAnalysis')
    def test_summary_has_odds_ratio_column(self, MockTA):
        """Summary table must have an Odds Ratio column header."""
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, 'Odds Ratio')

    @patch('core.views.TablesAnalysis')
    def test_summary_has_orll_and_orul_columns(self, MockTA):
        """Summary table must have OR lower and upper limit column headers."""
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, 'ORLL')
        self.assertContains(response, 'ORUL')

    @patch('core.views.TablesAnalysis')
    def test_summary_has_risk_ratio_column(self, MockTA):
        """Summary table must have a Risk Ratio column header."""
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, 'Risk Ratio')

    @patch('core.views.TablesAnalysis')
    def test_summary_has_rr_ll_and_ul_columns(self, MockTA):
        """Summary table must have RR lower and upper limit column headers."""
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, 'RR LL')
        self.assertContains(response, 'RR UL')

    @patch('core.views.TablesAnalysis')
    def test_summary_shows_variable_name(self, MockTA):
        """Summary table must contain a row for each analyzed variable."""
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, 'outcome * exposure')

    @patch('core.views.TablesAnalysis')
    def test_summary_shows_or_value(self, MockTA):
        """Summary table must display the Odds Ratio point estimate."""
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, '4.0000')

    @patch('core.views.TablesAnalysis')
    def test_summary_shows_rr_value(self, MockTA):
        """Summary table must display the Risk Ratio point estimate."""
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, '2.0000')

    @patch('core.views.TablesAnalysis')
    def test_summary_headers_are_sortable(self, MockTA):
        """Column headers must carry the sort-header class for JS sorting."""
        MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, 'sort-header')


# ===========================================================================
# SalmonellosisIntegrationTests
# ===========================================================================

SAMPLE_DATA_PATH = Path(__file__).resolve().parent.parent / 'sample_data' / 'Salmonellosis.json'


class SalmonellosisIntegrationTests(TestCase):
    """
    Integration test: loads Salmonellosis.json, runs TablesAnalysis against
    the live epiinfo library, and asserts known Risk Ratio values.

    Reference values confirmed by running TablesAnalysis directly:
      Ill * ChefSalad        RiskRatio = 1.2186452726718797
      Ill * EggSaladSandwich RiskRatio = 1.1830147058823528
    """

    OUTCOME = 'Ill'
    EXPOSURES = ['ChefSalad', 'EggSaladSandwich']

    # Precision: 4 decimal places matches the stated expected values
    PLACES = 4

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(SAMPLE_DATA_PATH) as f:
            cls.data = json.load(f)

    def _set_session(self):
        session = self.client.session
        session['data'] = self.data
        session.save()

    def _run(self):
        self._set_session()
        return self.client.post(
            reverse('core:run_analysis'),
            {
                'outcome_variable': self.OUTCOME,
                'exposure_variables': self.EXPOSURES,
            },
        )

    def test_salmonellosis_data_loads(self):
        """Salmonellosis.json must be a non-empty list of dicts."""
        self.assertIsInstance(self.data, list)
        self.assertGreater(len(self.data), 0)
        self.assertIn('Ill', self.data[0])
        self.assertIn('ChefSalad', self.data[0])
        self.assertIn('EggSaladSandwich', self.data[0])

    def test_run_analysis_returns_200(self):
        """run_analysis view must return HTTP 200 for Salmonellosis inputs."""
        response = self._run()
        self.assertEqual(response.status_code, 200)

    def test_chefsalad_risk_ratio(self):
        """ChefSalad Risk Ratio must equal 1.2186 (to 4 decimal places)."""
        from epiinfo.TablesAnalysis import TablesAnalysis as EpiTA
        ta = EpiTA()
        result = ta.Run(
            {'outcomeVariable': self.OUTCOME, 'exposureVariables': self.EXPOSURES},
            self.data,
        )
        idx = result['Variables'].index(f'{self.OUTCOME} * ChefSalad')
        rr = result['Statistics'][idx]['RiskRatio']
        self.assertAlmostEqual(rr, 1.2186, places=self.PLACES)

    def test_eggsaladsandwich_risk_ratio(self):
        """EggSaladSandwich Risk Ratio must equal 1.1830 (to 4 decimal places)."""
        from epiinfo.TablesAnalysis import TablesAnalysis as EpiTA
        ta = EpiTA()
        result = ta.Run(
            {'outcomeVariable': self.OUTCOME, 'exposureVariables': self.EXPOSURES},
            self.data,
        )
        idx = result['Variables'].index(f'{self.OUTCOME} * EggSaladSandwich')
        rr = result['Statistics'][idx]['RiskRatio']
        self.assertAlmostEqual(rr, 1.1830, places=self.PLACES)

    def test_both_variables_present_in_results_page(self):
        """The results HTML must display both variable labels."""
        response = self._run()
        self.assertContains(response, 'Ill * ChefSalad')
        self.assertContains(response, 'Ill * EggSaladSandwich')

    def test_results_page_contains_risk_ratio_values(self):
        """The rendered page must show the known RR values (to 4 decimal places)."""
        response = self._run()
        self.assertContains(response, '1.2186')
        self.assertContains(response, '1.1830')

    def test_results_page_contains_mid_p_odds_ratio(self):
        """Results must show MidPOR (Odds Ratio MLE) for both exposures."""
        response = self._run()
        # ChefSalad MidPOR = 1.6311 per reference HTML
        self.assertContains(response, '1.6311')
        # EggSaladSandwich MidPOR = 1.5765 per reference HTML
        self.assertContains(response, '1.5765')

    def test_results_page_contains_fisher_or_ci(self):
        """Results must show Fisher exact OR confidence limits for both exposures."""
        response = self._run()
        # ChefSalad: FisherORLL=0.9399, FisherORUL=2.8267
        self.assertContains(response, '0.9399')
        self.assertContains(response, '2.8267')
        # EggSaladSandwich: FisherORLL=0.9611, FisherORUL=2.6040
        self.assertContains(response, '0.9611')
        self.assertContains(response, '2.6040')


# ---------------------------------------------------------------------------
# Shared mock for LogisticRegression.doRegression()
# Variables = ['exposure', 'CONSTANT'], one non-constant term
# ---------------------------------------------------------------------------
MOCK_LOGISTIC_RESULT = SimpleNamespace(
    Variables=['exposure', 'CONSTANT'],
    Beta=[1.1450, -0.7644],
    SE=[0.3429, 0.3602],
    OR=[3.1424],
    ORLCL=[1.6046],
    ORUCL=[6.1539],
    Z=[3.3391, -2.1224],
    PZ=[0.0008, 0.0338],
    Iterations=4,
    MinusTwoLogLikelihood=393.3736,
    CasesIncluded=6,
    Score=14.7777,
    ScoreDF=1,
    ScoreP=0.0006,
    LikelihoodRatio=15.5999,
    LikelihoodRatioDF=1,
    LikelihoodRatioP=0.0004,
    InteractionOR=[],
)


# ===========================================================================
# LogisticFormViewTests
# ===========================================================================

class LogisticFormViewTests(TestCase):
    """TDD tests for the logistic regression variable-selection form view."""

    URL = 'core:logistic_form'

    def _set_session_data(self):
        session = self.client.session
        session['data'] = SAMPLE_DATA
        session['data_filename'] = 'sample.json'
        session.save()

    def test_requires_session_data(self):
        """GET without loaded data must return 400."""
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 400)

    def test_returns_200_with_session_data(self):
        """GET with data in session must return 200."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        """Must render the logistic_form partial template."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertTemplateUsed(response, 'core/partials/logistic_form.html')

    def test_all_columns_in_outcome_dropdown(self):
        """Every column name from the data must appear in the outcome select."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        for col in ['outcome', 'exposure', 'age']:
            self.assertContains(response, col)

    def test_exposure_checkboxes_present(self):
        """Must include exposure variable checkboxes."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, 'type="checkbox"')

    def test_match_variable_dropdown_present(self):
        """Must include a match variable dropdown."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, 'match_variable')

    def test_interaction_variables_checkboxes_present(self):
        """Must include interaction variable checkboxes."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, 'interaction_variables')

    def test_columns_sorted_alphabetically_case_insensitive(self):
        """Columns must appear in case-insensitive alphabetical order."""
        session = self.client.session
        session['data'] = [{'Zebra': 1, 'apple': 1, 'Mango': 1, 'banana': 1}]
        session.save()
        response = self.client.get(reverse(self.URL))
        content = response.content.decode()
        positions = [content.index(col) for col in ['apple', 'banana', 'Mango', 'Zebra']]
        self.assertEqual(positions, sorted(positions))

    def test_form_posts_to_run_logistic_url(self):
        """The form action must point to the run_logistic endpoint."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, reverse('core:run_logistic'))


# ===========================================================================
# RunLogisticViewTests
# ===========================================================================

class RunLogisticViewTests(TestCase):
    """TDD tests for the run_logistic view (calls epiinfo.LogisticRegression)."""

    URL = 'core:run_logistic'

    def _set_session_data(self):
        session = self.client.session
        session['data'] = SAMPLE_DATA
        session.save()

    def _run(self, outcome='outcome', exposures=None, match='', interactions=None):
        if exposures is None:
            exposures = ['exposure']
        data = {
            'outcome_variable': outcome,
            'exposure_variables': exposures,
            'match_variable': match,
        }
        if interactions:
            data['interaction_variables'] = interactions
        return self.client.post(reverse(self.URL), data)

    def test_get_returns_405(self):
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 405)

    def test_requires_session_data(self):
        response = self._run()
        self.assertEqual(response.status_code, 400)

    def test_missing_outcome_returns_400(self):
        self._set_session_data()
        response = self.client.post(
            reverse(self.URL),
            {'exposure_variables': ['exposure'], 'match_variable': ''},
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_exposures_returns_400(self):
        self._set_session_data()
        response = self.client.post(
            reverse(self.URL),
            {'outcome_variable': 'outcome', 'match_variable': ''},
        )
        self.assertEqual(response.status_code, 400)

    @patch('core.views.LogisticRegression')
    def test_valid_run_returns_200(self, MockLR):
        MockLR.return_value.doRegression.return_value = MOCK_LOGISTIC_RESULT
        self._set_session_data()
        response = self._run()
        self.assertEqual(response.status_code, 200)

    @patch('core.views.LogisticRegression')
    def test_valid_run_uses_results_template(self, MockLR):
        MockLR.return_value.doRegression.return_value = MOCK_LOGISTIC_RESULT
        self._set_session_data()
        response = self._run()
        self.assertTemplateUsed(response, 'core/partials/logistic_results.html')

    @patch('core.views.LogisticRegression')
    def test_results_contain_term_name(self, MockLR):
        """Results must display the exposure variable name as a term."""
        MockLR.return_value.doRegression.return_value = MOCK_LOGISTIC_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, 'exposure')

    @patch('core.views.LogisticRegression')
    def test_results_contain_constant(self, MockLR):
        """Results must display the CONSTANT row."""
        MockLR.return_value.doRegression.return_value = MOCK_LOGISTIC_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, 'CONSTANT')

    @patch('core.views.LogisticRegression')
    def test_results_contain_odds_ratio(self, MockLR):
        """Results must display the Odds Ratio value for a term."""
        MockLR.return_value.doRegression.return_value = MOCK_LOGISTIC_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, '3.1424')

    @patch('core.views.LogisticRegression')
    def test_calls_doregression_with_outcome_and_exposures(self, MockLR):
        """doRegression() must be called with outcome as dependvar."""
        MockLR.return_value.doRegression.return_value = MOCK_LOGISTIC_RESULT
        self._set_session_data()
        self._run(outcome='outcome', exposures=['exposure'])
        call_args = MockLR.return_value.doRegression.call_args
        ivl = call_args[0][0]
        self.assertEqual(ivl.get('outcome'), 'dependvar')
        self.assertIn('exposure', ivl.get('exposureVariables', []))

    @patch('core.views.LogisticRegression')
    def test_interaction_terms_added_to_exposure_variables(self, MockLR):
        """Pairwise interaction terms must be appended to exposureVariables."""
        MockLR.return_value.doRegression.return_value = MOCK_LOGISTIC_RESULT
        self._set_session_data()
        self._run(
            outcome='outcome',
            exposures=['exposure', 'age'],
            interactions=['exposure', 'age'],
        )
        call_args = MockLR.return_value.doRegression.call_args
        ivl = call_args[0][0]
        ev = ivl.get('exposureVariables', [])
        self.assertIn('exposure*age', ev)

    @patch('core.views.LogisticRegression')
    def test_match_variable_included_when_provided(self, MockLR):
        """Match variable must be set as matchvar in inputVariableList."""
        MockLR.return_value.doRegression.return_value = MOCK_LOGISTIC_RESULT
        self._set_session_data()
        response = self.client.post(
            reverse(self.URL),
            {
                'outcome_variable': 'outcome',
                'exposure_variables': ['exposure'],
                'match_variable': 'age',
            },
        )
        call_args = MockLR.return_value.doRegression.call_args
        ivl = call_args[0][0]
        self.assertEqual(ivl.get('age'), 'matchvar')

    @patch('core.views.LogisticRegression')
    def test_results_contain_model_fit_stats(self, MockLR):
        """Results must display convergence and model fit statistics."""
        MockLR.return_value.doRegression.return_value = MOCK_LOGISTIC_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, '393.3736')   # -2LL
        self.assertContains(response, '4')           # iterations

    @patch('core.views.LogisticRegression')
    def test_results_contain_score_test(self, MockLR):
        """Results must display Score and Likelihood Ratio test statistics."""
        MockLR.return_value.doRegression.return_value = MOCK_LOGISTIC_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, '14.7777')    # Score
        self.assertContains(response, '15.5999')    # LR


# ===========================================================================
# LogisticIntegrationTests
# ===========================================================================

class LogisticIntegrationTests(TestCase):
    """
    Integration test: loads Salmonellosis.json, runs LogisticRegression
    against the live epiinfo library, and asserts known OR values.

    Reference values from sample_data/Salmonellosis.html:
      Ill = ChefSalad + EggSaladSandwich (no interaction)
        ChefSalad OR = 3.1424
        EggSaladSandwich OR = 2.8343
    """

    OUTCOME = 'Ill'
    EXPOSURES = ['ChefSalad', 'EggSaladSandwich']
    PLACES = 4

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(SAMPLE_DATA_PATH) as f:
            cls.data = json.load(f)

    def _set_session(self):
        session = self.client.session
        session['data'] = self.data
        session.save()

    def _run(self, interactions=None):
        self._set_session()
        post_data = {
            'outcome_variable': self.OUTCOME,
            'exposure_variables': self.EXPOSURES,
            'match_variable': '',
        }
        if interactions:
            post_data['interaction_variables'] = interactions
        return self.client.post(reverse('core:run_logistic'), post_data)

    def test_run_logistic_returns_200(self):
        """run_logistic view must return HTTP 200 for Salmonellosis inputs."""
        response = self._run()
        self.assertEqual(response.status_code, 200)

    def test_chefsalad_odds_ratio(self):
        """ChefSalad OR must equal 3.1424 (to 4 decimal places)."""
        from epiinfo.LogisticRegression import LogisticRegression as EpiLR
        lr = EpiLR()
        results = lr.doRegression(
            {'Ill': 'dependvar', 'exposureVariables': self.EXPOSURES},
            self.data,
        )
        idx = results.Variables.index('ChefSalad')
        self.assertAlmostEqual(results.OR[idx], 3.1424, places=self.PLACES)

    def test_eggsaladsandwich_odds_ratio(self):
        """EggSaladSandwich OR must equal 2.8343 (to 4 decimal places)."""
        from epiinfo.LogisticRegression import LogisticRegression as EpiLR
        lr = EpiLR()
        results = lr.doRegression(
            {'Ill': 'dependvar', 'exposureVariables': self.EXPOSURES},
            self.data,
        )
        idx = results.Variables.index('EggSaladSandwich')
        self.assertAlmostEqual(results.OR[idx], 2.8343, places=self.PLACES)

    def test_results_page_shows_or_values(self):
        """The rendered page must display the known OR values."""
        response = self._run()
        self.assertContains(response, '3.1424')
        self.assertContains(response, '2.8343')

    def test_results_page_shows_both_term_names(self):
        """Results page must display both variable names as terms."""
        response = self._run()
        self.assertContains(response, 'ChefSalad')
        self.assertContains(response, 'EggSaladSandwich')

    def test_results_page_shows_constant(self):
        """Results page must display the CONSTANT term."""
        response = self._run()
        self.assertContains(response, 'CONSTANT')

    def test_interaction_run_returns_200(self):
        """run_logistic with interaction variables must return HTTP 200."""
        response = self._run(interactions=['ChefSalad', 'EggSaladSandwich'])
        self.assertEqual(response.status_code, 200)

    def test_interaction_results_page_shows_interaction_table(self):
        """Results with interaction must include an interaction odds ratios section."""
        response = self._run(interactions=['ChefSalad', 'EggSaladSandwich'])
        self.assertContains(response, 'Interaction')

    # ------------------------------------------------------------------
    # Detailed value checks from Salmonellosis.html Analysis 1
    # (Ill = ChefSalad + EggSaladSandwich, no interaction)
    # ------------------------------------------------------------------

    def test_chefsalad_or_confidence_limits(self):
        """ChefSalad 95% CI must be [1.6046, 6.1539]."""
        from epiinfo.LogisticRegression import LogisticRegression as EpiLR
        lr = EpiLR()
        results = lr.doRegression(
            {'Ill': 'dependvar', 'exposureVariables': self.EXPOSURES},
            self.data,
        )
        idx = results.Variables.index('ChefSalad')
        self.assertAlmostEqual(results.ORLCL[idx], 1.6046, places=self.PLACES)
        self.assertAlmostEqual(results.ORUCL[idx], 6.1539, places=self.PLACES)

    def test_eggsaladsandwich_or_confidence_limits(self):
        """EggSaladSandwich 95% CI must be [1.5300, 5.2506]."""
        from epiinfo.LogisticRegression import LogisticRegression as EpiLR
        lr = EpiLR()
        results = lr.doRegression(
            {'Ill': 'dependvar', 'exposureVariables': self.EXPOSURES},
            self.data,
        )
        idx = results.Variables.index('EggSaladSandwich')
        self.assertAlmostEqual(results.ORLCL[idx], 1.5300, places=self.PLACES)
        self.assertAlmostEqual(results.ORUCL[idx], 5.2506, places=self.PLACES)

    def test_chefsalad_coefficient_and_se(self):
        """ChefSalad coefficient must be 1.1450, SE must be 0.3429."""
        from epiinfo.LogisticRegression import LogisticRegression as EpiLR
        lr = EpiLR()
        results = lr.doRegression(
            {'Ill': 'dependvar', 'exposureVariables': self.EXPOSURES},
            self.data,
        )
        idx = results.Variables.index('ChefSalad')
        self.assertAlmostEqual(results.Beta[idx], 1.1450, places=self.PLACES)
        self.assertAlmostEqual(results.SE[idx], 0.3429, places=self.PLACES)

    def test_chefsalad_z_and_p(self):
        """ChefSalad Z-statistic must be 3.3391, P-value must be 0.0008."""
        from epiinfo.LogisticRegression import LogisticRegression as EpiLR
        lr = EpiLR()
        results = lr.doRegression(
            {'Ill': 'dependvar', 'exposureVariables': self.EXPOSURES},
            self.data,
        )
        idx = results.Variables.index('ChefSalad')
        self.assertAlmostEqual(results.Z[idx], 3.3391, places=self.PLACES)
        self.assertAlmostEqual(results.PZ[idx], 0.0008, places=self.PLACES)

    def test_model_fit_stats(self):
        """Iterations must be 4, -2LL must be 393.3736, cases must be 309."""
        from epiinfo.LogisticRegression import LogisticRegression as EpiLR
        lr = EpiLR()
        results = lr.doRegression(
            {'Ill': 'dependvar', 'exposureVariables': self.EXPOSURES},
            self.data,
        )
        self.assertEqual(results.Iterations, 4)
        self.assertAlmostEqual(results.MinusTwoLogLikelihood, 393.3736, places=self.PLACES)
        self.assertEqual(results.CasesIncluded, 309)

    def test_score_and_lr_tests(self):
        """Score must be 14.7777 (df=2, p=0.0006); LR must be 15.5999 (df=2, p=0.0004)."""
        from epiinfo.LogisticRegression import LogisticRegression as EpiLR
        lr = EpiLR()
        results = lr.doRegression(
            {'Ill': 'dependvar', 'exposureVariables': self.EXPOSURES},
            self.data,
        )
        self.assertAlmostEqual(results.Score, 14.7777, places=self.PLACES)
        self.assertEqual(results.ScoreDF, 2)
        self.assertAlmostEqual(results.ScoreP, 0.0006, places=self.PLACES)
        self.assertAlmostEqual(results.LikelihoodRatio, 15.5999, places=self.PLACES)
        self.assertEqual(results.LikelihoodRatioDF, 2)
        self.assertAlmostEqual(results.LikelihoodRatioP, 0.0004, places=self.PLACES)

    def test_results_page_shows_ci_and_beta_values(self):
        """Rendered page must show CI limits and Beta for ChefSalad."""
        response = self._run()
        self.assertContains(response, '1.6046')   # ChefSalad ORLCL
        self.assertContains(response, '6.1539')   # ChefSalad ORUCL
        self.assertContains(response, '1.1450')   # ChefSalad Beta
        self.assertContains(response, '0.3429')   # ChefSalad SE
        self.assertContains(response, '3.3391')   # ChefSalad Z

    def test_results_page_shows_model_fit(self):
        """Rendered page must show -2LL, iterations, and cases."""
        response = self._run()
        self.assertContains(response, '393.3736')
        self.assertContains(response, '309')

    def test_results_page_shows_score_and_lr(self):
        """Rendered page must show Score and LR test statistics."""
        response = self._run()
        self.assertContains(response, '14.7777')
        self.assertContains(response, '15.5999')

    # ------------------------------------------------------------------
    # Detailed value checks from Salmonellosis.html Analysis 2
    # (with ChefSalad * EggSaladSandwich interaction)
    # ------------------------------------------------------------------

    def test_interaction_chefsalad_or(self):
        """With interaction, ChefSalad OR must be 13.8937."""
        from epiinfo.LogisticRegression import LogisticRegression as EpiLR
        lr = EpiLR()
        results = lr.doRegression(
            {
                'Ill': 'dependvar',
                'exposureVariables': self.EXPOSURES + ['ChefSalad*EggSaladSandwich'],
            },
            self.data,
        )
        idx = results.Variables.index('ChefSalad')
        self.assertAlmostEqual(results.OR[idx], 13.8937, places=self.PLACES)

    def test_interaction_minus_two_ll(self):
        """-2LL with interaction must be 389.8618."""
        from epiinfo.LogisticRegression import LogisticRegression as EpiLR
        lr = EpiLR()
        results = lr.doRegression(
            {
                'Ill': 'dependvar',
                'exposureVariables': self.EXPOSURES + ['ChefSalad*EggSaladSandwich'],
            },
            self.data,
        )
        self.assertAlmostEqual(results.MinusTwoLogLikelihood, 389.8618, places=self.PLACES)

    def test_interaction_results_page_shows_reference_values(self):
        """Rendered page with interaction must show key values from reference HTML."""
        response = self._run(interactions=['ChefSalad', 'EggSaladSandwich'])
        self.assertContains(response, '13.8937')   # ChefSalad OR (with interaction)
        self.assertContains(response, '389.8618')  # -2LL


# ---------------------------------------------------------------------------
# Shared mock for LogBinomialRegression.doRegression()
# ---------------------------------------------------------------------------
MOCK_LOGBINOMIAL_RESULT = SimpleNamespace(
    Variables=['exposure', 'CONSTANT'],
    Beta=[0.3359, -0.8579],
    SE=[0.1156, 0.1275],
    RR=[1.3992],
    RRLCL=[1.1155],
    RRUCL=[1.7550],
    Z=[2.9054, -6.7264],
    PZ=[0.0037, 0.0000],
    Iterations=7,
    LogLikelihood=-197.8080,
    CasesIncluded=6,
    InteractionRR=[],
)


# ===========================================================================
# LogBinomialFormViewTests
# ===========================================================================

class LogBinomialFormViewTests(TestCase):
    """TDD tests for the log-binomial regression variable-selection form view."""

    URL = 'core:logbinomial_form'

    def _set_session_data(self):
        session = self.client.session
        session['data'] = SAMPLE_DATA
        session['data_filename'] = 'sample.json'
        session.save()

    def test_requires_session_data(self):
        """GET without loaded data must return 400."""
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 400)

    def test_returns_200_with_session_data(self):
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertTemplateUsed(response, 'core/partials/logbinomial_form.html')

    def test_all_columns_in_outcome_dropdown(self):
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        for col in ['outcome', 'exposure', 'age']:
            self.assertContains(response, col)

    def test_exposure_checkboxes_present(self):
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, 'type="checkbox"')

    def test_no_match_variable_dropdown(self):
        """Log-binomial form must NOT include a match variable option."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertNotContains(response, 'match_variable')

    def test_interaction_variables_checkboxes_present(self):
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, 'interaction_variables')

    def test_columns_sorted_alphabetically_case_insensitive(self):
        session = self.client.session
        session['data'] = [{'Zebra': 1, 'apple': 1, 'Mango': 1, 'banana': 1}]
        session.save()
        response = self.client.get(reverse(self.URL))
        content = response.content.decode()
        positions = [content.index(col) for col in ['apple', 'banana', 'Mango', 'Zebra']]
        self.assertEqual(positions, sorted(positions))

    def test_form_posts_to_run_logbinomial_url(self):
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, reverse('core:run_logbinomial'))


# ===========================================================================
# RunLogBinomialViewTests
# ===========================================================================

class RunLogBinomialViewTests(TestCase):
    """TDD tests for the run_logbinomial view (calls epiinfo.LogBinomialRegression)."""

    URL = 'core:run_logbinomial'

    def _set_session_data(self):
        session = self.client.session
        session['data'] = SAMPLE_DATA
        session.save()

    def _run(self, outcome='outcome', exposures=None, interactions=None):
        if exposures is None:
            exposures = ['exposure']
        data = {
            'outcome_variable': outcome,
            'exposure_variables': exposures,
        }
        if interactions:
            data['interaction_variables'] = interactions
        return self.client.post(reverse(self.URL), data)

    def test_get_returns_405(self):
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 405)

    def test_requires_session_data(self):
        response = self._run()
        self.assertEqual(response.status_code, 400)

    def test_missing_outcome_returns_400(self):
        self._set_session_data()
        response = self.client.post(
            reverse(self.URL),
            {'exposure_variables': ['exposure']},
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_exposures_returns_400(self):
        self._set_session_data()
        response = self.client.post(
            reverse(self.URL),
            {'outcome_variable': 'outcome'},
        )
        self.assertEqual(response.status_code, 400)

    @patch('core.views.LogBinomialRegression')
    def test_valid_run_returns_200(self, MockLB):
        MockLB.return_value.doRegression.return_value = MOCK_LOGBINOMIAL_RESULT
        self._set_session_data()
        response = self._run()
        self.assertEqual(response.status_code, 200)

    @patch('core.views.LogBinomialRegression')
    def test_valid_run_uses_results_template(self, MockLB):
        MockLB.return_value.doRegression.return_value = MOCK_LOGBINOMIAL_RESULT
        self._set_session_data()
        response = self._run()
        self.assertTemplateUsed(response, 'core/partials/logbinomial_results.html')

    @patch('core.views.LogBinomialRegression')
    def test_results_contain_risk_ratio(self, MockLB):
        """Results must display the Risk Ratio value for a term."""
        MockLB.return_value.doRegression.return_value = MOCK_LOGBINOMIAL_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, '1.3992')

    @patch('core.views.LogBinomialRegression')
    def test_results_contain_term_name_and_constant(self, MockLB):
        MockLB.return_value.doRegression.return_value = MOCK_LOGBINOMIAL_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, 'exposure')
        self.assertContains(response, 'CONSTANT')

    @patch('core.views.LogBinomialRegression')
    def test_results_contain_log_likelihood(self, MockLB):
        """Results must display the final log-likelihood (not -2LL)."""
        MockLB.return_value.doRegression.return_value = MOCK_LOGBINOMIAL_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, '197.8080')

    @patch('core.views.LogBinomialRegression')
    def test_calls_doregression_with_outcome_and_exposures(self, MockLB):
        MockLB.return_value.doRegression.return_value = MOCK_LOGBINOMIAL_RESULT
        self._set_session_data()
        self._run(outcome='outcome', exposures=['exposure'])
        call_args = MockLB.return_value.doRegression.call_args
        ivl = call_args[0][0]
        self.assertEqual(ivl.get('outcome'), 'dependvar')
        self.assertIn('exposure', ivl.get('exposureVariables', []))

    @patch('core.views.LogBinomialRegression')
    def test_interaction_terms_added_to_exposure_variables(self, MockLB):
        MockLB.return_value.doRegression.return_value = MOCK_LOGBINOMIAL_RESULT
        self._set_session_data()
        self._run(
            outcome='outcome',
            exposures=['exposure', 'age'],
            interactions=['exposure', 'age'],
        )
        call_args = MockLB.return_value.doRegression.call_args
        ivl = call_args[0][0]
        self.assertIn('exposure*age', ivl.get('exposureVariables', []))


# ===========================================================================
# LogBinomialIntegrationTests
# ===========================================================================

class LogBinomialIntegrationTests(TestCase):
    """
    Integration test: loads Salmonellosis.json, runs LogBinomialRegression
    against the live epiinfo library, and asserts known RR values.

    Reference values from sample_data/Salmonellosis.html:
      Ill = ChefSalad + EggSaladSandwich (no interaction):
        ChefSalad        RR=1.3992, CI=[1.1155, 1.7550], Beta=0.3359, SE=0.1156, Z=2.9054, P=0.0037
        EggSaladSandwich RR=1.3325, CI=[1.1251, 1.5780], Beta=0.2870, SE=0.0863, Z=3.3261, P=0.0009
        CONSTANT         Beta=-0.8579, SE=0.1275, Z=-6.7264, P=0.0000
        Iterations=7, LogLikelihood=-197.8080, Cases=309

      Ill = ChefSalad + EggSaladSandwich + ChefSalad*EggSaladSandwich (interaction):
        ChefSalad        RR=6.0736, CI=[0.9422, 39.1510]
        EggSaladSandwich RR=6.0000, CI=[0.9255, 38.8983]
        Iterations=8, LogLikelihood=-194.9309, Cases=309
        InteractionRR:
          ChefSalad 1 vs 0 at EggSaladSandwich=0: 6.073605 [0.942214, 39.151041]
          ChefSalad 1 vs 0 at EggSaladSandwich=1: 1.287879 [1.021483, 1.623750]
    """

    OUTCOME = 'Ill'
    EXPOSURES = ['ChefSalad', 'EggSaladSandwich']
    PLACES = 4

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(SAMPLE_DATA_PATH) as f:
            cls.data = json.load(f)

    def _set_session(self):
        session = self.client.session
        session['data'] = self.data
        session.save()

    def _run(self, interactions=None):
        self._set_session()
        post_data = {
            'outcome_variable': self.OUTCOME,
            'exposure_variables': self.EXPOSURES,
        }
        if interactions:
            post_data['interaction_variables'] = interactions
        return self.client.post(reverse('core:run_logbinomial'), post_data)

    def _direct(self, exposures=None):
        from epiinfo.LogBinomialRegression import LogBinomialRegression as EpiLB
        lb = EpiLB()
        return lb.doRegression(
            {'Ill': 'dependvar', 'exposureVariables': exposures or self.EXPOSURES},
            self.data,
        )

    # --- Analysis 1: no interaction ---

    def test_run_returns_200(self):
        self.assertEqual(self._run().status_code, 200)

    def test_chefsalad_rr(self):
        """ChefSalad RR must equal 1.3992 (to 4 dp)."""
        r = self._direct()
        idx = r.Variables.index('ChefSalad')
        self.assertAlmostEqual(r.RR[idx], 1.3992, places=self.PLACES)

    def test_eggsaladsandwich_rr(self):
        """EggSaladSandwich RR must equal 1.3325 (to 4 dp)."""
        r = self._direct()
        idx = r.Variables.index('EggSaladSandwich')
        self.assertAlmostEqual(r.RR[idx], 1.3325, places=self.PLACES)

    def test_chefsalad_rr_confidence_limits(self):
        """ChefSalad 95% CI must be [1.1155, 1.7550]."""
        r = self._direct()
        idx = r.Variables.index('ChefSalad')
        self.assertAlmostEqual(r.RRLCL[idx], 1.1155, places=self.PLACES)
        self.assertAlmostEqual(r.RRUCL[idx], 1.7550, places=self.PLACES)

    def test_eggsaladsandwich_rr_confidence_limits(self):
        """EggSaladSandwich 95% CI must be [1.1251, 1.5780]."""
        r = self._direct()
        idx = r.Variables.index('EggSaladSandwich')
        self.assertAlmostEqual(r.RRLCL[idx], 1.1251, places=self.PLACES)
        self.assertAlmostEqual(r.RRUCL[idx], 1.5780, places=self.PLACES)

    def test_chefsalad_beta_and_se(self):
        """ChefSalad Beta=0.3359, SE=0.1156."""
        r = self._direct()
        idx = r.Variables.index('ChefSalad')
        self.assertAlmostEqual(r.Beta[idx], 0.3359, places=self.PLACES)
        self.assertAlmostEqual(r.SE[idx], 0.1156, places=self.PLACES)

    def test_chefsalad_z_and_p(self):
        """ChefSalad Z=2.9054, P=0.0037."""
        r = self._direct()
        idx = r.Variables.index('ChefSalad')
        self.assertAlmostEqual(r.Z[idx], 2.9054, places=self.PLACES)
        self.assertAlmostEqual(r.PZ[idx], 0.0037, places=self.PLACES)

    def test_model_fit_stats(self):
        """Iterations=7, LogLikelihood=-197.8080, Cases=309."""
        r = self._direct()
        self.assertEqual(r.Iterations, 7)
        self.assertAlmostEqual(r.LogLikelihood, -197.8080, places=self.PLACES)
        self.assertEqual(r.CasesIncluded, 309)

    def test_results_page_shows_rr_values(self):
        response = self._run()
        self.assertContains(response, '1.3992')
        self.assertContains(response, '1.3325')

    def test_results_page_shows_ci_and_beta(self):
        response = self._run()
        self.assertContains(response, '1.1155')   # ChefSalad RRLCL
        self.assertContains(response, '1.7550')   # ChefSalad RRUCL
        self.assertContains(response, '0.3359')   # ChefSalad Beta
        self.assertContains(response, '0.1156')   # ChefSalad SE
        self.assertContains(response, '2.9054')   # ChefSalad Z

    def test_results_page_shows_log_likelihood(self):
        response = self._run()
        self.assertContains(response, '197.8080')
        self.assertContains(response, '309')

    # --- Analysis 2: with interaction ---

    def test_interaction_run_returns_200(self):
        self.assertEqual(self._run(interactions=['ChefSalad', 'EggSaladSandwich']).status_code, 200)

    def test_interaction_chefsalad_rr(self):
        """With interaction, ChefSalad RR=6.0736."""
        r = self._direct(self.EXPOSURES + ['ChefSalad*EggSaladSandwich'])
        idx = r.Variables.index('ChefSalad')
        self.assertAlmostEqual(r.RR[idx], 6.0736, places=self.PLACES)

    def test_interaction_log_likelihood(self):
        """With interaction, LogLikelihood=-194.9309."""
        r = self._direct(self.EXPOSURES + ['ChefSalad*EggSaladSandwich'])
        self.assertAlmostEqual(r.LogLikelihood, -194.9309, places=self.PLACES)

    def test_interaction_rr_rows(self):
        """InteractionRR must contain two rows with reference values."""
        r = self._direct(self.EXPOSURES + ['ChefSalad*EggSaladSandwich'])
        self.assertEqual(len(r.InteractionRR), 2)
        # Row 0: ChefSalad 1 vs 0 at EggSaladSandwich=0
        self.assertAlmostEqual(r.InteractionRR[0][2], 6.073605, places=4)
        self.assertAlmostEqual(r.InteractionRR[0][3], 0.942214, places=4)
        self.assertAlmostEqual(r.InteractionRR[0][4], 39.151041, places=2)
        # Row 1: ChefSalad 1 vs 0 at EggSaladSandwich=1
        self.assertAlmostEqual(r.InteractionRR[1][2], 1.287879, places=4)
        self.assertAlmostEqual(r.InteractionRR[1][3], 1.021483, places=4)
        self.assertAlmostEqual(r.InteractionRR[1][4], 1.623750, places=4)

    def test_interaction_results_page_shows_reference_values(self):
        response = self._run(interactions=['ChefSalad', 'EggSaladSandwich'])
        self.assertContains(response, '6.0736')    # ChefSalad RR (with interaction)
        self.assertContains(response, '194.9309')  # LogLikelihood

    def test_interaction_results_page_shows_interaction_table(self):
        response = self._run(interactions=['ChefSalad', 'EggSaladSandwich'])
        self.assertContains(response, 'Risk Ratio')
        self.assertContains(response, 'Interaction')


# ---------------------------------------------------------------------------
# Shared mock for LinearRegression.doRegression()
# Returns a list of dicts (not a SimpleNamespace object)
# ---------------------------------------------------------------------------
MOCK_LINEAR_RESULT = [
    {
        'variable': 'exposure',
        'beta': 5.888, 'lcl': 4.418, 'ucl': 7.357,
        'stderror': 0.680, 'ftest': 74.9229, 'pvalue': 0.000001,
    },
    {
        'variable': 'CONSTANT',
        'beta': 53.450, 'lcl': 43.660, 'ucl': 63.241,
        'stderror': 4.532, 'ftest': 139.1042, 'pvalue': 0.000000,
    },
    {
        'r2': 0.88,
        'regressionDF': 1, 'sumOfSquares': 591.036,
        'meanSquare': 591.036, 'fStatistic': 74.923,
        'residualsDF': 14, 'residualsSS': 79.902,
        'residualsMS': 5.707,
        'totalDF': 15, 'totalSS': 670.938,
    },
]

BABY_BP_PATH = Path(__file__).resolve().parent.parent / 'sample_data' / 'BabyBloodPressure.json'


# ===========================================================================
# LinearFormViewTests
# ===========================================================================

class LinearFormViewTests(TestCase):
    """TDD tests for the linear regression variable-selection form view."""

    URL = 'core:linear_form'

    def _set_session_data(self):
        session = self.client.session
        session['data'] = SAMPLE_DATA
        session['data_filename'] = 'sample.json'
        session.save()

    def test_requires_session_data(self):
        """GET without loaded data must return 400."""
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 400)

    def test_returns_200_with_session_data(self):
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertTemplateUsed(response, 'core/partials/linear_form.html')

    def test_all_columns_in_outcome_dropdown(self):
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        for col in ['outcome', 'exposure', 'age']:
            self.assertContains(response, col)

    def test_exposure_checkboxes_present(self):
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, 'type="checkbox"')

    def test_no_match_variable_dropdown(self):
        """Linear regression form must NOT include a match variable option."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertNotContains(response, 'match_variable')

    def test_interaction_variables_checkboxes_present(self):
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, 'interaction_variables')

    def test_columns_sorted_alphabetically_case_insensitive(self):
        session = self.client.session
        session['data'] = [{'Zebra': 1, 'apple': 1, 'Mango': 1, 'banana': 1}]
        session.save()
        response = self.client.get(reverse(self.URL))
        content = response.content.decode()
        positions = [content.index(col) for col in ['apple', 'banana', 'Mango', 'Zebra']]
        self.assertEqual(positions, sorted(positions))

    def test_form_posts_to_run_linear_url(self):
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, reverse('core:run_linear'))


# ===========================================================================
# RunLinearViewTests
# ===========================================================================

class RunLinearViewTests(TestCase):
    """TDD tests for the run_linear view (calls epiinfo.LinearRegression)."""

    URL = 'core:run_linear'

    def _set_session_data(self):
        session = self.client.session
        session['data'] = SAMPLE_DATA
        session.save()

    def _run(self, outcome='outcome', exposures=None, interactions=None):
        if exposures is None:
            exposures = ['exposure']
        data = {
            'outcome_variable': outcome,
            'exposure_variables': exposures,
        }
        if interactions:
            data['interaction_variables'] = interactions
        return self.client.post(reverse(self.URL), data)

    def test_get_returns_405(self):
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 405)

    def test_requires_session_data(self):
        response = self._run()
        self.assertEqual(response.status_code, 400)

    def test_missing_outcome_returns_400(self):
        self._set_session_data()
        response = self.client.post(
            reverse(self.URL),
            {'exposure_variables': ['exposure']},
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_exposures_returns_400(self):
        self._set_session_data()
        response = self.client.post(
            reverse(self.URL),
            {'outcome_variable': 'outcome'},
        )
        self.assertEqual(response.status_code, 400)

    @patch('core.views.LinearRegression')
    def test_valid_run_returns_200(self, MockLR):
        MockLR.return_value.doRegression.return_value = MOCK_LINEAR_RESULT
        self._set_session_data()
        response = self._run()
        self.assertEqual(response.status_code, 200)

    @patch('core.views.LinearRegression')
    def test_valid_run_uses_results_template(self, MockLR):
        MockLR.return_value.doRegression.return_value = MOCK_LINEAR_RESULT
        self._set_session_data()
        response = self._run()
        self.assertTemplateUsed(response, 'core/partials/linear_results.html')

    @patch('core.views.LinearRegression')
    def test_results_contain_term_name(self, MockLR):
        """Results must display the exposure variable name as a term."""
        MockLR.return_value.doRegression.return_value = MOCK_LINEAR_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, 'exposure')

    @patch('core.views.LinearRegression')
    def test_results_contain_constant(self, MockLR):
        """Results must display the CONSTANT term."""
        MockLR.return_value.doRegression.return_value = MOCK_LINEAR_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, 'CONSTANT')

    @patch('core.views.LinearRegression')
    def test_results_contain_coefficient(self, MockLR):
        """Results must display a coefficient value."""
        MockLR.return_value.doRegression.return_value = MOCK_LINEAR_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, '5.8880')

    @patch('core.views.LinearRegression')
    def test_results_contain_r_squared(self, MockLR):
        """Results must display the R² value."""
        MockLR.return_value.doRegression.return_value = MOCK_LINEAR_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, '0.88')

    @patch('core.views.LinearRegression')
    def test_results_contain_anova_table(self, MockLR):
        """Results must display ANOVA table headings."""
        MockLR.return_value.doRegression.return_value = MOCK_LINEAR_RESULT
        self._set_session_data()
        response = self._run()
        self.assertContains(response, 'Regression')
        self.assertContains(response, 'Residuals')

    @patch('core.views.LinearRegression')
    def test_calls_doregression_with_dependvar(self, MockLR):
        """doRegression() must be called with 'dependvar' key set to the outcome name."""
        MockLR.return_value.doRegression.return_value = MOCK_LINEAR_RESULT
        self._set_session_data()
        self._run(outcome='outcome', exposures=['exposure'])
        call_args = MockLR.return_value.doRegression.call_args
        ivl = call_args[0][0]
        self.assertEqual(ivl.get('dependvar'), 'outcome')
        self.assertIn('exposure', ivl.get('exposureVariables', []))

    @patch('core.views.LinearRegression')
    def test_interaction_terms_added_to_exposure_variables(self, MockLR):
        """Pairwise interaction terms must be appended to exposureVariables."""
        MockLR.return_value.doRegression.return_value = MOCK_LINEAR_RESULT
        self._set_session_data()
        self._run(
            outcome='outcome',
            exposures=['exposure', 'age'],
            interactions=['exposure', 'age'],
        )
        call_args = MockLR.return_value.doRegression.call_args
        ivl = call_args[0][0]
        self.assertIn('exposure*age', ivl.get('exposureVariables', []))


# ===========================================================================
# LinearRegressionIntegrationTests
# ===========================================================================

class LinearRegressionIntegrationTests(TestCase):
    """
    Integration test: loads BabyBloodPressure.json, runs LinearRegression
    against the live epiinfo library, and asserts known values.

    Reference values from sample_data/Salmonellosis.html:

    Analysis 1 — SystolicBlood = AgeInDays + Birthweight (no interaction):
      AgeInDays:   beta=5.888,  lcl=4.418,  ucl=7.357,  se=0.680,  f=74.9229,  p≈0 (< 0.0001)
      Birthweight: beta=0.126,  lcl=0.051,  ucl=0.200,  se=0.034,  f=13.3770,  p=0.002896
      CONSTANT:    beta=53.450, lcl=43.660, ucl=63.241, se=4.532,  f=139.1042, p≈0 (< 0.0001)
      R²=0.88
      ANOVA: Regression df=2, SS=591.036, MS=295.518, F=48.081
             Residuals  df=13, SS=79.902,  MS=6.146
             Total      df=15, SS=670.938

    Analysis 2 — SystolicBlood = AgeInDays + Birthweight + AgeInDays*Birthweight:
      AgeInDays:            beta=21.287,  p=0.005075
      Birthweight:          beta=0.551,   p=0.008026
      AgeInDays*Birthweight beta=-0.128,  p=0.028693
      CONSTANT:             beta=2.552,   p=0.904570
      R²=0.92
      ANOVA: Regression df=3, SS=618.183, F=46.873
             Residuals  df=12, SS=52.754
    """

    OUTCOME = 'SystolicBlood'
    EXPOSURES = ['AgeInDays', 'Birthweight']
    PLACES = 3

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(BABY_BP_PATH) as f:
            cls.data = json.load(f)

    def _set_session(self):
        session = self.client.session
        session['data'] = self.data
        session.save()

    def _run(self, interactions=None):
        self._set_session()
        post_data = {
            'outcome_variable': self.OUTCOME,
            'exposure_variables': self.EXPOSURES,
        }
        if interactions:
            post_data['interaction_variables'] = interactions
        return self.client.post(reverse('core:run_linear'), post_data)

    def _direct(self, exposures=None):
        from epiinfo.LinearRegression import LinearRegression as EpiLR
        exp = exposures or self.EXPOSURES
        interaction_terms = [v for v in exp if '*' in v]
        if interaction_terms:
            data = []
            for record in self.data:
                row = dict(record)
                for term in interaction_terms:
                    a, b = term.split('*')
                    try:
                        row[term] = float(record[a]) * float(record[b])
                    except (ValueError, TypeError, KeyError):
                        row[term] = None
                data.append(row)
        else:
            data = self.data
        lr = EpiLR()
        return lr.doRegression(
            {'dependvar': self.OUTCOME, 'exposureVariables': exp},
            data,
        )

    def _term(self, results, name):
        return next(r for r in results if isinstance(r, dict) and r.get('variable') == name)

    def _stats(self, results):
        return next(r for r in results if isinstance(r, dict) and 'r2' in r)

    # --- Analysis 1: no interaction ---

    def test_baby_bp_data_loads(self):
        """BabyBloodPressure.json must be a non-empty list of dicts with expected columns."""
        self.assertIsInstance(self.data, list)
        self.assertGreater(len(self.data), 0)
        self.assertIn('SystolicBlood', self.data[0])
        self.assertIn('AgeInDays', self.data[0])
        self.assertIn('Birthweight', self.data[0])

    def test_run_returns_200(self):
        self.assertEqual(self._run().status_code, 200)

    def test_ageindays_coefficient(self):
        """AgeInDays beta must be 5.888."""
        r = self._direct()
        t = self._term(r, 'AgeInDays')
        self.assertAlmostEqual(t['beta'], 5.888, places=self.PLACES)

    def test_ageindays_confidence_limits(self):
        """AgeInDays 95% CI must be [4.418, 7.357]."""
        r = self._direct()
        t = self._term(r, 'AgeInDays')
        self.assertAlmostEqual(t['lcl'], 4.418, places=self.PLACES)
        self.assertAlmostEqual(t['ucl'], 7.357, places=self.PLACES)

    def test_ageindays_se_and_f(self):
        """AgeInDays SE=0.680, F=74.923."""
        r = self._direct()
        t = self._term(r, 'AgeInDays')
        self.assertAlmostEqual(t['stderror'], 0.680, places=self.PLACES)
        self.assertAlmostEqual(t['ftest'], 74.923, places=self.PLACES)

    def test_ageindays_p_value(self):
        """AgeInDays p-value must be very small (< 0.0001)."""
        r = self._direct()
        t = self._term(r, 'AgeInDays')
        self.assertLess(t['pvalue'], 0.0001)

    def test_birthweight_coefficient(self):
        """Birthweight beta must be 0.126."""
        r = self._direct()
        t = self._term(r, 'Birthweight')
        self.assertAlmostEqual(t['beta'], 0.126, places=self.PLACES)

    def test_birthweight_confidence_limits(self):
        """Birthweight 95% CI must be [0.051, 0.200]."""
        r = self._direct()
        t = self._term(r, 'Birthweight')
        self.assertAlmostEqual(t['lcl'], 0.051, places=self.PLACES)
        self.assertAlmostEqual(t['ucl'], 0.200, places=self.PLACES)

    def test_birthweight_se_and_f(self):
        """Birthweight SE=0.034, F=13.377."""
        r = self._direct()
        t = self._term(r, 'Birthweight')
        self.assertAlmostEqual(t['stderror'], 0.034, places=self.PLACES)
        self.assertAlmostEqual(t['ftest'], 13.377, places=self.PLACES)

    def test_birthweight_p_value(self):
        """Birthweight p-value must be 0.002896 (±0.001)."""
        r = self._direct()
        t = self._term(r, 'Birthweight')
        self.assertAlmostEqual(t['pvalue'], 0.002896, delta=0.001)

    def test_constant_coefficient(self):
        """CONSTANT beta must be 53.450."""
        r = self._direct()
        t = self._term(r, 'CONSTANT')
        self.assertAlmostEqual(t['beta'], 53.450, places=self.PLACES)

    def test_r_squared(self):
        """R² must be 0.88."""
        r = self._direct()
        s = self._stats(r)
        self.assertAlmostEqual(s['r2'], 0.88, places=2)

    def test_anova_regression(self):
        """ANOVA Regression: df=2, SS=591.036, MS=295.518, F=48.081."""
        r = self._direct()
        s = self._stats(r)
        self.assertEqual(s['regressionDF'], 2)
        self.assertAlmostEqual(s['sumOfSquares'], 591.036, places=self.PLACES)
        self.assertAlmostEqual(s['meanSquare'], 295.518, places=self.PLACES)
        self.assertAlmostEqual(s['fStatistic'], 48.081, places=self.PLACES)

    def test_anova_residuals(self):
        """ANOVA Residuals: df=13, SS=79.902, MS=6.146."""
        r = self._direct()
        s = self._stats(r)
        self.assertEqual(s['residualsDF'], 13)
        self.assertAlmostEqual(s['residualsSS'], 79.902, places=self.PLACES)
        self.assertAlmostEqual(s['residualsMS'], 6.146, places=self.PLACES)

    def test_anova_total(self):
        """ANOVA Total: df=15, SS=670.938."""
        r = self._direct()
        s = self._stats(r)
        self.assertEqual(s['totalDF'], 15)
        self.assertAlmostEqual(s['totalSS'], 670.938, places=self.PLACES)

    def test_results_page_shows_coefficients(self):
        """Rendered page must show AgeInDays and Birthweight coefficients (4 dp)."""
        response = self._run()
        self.assertContains(response, '5.8877')   # AgeInDays beta (4 dp)
        self.assertContains(response, '0.1256')   # Birthweight beta (4 dp)

    def test_results_page_shows_r_squared(self):
        """Rendered page must show R² = 0.88."""
        response = self._run()
        self.assertContains(response, '0.88')

    def test_results_page_shows_anova_f(self):
        """Rendered page must show overall F-statistic from ANOVA table."""
        response = self._run()
        self.assertContains(response, '48.08')

    def test_results_page_shows_constant(self):
        """Rendered page must show CONSTANT term with coefficient (4 dp)."""
        response = self._run()
        self.assertContains(response, 'CONSTANT')
        self.assertContains(response, '53.4502')

    # --- Analysis 2: with interaction ---

    def test_interaction_run_returns_200(self):
        self.assertEqual(
            self._run(interactions=['AgeInDays', 'Birthweight']).status_code, 200
        )

    def test_interaction_ageindays_coefficient(self):
        """With interaction, AgeInDays beta must be 21.287."""
        r = self._direct(self.EXPOSURES + ['AgeInDays*Birthweight'])
        t = self._term(r, 'AgeInDays')
        self.assertAlmostEqual(t['beta'], 21.287, places=self.PLACES)

    def test_interaction_birthweight_coefficient(self):
        """With interaction, Birthweight beta must be 0.551."""
        r = self._direct(self.EXPOSURES + ['AgeInDays*Birthweight'])
        t = self._term(r, 'Birthweight')
        self.assertAlmostEqual(t['beta'], 0.551, places=self.PLACES)

    def test_interaction_term_coefficient(self):
        """AgeInDays*Birthweight interaction term beta must be -0.128."""
        r = self._direct(self.EXPOSURES + ['AgeInDays*Birthweight'])
        t = self._term(r, 'AgeInDays*Birthweight')
        self.assertAlmostEqual(t['beta'], -0.128, places=self.PLACES)

    def test_interaction_r_squared(self):
        """R² with interaction must be 0.92."""
        r = self._direct(self.EXPOSURES + ['AgeInDays*Birthweight'])
        s = self._stats(r)
        self.assertAlmostEqual(s['r2'], 0.92, places=2)

    def test_interaction_anova_regression(self):
        """With interaction, ANOVA Regression: df=3, SS=618.183, F=46.873."""
        r = self._direct(self.EXPOSURES + ['AgeInDays*Birthweight'])
        s = self._stats(r)
        self.assertEqual(s['regressionDF'], 3)
        self.assertAlmostEqual(s['sumOfSquares'], 618.183, places=self.PLACES)
        self.assertAlmostEqual(s['fStatistic'], 46.873, places=self.PLACES)

    def test_interaction_anova_residuals(self):
        """With interaction, ANOVA Residuals: df=12, SS=52.754."""
        r = self._direct(self.EXPOSURES + ['AgeInDays*Birthweight'])
        s = self._stats(r)
        self.assertEqual(s['residualsDF'], 12)
        self.assertAlmostEqual(s['residualsSS'], 52.754, places=self.PLACES)

    def test_interaction_results_page_shows_interaction_coefficient(self):
        """Rendered page with interaction must show AgeInDays*Birthweight term."""
        response = self._run(interactions=['AgeInDays', 'Birthweight'])
        self.assertContains(response, 'AgeInDays*Birthweight')
        self.assertContains(response, '-0.128')

    def test_interaction_results_page_shows_r_squared(self):
        """Rendered page with interaction must show R² = 0.92."""
        response = self._run(interactions=['AgeInDays', 'Birthweight'])
        self.assertContains(response, '0.92')

import json
from pathlib import Path
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

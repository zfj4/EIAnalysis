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

    def test_header_title_links_to_index(self):
        """Clicking EIAnalysis in the header must navigate back to the index (file navigator)."""
        response = self.client.get(reverse('core:index'))
        index_url = reverse('core:index')
        self.assertContains(response, f'hx-get="{index_url}"')
        self.assertContains(response, 'EIAnalysis')


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
OSWEGO_DATA_PATH = Path(__file__).resolve().parent.parent / 'sample_data' / 'Oswego.json'


def _load_oswego():
    """Load Oswego.json, repairing the invalid JSON escape in the source file."""
    with open(OSWEGO_DATA_PATH, 'rb') as f:
        raw = f.read()
    # The file contains 'CDC\zfj4' which is an invalid JSON escape sequence.
    # Replace it with 'CDC_zfj4' so json.loads can parse the file.
    return json.loads(raw.replace(rb'CDC\zfj4', b'CDC_zfj4'))


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


# ---------------------------------------------------------------------------
# Shared mocks for Means.Run()
# ---------------------------------------------------------------------------

MOCK_MEANS_RESULT_CROSSTAB = [
    {
        'crosstabVariable': '0',
        'obs': 29.0, 'total': 955.0, 'mean': 32.9310,
        'variance': 423.7094, 'std_dev': 20.5842,
        'min': 7.0, 'q25': 14.0, 'q50': 35.0, 'q75': 50.0, 'max': 69.0, 'mode': 11.0,
    },
    {
        'crosstabVariable': '1',
        'obs': 46.0, 'total': 1806.0, 'mean': 39.2609,
        'variance': 477.2638, 'std_dev': 21.8464,
        'min': 3.0, 'q25': 17.0, 'q50': 38.5, 'q75': 59.0, 'max': 77.0, 'mode': 15.0,
    },
    {
        'meansDiffPooled': -6.3298, 'lclPooled': -16.4290, 'uclPooled': 3.7693,
        'stdDevDiff': 21.3711, 'pooledT': -1.2491, 'pooledDF': 73, 'pooledPT': 0.2156,
        'meansDiffSatterthwaite': -6.3298, 'lclSatterthwaite': -16.3198,
        'uclSatterthwaite': 3.6601, 'SatterthwaiteT': -1.2663,
        'SatterthwaiteDF': 62.33, 'SatterthwaitePT': 0.2101,
    },
    {
        'ssBetween': 712.655, 'dfBetween': 1, 'msBetween': 712.655,
        'fStatistic': 1.5604, 'ssWithin': 33340.732, 'dfWithin': 73.0,
        'msWithin': 456.722, 'ssTotal': 34053.387, 'dfTotal': 74.0,
        'anovaPValue': 0.2156, 'bartlettChiSquare': 0.1193, 'bartlettPValue': 0.7298,
        'kruskalWallisH': 1.1612, 'kruskalWallisDF': 1, 'kruskalPValue': 0.2812,
    },
]

MOCK_MEANS_RESULT_NO_CROSSTAB = [
    {
        'obs': 75.0, 'total': 2761.0, 'mean': 36.8133,
        'variance': 460.1809, 'std_dev': 21.4518,
        'min': 3.0, 'q25': 16.0, 'q50': 36.0, 'q75': 58.0, 'max': 77.0, 'mode': 11.0,
    },
]

MOCK_MEANS_RESULT_THREE_GROUPS = [
    {'crosstabVariable': 'A', 'obs': 10.0, 'total': 100.0, 'mean': 10.0,
     'variance': 1.0, 'std_dev': 1.0, 'min': 5.0, 'q25': 8.0, 'q50': 10.0,
     'q75': 12.0, 'max': 15.0, 'mode': 10.0},
    {'crosstabVariable': 'B', 'obs': 10.0, 'total': 110.0, 'mean': 11.0,
     'variance': 1.0, 'std_dev': 1.0, 'min': 6.0, 'q25': 9.0, 'q50': 11.0,
     'q75': 13.0, 'max': 16.0, 'mode': 11.0},
    {'crosstabVariable': 'C', 'obs': 10.0, 'total': 120.0, 'mean': 12.0,
     'variance': 1.0, 'std_dev': 1.0, 'min': 7.0, 'q25': 10.0, 'q50': 12.0,
     'q75': 14.0, 'max': 17.0, 'mode': 12.0},
    # T-test placeholder (present in epiinfo output even for >2 groups)
    {'meansDiffPooled': 0.0, 'lclPooled': 0.0, 'uclPooled': 0.0, 'stdDevDiff': 1.0,
     'pooledT': 0.0, 'pooledDF': 27, 'pooledPT': 1.0,
     'meansDiffSatterthwaite': 0.0, 'lclSatterthwaite': 0.0, 'uclSatterthwaite': 0.0,
     'SatterthwaiteT': 0.0, 'SatterthwaiteDF': 18.0, 'SatterthwaitePT': 1.0},
    {'ssBetween': 20.0, 'dfBetween': 2, 'msBetween': 10.0, 'fStatistic': 10.0,
     'ssWithin': 27.0, 'dfWithin': 27.0, 'msWithin': 1.0,
     'ssTotal': 47.0, 'dfTotal': 29.0, 'anovaPValue': 0.001,
     'bartlettChiSquare': 0.0, 'bartlettPValue': 1.0,
     'kruskalWallisH': 9.5, 'kruskalWallisDF': 2, 'kruskalPValue': 0.009},
]


# ===========================================================================
# MeansFormViewTests
# ===========================================================================

class MeansFormViewTests(TestCase):
    """TDD tests for the means analysis variable-selection form view."""

    URL = 'core:means_form'

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
        """Must render the means_form partial template."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertTemplateUsed(response, 'core/partials/means_form.html')

    def test_all_columns_in_means_dropdown(self):
        """Every column name from the data must appear in the means-of select."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        for col in ['outcome', 'exposure', 'age']:
            self.assertContains(response, col)

    def test_columns_sorted_alphabetically_case_insensitive(self):
        """Columns must appear in case-insensitive alphabetical order."""
        session = self.client.session
        session['data'] = [{'Zebra': 1, 'apple': 1, 'Mango': 1, 'banana': 1}]
        session.save()
        response = self.client.get(reverse(self.URL))
        content = response.content.decode()
        positions = [content.index(col) for col in ['apple', 'banana', 'Mango', 'Zebra']]
        self.assertEqual(positions, sorted(positions))

    def test_crosstab_dropdown_present(self):
        """Must include a cross-tabulate variable dropdown."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, 'crosstab_variable')

    def test_form_posts_to_run_means_url(self):
        """The form action must point to the run_means endpoint."""
        self._set_session_data()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, reverse('core:run_means'))


# ===========================================================================
# RunMeansViewTests
# ===========================================================================

class RunMeansViewTests(TestCase):
    """TDD tests for the run_means view (calls epiinfo.Means)."""

    URL = 'core:run_means'

    def _set_session_data(self):
        session = self.client.session
        session['data'] = SAMPLE_DATA
        session.save()

    def _run(self, means_var='age', crosstab_var=''):
        return self.client.post(
            reverse(self.URL),
            {'means_variable': means_var, 'crosstab_variable': crosstab_var},
        )

    def test_get_returns_405(self):
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 405)

    def test_requires_session_data(self):
        response = self._run()
        self.assertEqual(response.status_code, 400)

    def test_missing_means_variable_returns_400(self):
        self._set_session_data()
        response = self.client.post(reverse(self.URL), {'means_variable': '', 'crosstab_variable': ''})
        self.assertEqual(response.status_code, 400)

    @patch('core.views.Means')
    def test_valid_run_returns_200(self, MockMeans):
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_NO_CROSSTAB
        self._set_session_data()
        response = self._run()
        self.assertEqual(response.status_code, 200)

    @patch('core.views.Means')
    def test_valid_run_uses_results_template(self, MockMeans):
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_NO_CROSSTAB
        self._set_session_data()
        response = self._run()
        self.assertTemplateUsed(response, 'core/partials/means_results.html')

    @patch('core.views.Means')
    def test_calls_run_with_mean_variable(self, MockMeans):
        """Run() must be called with the correct meanVariable."""
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_NO_CROSSTAB
        self._set_session_data()
        self._run(means_var='age', crosstab_var='')
        call_args = MockMeans.return_value.Run.call_args
        cols = call_args[0][0]
        self.assertEqual(cols.get('meanVariable'), 'age')
        self.assertNotIn('crosstabVariable', cols)

    @patch('core.views.Means')
    def test_calls_run_with_crosstab_variable(self, MockMeans):
        """Run() must include crosstabVariable when provided."""
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_CROSSTAB
        self._set_session_data()
        self._run(means_var='age', crosstab_var='outcome')
        call_args = MockMeans.return_value.Run.call_args
        cols = call_args[0][0]
        self.assertEqual(cols.get('crosstabVariable'), 'outcome')

    @patch('core.views.Means')
    def test_results_contain_mean_value(self, MockMeans):
        """Results must display the mean value from the stats dict."""
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_NO_CROSSTAB
        self._set_session_data()
        response = self._run()
        self.assertContains(response, '36.8133')

    @patch('core.views.Means')
    def test_results_contain_table_element(self, MockMeans):
        """Response HTML must contain a <table> element."""
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_NO_CROSSTAB
        self._set_session_data()
        response = self._run()
        self.assertContains(response, '<table')

    @patch('core.views.Means')
    def test_no_crosstab_hides_anova(self, MockMeans):
        """Without a crosstab variable, the ANOVA section must not appear."""
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_NO_CROSSTAB
        self._set_session_data()
        response = self._run()
        self.assertNotContains(response, 'ANOVA')

    @patch('core.views.Means')
    def test_no_crosstab_hides_ttest(self, MockMeans):
        """Without a crosstab variable, the T-Test section must not appear."""
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_NO_CROSSTAB
        self._set_session_data()
        response = self._run()
        self.assertNotContains(response, 'T-Test')

    @patch('core.views.Means')
    def test_two_groups_shows_ttest(self, MockMeans):
        """With two crosstab groups, the T-Test section must be displayed."""
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_CROSSTAB
        self._set_session_data()
        response = self._run(means_var='age', crosstab_var='outcome')
        self.assertContains(response, 'T-Test')

    @patch('core.views.Means')
    def test_two_groups_shows_anova(self, MockMeans):
        """With two crosstab groups, the ANOVA section must be displayed."""
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_CROSSTAB
        self._set_session_data()
        response = self._run(means_var='age', crosstab_var='outcome')
        self.assertContains(response, 'ANOVA')

    @patch('core.views.Means')
    def test_three_groups_hides_ttest(self, MockMeans):
        """With more than two crosstab groups, the T-Test section must be hidden."""
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_THREE_GROUPS
        self._set_session_data()
        response = self._run(means_var='age', crosstab_var='outcome')
        self.assertNotContains(response, 'T-Test')

    @patch('core.views.Means')
    def test_three_groups_shows_anova(self, MockMeans):
        """With more than two crosstab groups, ANOVA must still be displayed."""
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_THREE_GROUPS
        self._set_session_data()
        response = self._run(means_var='age', crosstab_var='outcome')
        self.assertContains(response, 'ANOVA')

    @patch('core.views.Means')
    def test_crosstab_results_show_group_labels(self, MockMeans):
        """Crosstab results must display each group label."""
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_CROSSTAB
        self._set_session_data()
        response = self._run(means_var='age', crosstab_var='outcome')
        self.assertContains(response, '32.9310')   # group 0 mean
        self.assertContains(response, '39.2609')   # group 1 mean

    @patch('core.views.Means')
    def test_ttest_pooled_values_displayed(self, MockMeans):
        """T-Test pooled row must show mean diff and confidence limits."""
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_CROSSTAB
        self._set_session_data()
        response = self._run(means_var='age', crosstab_var='outcome')
        self.assertContains(response, '-6.3298')
        self.assertContains(response, '-16.4290')
        self.assertContains(response, '3.7693')

    @patch('core.views.Means')
    def test_anova_f_statistic_displayed(self, MockMeans):
        """ANOVA table must display F statistic."""
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_CROSSTAB
        self._set_session_data()
        response = self._run(means_var='age', crosstab_var='outcome')
        self.assertContains(response, '1.5604')

    @patch('core.views.Means')
    def test_kruskal_wallis_displayed(self, MockMeans):
        """Kruskal-Wallis H value must be displayed."""
        MockMeans.return_value.Run.return_value = MOCK_MEANS_RESULT_CROSSTAB
        self._set_session_data()
        response = self._run(means_var='age', crosstab_var='outcome')
        self.assertContains(response, '1.1612')


# ===========================================================================
# MeansIntegrationTests
# ===========================================================================

class MeansIntegrationTests(TestCase):
    """
    Integration test: loads Oswego.json, runs Means against the live epiinfo
    library, and asserts known values from sample_data/Means.html.

    Reference values (Age cross-tabulated by ILL):
      Group 0 (ILL=0): obs=29,  mean=32.9310, std_dev=20.5842
      Group 1 (ILL=1): obs=46,  mean=39.2609, std_dev=21.8464
      T-Test pooled mean diff: -6.3298
      ANOVA F-statistic: 1.5604
      Kruskal-Wallis H: 1.1612
    """

    MEANS_VAR = 'AGE'
    CROSSTAB_VAR = 'ILL'
    PLACES = 4

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data = _load_oswego()

    def _set_session(self):
        session = self.client.session
        session['data'] = self.data
        session.save()

    def _direct(self, crosstab_var=None):
        from epiinfo.Means import Means as EpiMeans
        cols = {'meanVariable': self.MEANS_VAR}
        if crosstab_var:
            cols['crosstabVariable'] = crosstab_var
        return EpiMeans().Run(cols, self.data)

    def test_oswego_data_loads(self):
        """Oswego.json must be a non-empty list of dicts."""
        self.assertIsInstance(self.data, list)
        self.assertGreater(len(self.data), 0)
        self.assertIn('AGE', self.data[0])
        self.assertIn('ILL', self.data[0])

    def test_group0_obs(self):
        """ILL=0 group must have 29 observations."""
        r = self._direct(self.CROSSTAB_VAR)
        self.assertAlmostEqual(r[0]['obs'], 29.0, places=self.PLACES)

    def test_group1_obs(self):
        """ILL=1 group must have 46 observations."""
        r = self._direct(self.CROSSTAB_VAR)
        self.assertAlmostEqual(r[1]['obs'], 46.0, places=self.PLACES)

    def test_group0_mean(self):
        """ILL=0 mean age must be 32.9310."""
        r = self._direct(self.CROSSTAB_VAR)
        self.assertAlmostEqual(r[0]['mean'], 32.9310, places=self.PLACES)

    def test_group1_mean(self):
        """ILL=1 mean age must be 39.2609."""
        r = self._direct(self.CROSSTAB_VAR)
        self.assertAlmostEqual(r[1]['mean'], 39.2609, places=self.PLACES)

    def test_group0_std_dev(self):
        """ILL=0 std dev must be 20.5842."""
        r = self._direct(self.CROSSTAB_VAR)
        self.assertAlmostEqual(r[0]['std_dev'], 20.5842, places=self.PLACES)

    def test_group1_std_dev(self):
        """ILL=1 std dev must be 21.8464."""
        r = self._direct(self.CROSSTAB_VAR)
        self.assertAlmostEqual(r[1]['std_dev'], 21.8464, places=self.PLACES)

    def test_ttest_pooled_mean_diff(self):
        """Pooled mean difference must be -6.3298."""
        r = self._direct(self.CROSSTAB_VAR)
        ttest = r[-2]
        self.assertAlmostEqual(ttest['meansDiffPooled'], -6.3298, places=self.PLACES)

    def test_ttest_pooled_lcl(self):
        """Pooled 95% LCL must be -16.4290."""
        r = self._direct(self.CROSSTAB_VAR)
        ttest = r[-2]
        self.assertAlmostEqual(ttest['lclPooled'], -16.4290, places=self.PLACES)

    def test_anova_f_statistic(self):
        """ANOVA F-statistic must be 1.5604."""
        r = self._direct(self.CROSSTAB_VAR)
        anova = r[-1]
        self.assertAlmostEqual(anova['fStatistic'], 1.5604, places=self.PLACES)

    def test_anova_p_value(self):
        """ANOVA p-value must be 0.2156."""
        r = self._direct(self.CROSSTAB_VAR)
        anova = r[-1]
        self.assertAlmostEqual(anova['anovaPValue'], 0.2156, places=self.PLACES)

    def test_kruskal_wallis_h(self):
        """Kruskal-Wallis H must be 1.1612."""
        r = self._direct(self.CROSSTAB_VAR)
        anova = r[-1]
        self.assertAlmostEqual(anova['kruskalWallisH'], 1.1612, places=self.PLACES)

    def test_bartlett_chi_square(self):
        """Bartlett's chi square must be 0.1193."""
        r = self._direct(self.CROSSTAB_VAR)
        anova = r[-1]
        self.assertAlmostEqual(anova['bartlettChiSquare'], 0.1193, places=self.PLACES)

    def test_run_means_page_returns_200(self):
        """run_means view must return HTTP 200 for Oswego inputs."""
        self._set_session()
        response = self.client.post(
            reverse('core:run_means'),
            {'means_variable': self.MEANS_VAR, 'crosstab_variable': self.CROSSTAB_VAR},
        )
        self.assertEqual(response.status_code, 200)

    def test_page_shows_group0_mean(self):
        """Rendered page must display group 0 mean = 32.9310."""
        self._set_session()
        response = self.client.post(
            reverse('core:run_means'),
            {'means_variable': self.MEANS_VAR, 'crosstab_variable': self.CROSSTAB_VAR},
        )
        self.assertContains(response, '32.9310')

    def test_page_shows_group1_mean(self):
        """Rendered page must display group 1 mean = 39.2609."""
        self._set_session()
        response = self.client.post(
            reverse('core:run_means'),
            {'means_variable': self.MEANS_VAR, 'crosstab_variable': self.CROSSTAB_VAR},
        )
        self.assertContains(response, '39.2609')

    def test_page_shows_anova_f(self):
        """Rendered page must display ANOVA F = 1.5604."""
        self._set_session()
        response = self.client.post(
            reverse('core:run_means'),
            {'means_variable': self.MEANS_VAR, 'crosstab_variable': self.CROSSTAB_VAR},
        )
        self.assertContains(response, '1.5604')

    def test_page_shows_kruskal_h(self):
        """Rendered page must display Kruskal-Wallis H = 1.1612."""
        self._set_session()
        response = self.client.post(
            reverse('core:run_means'),
            {'means_variable': self.MEANS_VAR, 'crosstab_variable': self.CROSSTAB_VAR},
        )
        self.assertContains(response, '1.1612')



# ===========================================================================
# FrequenciesFormViewTests
# ===========================================================================

AGE_WITH_COUNT_PATH = Path(__file__).resolve().parent.parent / 'sample_data' / 'AgeWithCount.json'


def _load_age_with_count():
    with open(AGE_WITH_COUNT_PATH, 'rb') as f:
        raw = f.read()
    return json.loads(raw.replace(rb'CDC\zfj4', b'CDC_zfj4'))


class FrequenciesFormViewTests(TestCase):
    """TDD tests for the GET frequencies_form view."""

    def _set_session(self):
        session = self.client.session
        session['data'] = SAMPLE_DATA
        session.save()

    def test_frequencies_form_returns_200(self):
        """GET frequencies-form must return HTTP 200 when data is loaded."""
        self._set_session()
        response = self.client.get(reverse('core:frequencies_form'))
        self.assertEqual(response.status_code, 200)

    def test_frequencies_form_uses_correct_template(self):
        """GET frequencies-form must render frequencies_form.html partial."""
        self._set_session()
        response = self.client.get(reverse('core:frequencies_form'))
        self.assertTemplateUsed(response, 'core/partials/frequencies_form.html')

    def test_frequencies_form_contains_columns(self):
        """Form must list all columns from the loaded dataset."""
        self._set_session()
        response = self.client.get(reverse('core:frequencies_form'))
        for col in SAMPLE_DATA[0].keys():
            self.assertContains(response, col)

    def test_frequencies_form_contains_freq_variable_select(self):
        """Form must contain a multi-select for frequency variables."""
        self._set_session()
        response = self.client.get(reverse('core:frequencies_form'))
        self.assertContains(response, 'name="freq_variables"')

    def test_frequencies_form_contains_stratify_select(self):
        """Form must contain an optional stratify-by select."""
        self._set_session()
        response = self.client.get(reverse('core:frequencies_form'))
        self.assertContains(response, 'name="stratify_variable"')

    def test_frequencies_form_contains_weight_select(self):
        """Form must contain an optional weight variable select."""
        self._set_session()
        response = self.client.get(reverse('core:frequencies_form'))
        self.assertContains(response, 'name="weight_variable"')

    def test_frequencies_form_without_data_returns_400(self):
        """GET frequencies-form without loaded data must return HTTP 400."""
        response = self.client.get(reverse('core:frequencies_form'))
        self.assertEqual(response.status_code, 400)


# ===========================================================================
# RunFrequenciesViewTests
# ===========================================================================

class RunFrequenciesViewTests(TestCase):
    """TDD tests for the POST run_frequencies view."""

    def _set_session(self):
        session = self.client.session
        session['data'] = SAMPLE_DATA
        session.save()

    def test_run_frequencies_returns_200(self):
        """POST run-frequencies must return HTTP 200."""
        self._set_session()
        response = self.client.post(
            reverse('core:run_frequencies'),
            {'freq_variables': ['exposure']},
        )
        self.assertEqual(response.status_code, 200)

    def test_run_frequencies_uses_results_template(self):
        """POST run-frequencies must render frequencies_results.html."""
        self._set_session()
        response = self.client.post(
            reverse('core:run_frequencies'),
            {'freq_variables': ['exposure']},
        )
        self.assertTemplateUsed(response, 'core/partials/frequencies_results.html')

    def test_run_frequencies_shows_variable_name(self):
        """Results must display the selected frequency variable name."""
        self._set_session()
        response = self.client.post(
            reverse('core:run_frequencies'),
            {'freq_variables': ['exposure']},
        )
        self.assertContains(response, 'exposure')

    def test_run_frequencies_shows_values(self):
        """Results must display the distinct values of the frequency variable."""
        self._set_session()
        response = self.client.post(
            reverse('core:run_frequencies'),
            {'freq_variables': ['outcome']},
        )
        self.assertContains(response, 'Yes')
        self.assertContains(response, 'No')

    def test_run_frequencies_shows_total(self):
        """Results must display the total row."""
        self._set_session()
        response = self.client.post(
            reverse('core:run_frequencies'),
            {'freq_variables': ['exposure']},
        )
        self.assertContains(response, 'Total')

    def test_run_frequencies_shows_confidence_limits(self):
        """Results must display a confidence limits section."""
        self._set_session()
        response = self.client.post(
            reverse('core:run_frequencies'),
            {'freq_variables': ['exposure']},
        )
        self.assertContains(response, 'Conf Limits')

    def test_run_frequencies_without_data_returns_400(self):
        """POST run-frequencies without loaded data must return HTTP 400."""
        response = self.client.post(
            reverse('core:run_frequencies'),
            {'freq_variables': ['exposure']},
        )
        self.assertEqual(response.status_code, 400)

    def test_run_frequencies_without_variables_returns_400(self):
        """POST run-frequencies without freq_variables must return HTTP 400."""
        self._set_session()
        response = self.client.post(reverse('core:run_frequencies'), {})
        self.assertEqual(response.status_code, 400)

    def test_run_frequencies_get_not_allowed(self):
        """GET run-frequencies must return HTTP 405."""
        self._set_session()
        response = self.client.get(reverse('core:run_frequencies'))
        self.assertEqual(response.status_code, 405)

    def test_run_frequencies_stratify_shows_strata(self):
        """Results with stratify variable must show each stratum label."""
        self._set_session()
        response = self.client.post(
            reverse('core:run_frequencies'),
            {'freq_variables': ['exposure'], 'stratify_variable': 'outcome'},
        )
        self.assertContains(response, 'Yes')
        self.assertContains(response, 'No')

    def test_run_frequencies_weight_variable_shown(self):
        """Results with a weight variable must reference the weight variable name."""
        self._set_session()
        response = self.client.post(
            reverse('core:run_frequencies'),
            {'freq_variables': ['outcome'], 'weight_variable': 'age'},
        )
        self.assertContains(response, 'age')


# ===========================================================================
# FrequenciesIntegrationTests
# ===========================================================================

class FrequenciesIntegrationTests(TestCase):
    """
    Integration test: loads AgeWithCount.json, runs Frequencies with
    weightVariable='Count', and asserts every value from
    sample_data/Frequencies.html.

    Reference table (Age; weightVariable=Count; total=85):
      Age | Freq | Pct    | Cum%   | LCL   | UCL
      ----+------+--------+--------+-------+-------
       1  |   5  |  5.88  |  5.88  |  1.94 | 13.20
       2  |  11  | 12.94  | 18.82  |  6.64 | 21.98
       3  |  19  | 22.35  | 41.18  | 14.03 | 32.69
       4  |  17  | 20.00  | 61.18  | 12.10 | 30.08
       5  |  20  | 23.53  | 84.71  | 15.00 | 33.97
       6  |   6  |  7.06  | 91.76  |  2.63 | 14.73
       7  |   3  |  3.53  | 95.29  |  0.73 |  9.97
       8  |   2  |  2.35  | 97.65  |  0.29 |  8.24
       9  |   1  |  1.18  | 98.82  |  0.03 |  6.38
      10  |   1  |  1.18  | 100.00 |  0.03 |  6.38
    """

    FREQ_VAR = 'Age'
    WEIGHT_VAR = 'Count'

    # (age, frequency, percent, cum_percent, lcl, ucl)
    EXPECTED_ROWS = [
        ('1',  5,   5.88,  5.88,   1.94, 13.20),
        ('2',  11, 12.94, 18.82,   6.64, 21.98),
        ('3',  19, 22.35, 41.18,  14.03, 32.69),
        ('4',  17, 20.00, 61.18,  12.10, 30.08),
        ('5',  20, 23.53, 84.71,  15.00, 33.97),
        ('6',   6,  7.06, 91.76,   2.63, 14.73),
        ('7',   3,  3.53, 95.29,   0.73,  9.97),
        ('8',   2,  2.35, 97.65,   0.29,  8.24),
        ('9',   1,  1.18, 98.82,   0.03,  6.38),
        ('10',  1,  1.18, 100.00,  0.03,  6.38),
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data = _load_age_with_count()

    def _set_session(self):
        session = self.client.session
        session['data'] = self.data
        session.save()

    def _run(self, **extra):
        self._set_session()
        return self.client.post(
            reverse('core:run_frequencies'),
            {'freq_variables': [self.FREQ_VAR], 'weight_variable': self.WEIGHT_VAR, **extra},
        )

    def test_total_is_85(self):
        """Weighted total must equal 85."""
        response = self._run()
        self.assertContains(response, '85')

    def test_exact_conf_limits_label(self):
        """Results must show 'Exact 95% Conf Limits' (total=85 < 300)."""
        response = self._run()
        self.assertContains(response, 'Exact 95% Conf Limits')

    def test_weight_variable_label_shown(self):
        """Results must display the weight variable name."""
        response = self._run()
        self.assertContains(response, self.WEIGHT_VAR)

    def test_all_frequencies(self):
        """Every weighted frequency must match sample_data/Frequencies.html."""
        response = self._run()
        for age, freq, _pct, _cum, _lcl, _ucl in self.EXPECTED_ROWS:
            with self.subTest(age=age):
                self.assertContains(response, str(freq))

    def test_all_percents(self):
        """Every percent value must match sample_data/Frequencies.html."""
        response = self._run()
        for age, _freq, pct, _cum, _lcl, _ucl in self.EXPECTED_ROWS:
            with self.subTest(age=age):
                self.assertContains(response, f'{pct:.2f}')

    def test_all_cumulative_percents(self):
        """Every cumulative percent must match sample_data/Frequencies.html."""
        response = self._run()
        for age, _freq, _pct, cum, _lcl, _ucl in self.EXPECTED_ROWS:
            with self.subTest(age=age):
                self.assertContains(response, f'{cum:.2f}')

    def test_all_lcls(self):
        """Every exact 95% LCL must match sample_data/Frequencies.html."""
        response = self._run()
        for age, _freq, _pct, _cum, lcl, _ucl in self.EXPECTED_ROWS:
            with self.subTest(age=age):
                self.assertContains(response, f'{lcl:.2f}')

    def test_all_ucls(self):
        """Every exact 95% UCL must match sample_data/Frequencies.html."""
        response = self._run()
        for age, _freq, _pct, _cum, _lcl, ucl in self.EXPECTED_ROWS:
            with self.subTest(age=age):
                self.assertContains(response, f'{ucl:.2f}')

# ===========================================================================
# Filter test data
# ===========================================================================

FILTER_DATA = [
    {'name': 'Alice', 'age': '30', 'score': '90'},
    {'name': 'Bob',   'age': '25', 'score': '85'},
    {'name': 'Carol', 'age': '',   'score': '70'},
    {'name': 'Dave',  'age': '40', 'score': '80'},
    {'name': 'Eve',   'age': '30', 'score': '95'},
    {'name': 'Frank', 'age': '35', 'score': '75'},
]


# ===========================================================================
# FilterFormViewTests
# ===========================================================================

class FilterFormViewTests(TestCase):

    URL = 'core:filter_form'

    def _set_session(self, filters=None):
        session = self.client.session
        session['data'] = FILTER_DATA
        session['original_data'] = FILTER_DATA
        session['filters'] = filters or []
        session.save()

    def test_requires_session_data(self):
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 400)

    def test_returns_200_with_session_data(self):
        self._set_session()
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        self._set_session()
        response = self.client.get(reverse(self.URL))
        self.assertTemplateUsed(response, 'core/partials/filter_form.html')

    def test_columns_present(self):
        self._set_session()
        response = self.client.get(reverse(self.URL))
        for col in ['name', 'age', 'score']:
            self.assertContains(response, col)

    def test_no_active_filters_shown_when_empty(self):
        self._set_session()
        response = self.client.get(reverse(self.URL))
        self.assertNotContains(response, 'Active Filters')

    def test_active_filters_shown(self):
        self._set_session(filters=[[{
            'variable': 'age', 'operator': 'gt',
            'operator_label': 'greater than', 'value': '25',
        }]])
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, 'Active Filters')
        self.assertContains(response, 'greater than')

    def test_row_count_shown(self):
        self._set_session()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, '6')


# ===========================================================================
# FilterOptionsViewTests
# ===========================================================================

class FilterOptionsViewTests(TestCase):

    URL = 'core:filter_options'

    def _set_session(self):
        session = self.client.session
        session['data'] = FILTER_DATA
        session['original_data'] = FILTER_DATA
        session['filters'] = []
        session.save()

    def test_returns_200(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'variable': 'age'})
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'variable': 'age'})
        self.assertTemplateUsed(response, 'core/partials/filter_options.html')

    def test_numeric_variable_shows_numeric_operators(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'variable': 'age'})
        self.assertContains(response, 'less than')
        self.assertContains(response, 'greater than')

    def test_non_numeric_variable_no_numeric_operators(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'variable': 'name'})
        self.assertNotContains(response, 'less than')
        self.assertNotContains(response, 'greater than')

    def test_all_variables_get_base_operators(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'variable': 'name'})
        self.assertContains(response, 'is missing')
        self.assertContains(response, 'is not missing')
        self.assertContains(response, 'is equal to')
        self.assertContains(response, 'is not equal to')

    def test_empty_variable_returns_empty_body(self):
        self._set_session()
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'is missing')

    def test_options_include_indexed_target(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'variable': 'age', 'index': '2'})
        self.assertContains(response, 'filter-value-area-2')


# ===========================================================================
# FilterValueInputViewTests
# ===========================================================================

class FilterValueInputViewTests(TestCase):

    URL = 'core:filter_value_input'

    def _set_session(self):
        session = self.client.session
        session['data'] = FILTER_DATA
        session['original_data'] = FILTER_DATA
        session['filters'] = []
        session.save()

    def test_is_missing_returns_no_visible_input(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'variable': 'age', 'operator': 'is_missing'})
        self.assertNotContains(response, 'type="text"')
        self.assertNotContains(response, '<select')

    def test_is_not_missing_returns_no_visible_input(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'variable': 'age', 'operator': 'is_not_missing'})
        self.assertNotContains(response, 'type="text"')
        self.assertNotContains(response, '<select')

    def test_eq_few_values_returns_select(self):
        # age has 4 distinct non-empty values - <=5 so select
        self._set_session()
        response = self.client.get(reverse(self.URL), {'variable': 'age', 'operator': 'eq'})
        self.assertContains(response, '<select')

    def test_neq_few_values_returns_select(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'variable': 'age', 'operator': 'neq'})
        self.assertContains(response, '<select')

    def test_eq_many_values_returns_text_input(self):
        # name has 6 distinct values - >5 so text input
        self._set_session()
        response = self.client.get(reverse(self.URL), {'variable': 'name', 'operator': 'eq'})
        self.assertContains(response, 'type="text"')
        self.assertNotContains(response, '<select')

    def test_lt_returns_text_input(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'variable': 'age', 'operator': 'lt'})
        self.assertContains(response, 'type="text"')

    def test_eq_select_contains_values(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'variable': 'age', 'operator': 'eq'})
        self.assertContains(response, '25')
        self.assertContains(response, '30')
        self.assertContains(response, '40')


# ===========================================================================
# RunFilterViewTests
# ===========================================================================

class RunFilterViewTests(TestCase):

    URL = 'core:run_filter'

    def _set_session(self, data=None):
        data = data or FILTER_DATA
        session = self.client.session
        session['data'] = list(data)
        session['original_data'] = list(data)
        session['filters'] = []
        session.save()

    def test_requires_post(self):
        self._set_session()
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 405)

    def test_requires_session_data(self):
        response = self.client.post(reverse(self.URL), {'variable': 'age', 'operator': 'eq', 'value': '30'})
        self.assertEqual(response.status_code, 400)

    def test_is_missing_filter(self):
        self._set_session()
        self.client.post(reverse(self.URL), {'variable': 'age', 'operator': 'is_missing'})
        session = self.client.session
        self.assertEqual(len(session['data']), 1)  # only Carol

    def test_is_not_missing_filter(self):
        self._set_session()
        self.client.post(reverse(self.URL), {'variable': 'age', 'operator': 'is_not_missing'})
        session = self.client.session
        self.assertEqual(len(session['data']), 5)

    def test_eq_filter(self):
        self._set_session()
        self.client.post(reverse(self.URL), {'variable': 'age', 'operator': 'eq', 'value': '30'})
        session = self.client.session
        self.assertEqual(len(session['data']), 2)  # Alice and Eve

    def test_neq_filter_excludes_missing(self):
        self._set_session()
        self.client.post(reverse(self.URL), {'variable': 'age', 'operator': 'neq', 'value': '30'})
        session = self.client.session
        self.assertEqual(len(session['data']), 3)  # Bob, Dave, Frank

    def test_lt_filter(self):
        self._set_session()
        self.client.post(reverse(self.URL), {'variable': 'age', 'operator': 'lt', 'value': '30'})
        session = self.client.session
        self.assertEqual(len(session['data']), 1)  # Bob(25)

    def test_lte_filter(self):
        self._set_session()
        self.client.post(reverse(self.URL), {'variable': 'age', 'operator': 'lte', 'value': '30'})
        session = self.client.session
        self.assertEqual(len(session['data']), 3)  # Bob(25), Alice(30), Eve(30)

    def test_gte_filter(self):
        self._set_session()
        self.client.post(reverse(self.URL), {'variable': 'age', 'operator': 'gte', 'value': '35'})
        session = self.client.session
        self.assertEqual(len(session['data']), 2)  # Dave(40), Frank(35)

    def test_gt_filter(self):
        self._set_session()
        self.client.post(reverse(self.URL), {'variable': 'age', 'operator': 'gt', 'value': '30'})
        session = self.client.session
        self.assertEqual(len(session['data']), 2)  # Dave(40), Frank(35)

    def test_filter_appends_to_session_filters(self):
        self._set_session()
        self.client.post(reverse(self.URL), {'variable': 'age', 'operator': 'gt', 'value': '25'})
        session = self.client.session
        self.assertEqual(len(session['filters']), 1)
        self.assertEqual(session['filters'][0][0]['variable'], 'age')
        self.assertEqual(session['filters'][0][0]['operator'], 'gt')

    def test_filter_shows_operator_label_in_response(self):
        self._set_session()
        response = self.client.post(reverse(self.URL), {'variable': 'age', 'operator': 'gt', 'value': '25'})
        self.assertContains(response, 'greater than')

    def test_filter_shows_variable_in_response(self):
        self._set_session()
        response = self.client.post(reverse(self.URL), {'variable': 'age', 'operator': 'gt', 'value': '25'})
        self.assertContains(response, 'age')

    def test_multiple_filters_are_cumulative(self):
        self._set_session()
        # Filter 1: age >= 30 -> Alice(30), Dave(40), Eve(30), Frank(35) = 4 rows
        self.client.post(reverse(self.URL), {'variable': 'age', 'operator': 'gte', 'value': '30'})
        # Filter 2: age <= 35 -> Alice(30), Eve(30), Frank(35) = 3 rows
        self.client.post(reverse(self.URL), {'variable': 'age', 'operator': 'lte', 'value': '35'})
        session = self.client.session
        self.assertEqual(len(session['data']), 3)
        self.assertEqual(len(session['filters']), 2)


# ===========================================================================
# ClearFiltersViewTests
# ===========================================================================

class ClearFiltersViewTests(TestCase):

    URL = 'core:clear_filters'

    def _set_session(self):
        session = self.client.session
        session['data'] = FILTER_DATA[:3]  # simulate a filtered state
        session['original_data'] = FILTER_DATA
        session['filters'] = [
            [{'variable': 'age', 'operator': 'lt', 'operator_label': 'less than', 'value': '35'}]
        ]
        session.save()

    def test_requires_post(self):
        self._set_session()
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 405)

    def test_requires_session_data(self):
        response = self.client.post(reverse(self.URL))
        self.assertEqual(response.status_code, 400)

    def test_restores_original_data(self):
        self._set_session()
        self.client.post(reverse(self.URL))
        session = self.client.session
        self.assertEqual(len(session['data']), len(FILTER_DATA))

    def test_clears_session_filters(self):
        self._set_session()
        self.client.post(reverse(self.URL))
        session = self.client.session
        self.assertEqual(session['filters'], [])

    def test_shows_full_row_count_in_response(self):
        self._set_session()
        response = self.client.post(reverse(self.URL))
        self.assertContains(response, str(len(FILTER_DATA)))

    def test_response_shows_no_active_filters(self):
        self._set_session()
        response = self.client.post(reverse(self.URL))
        self.assertNotContains(response, 'Active Filters')

# ===========================================================================
# FilterConditionRowViewTests
# ===========================================================================

class FilterConditionRowViewTests(TestCase):

    URL = 'core:filter_condition_row'

    def _set_session(self):
        session = self.client.session
        session['data'] = FILTER_DATA
        session['original_data'] = FILTER_DATA
        session['filters'] = []
        session.save()

    def test_returns_200(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'index': '1'})
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'index': '1'})
        self.assertTemplateUsed(response, 'core/partials/filter_condition_row.html')

    def test_contains_variable_select(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'index': '1'})
        self.assertContains(response, 'name="variable"')

    def test_contains_indexed_dynamic_target(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'index': '2'})
        self.assertContains(response, 'filter-dynamic-2')

    def test_columns_shown(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'index': '1'})
        for col in ['name', 'age', 'score']:
            self.assertContains(response, col)

    def test_or_label_shown_for_non_zero_index(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'index': '1'})
        self.assertContains(response, 'or')


# ===========================================================================
# RunFilterOrTests  (OR conditions within a Filter Definition)
# ===========================================================================

class RunFilterOrTests(TestCase):

    URL = 'core:run_filter'

    def _set_session(self):
        session = self.client.session
        session['data'] = list(FILTER_DATA)
        session['original_data'] = list(FILTER_DATA)
        session['filters'] = []
        session.save()

    def test_or_conditions_match_either_value(self):
        # age eq 25 OR age eq 40 -> Bob(25), Dave(40) = 2 rows
        self._set_session()
        self.client.post(reverse(self.URL), {
            'variable': ['age', 'age'],
            'operator': ['eq', 'eq'],
            'value': ['25', '40'],
        })
        session = self.client.session
        self.assertEqual(len(session['data']), 2)

    def test_or_conditions_include_missing(self):
        # age eq 30 OR age is_missing -> Alice(30), Carol(''), Eve(30) = 3 rows
        self._set_session()
        self.client.post(reverse(self.URL), {
            'variable': ['age', 'age'],
            'operator': ['eq', 'is_missing'],
            'value': ['30', ''],
        })
        session = self.client.session
        self.assertEqual(len(session['data']), 3)

    def test_filter_definition_stored_as_list_of_conditions(self):
        self._set_session()
        self.client.post(reverse(self.URL), {
            'variable': ['age', 'age'],
            'operator': ['eq', 'is_missing'],
            'value': ['30', ''],
        })
        session = self.client.session
        self.assertEqual(len(session['filters']), 1)
        self.assertEqual(len(session['filters'][0]), 2)

    def test_and_logic_between_filter_definitions(self):
        # Filter 1: age >= 30 -> Alice(30), Dave(40), Eve(30), Frank(35) = 4
        # Filter 2: age <= 35 -> Alice(30), Eve(30), Frank(35) = 3
        self._set_session()
        self.client.post(reverse(self.URL), {'variable': ['age'], 'operator': ['gte'], 'value': ['30']})
        self.client.post(reverse(self.URL), {'variable': ['age'], 'operator': ['lte'], 'value': ['35']})
        session = self.client.session
        self.assertEqual(len(session['data']), 3)
        self.assertEqual(len(session['filters']), 2)

    def test_or_response_shows_or_label(self):
        self._set_session()
        response = self.client.post(reverse(self.URL), {
            'variable': ['age', 'age'],
            'operator': ['eq', 'eq'],
            'value': ['25', '40'],
        })
        self.assertContains(response, 'or')


# ===========================================================================
# 0.3.0  Add/Update Variable — unit tests
# ===========================================================================

ADDVAR_DATA = [
    {'name': 'Alice', 'dob': '1/1/1980 12:00:00 AM', 'age': None},
    {'name': 'Bob',   'dob': '6/15/1990 12:00:00 AM', 'age': None},
    {'name': 'Carol', 'dob': None,                     'age': None},
    {'name': 'Dave',  'dob': 'bad-date',               'age': None},
    {'name': 'Eve',   'dob': '3/3/2000 12:00:00 AM',  'age': 5},
]

ADDVAR_END_DATE = '05/05/2012'  # End date literal used in tests


# ---------------------------------------------------------------------------
# AddVarFormViewTests
# ---------------------------------------------------------------------------

class AddVarFormViewTests(TestCase):

    URL = 'core:addvar_form'

    def _set_session(self):
        session = self.client.session
        session['data'] = ADDVAR_DATA
        session['original_data'] = ADDVAR_DATA
        session['filters'] = []
        session.save()

    def test_get_without_data_returns_400(self):
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 400)

    def test_get_with_data_returns_200(self):
        self._set_session()
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        self._set_session()
        response = self.client.get(reverse(self.URL))
        self.assertTemplateUsed(response, 'core/partials/addvar_form.html')

    def test_contains_assignment_type_dropdown(self):
        self._set_session()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, 'name="assignment_type"')

    def test_contains_select_assignment_type_placeholder(self):
        self._set_session()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, 'Select Assignment Type')

    def test_contains_date_diff_option(self):
        self._set_session()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, 'Difference between Two Dates')


# ---------------------------------------------------------------------------
# AddVarTypeViewTests
# ---------------------------------------------------------------------------

class AddVarTypeViewTests(TestCase):

    URL = 'core:addvar_type'

    def _set_session(self):
        session = self.client.session
        session['data'] = ADDVAR_DATA
        session['original_data'] = ADDVAR_DATA
        session['filters'] = []
        session.save()

    def test_date_diff_returns_200(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'assignment_type': 'date_diff'})
        self.assertEqual(response.status_code, 200)

    def test_date_diff_uses_correct_template(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'assignment_type': 'date_diff'})
        self.assertTemplateUsed(response, 'core/partials/addvar_type_date_diff.html')

    def test_date_diff_contains_days_radio(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'assignment_type': 'date_diff'})
        self.assertContains(response, 'value="days"')

    def test_date_diff_contains_months_radio(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'assignment_type': 'date_diff'})
        self.assertContains(response, 'value="months"')

    def test_date_diff_contains_years_radio(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'assignment_type': 'date_diff'})
        self.assertContains(response, 'value="years"')

    def test_date_diff_contains_start_date_variable_select(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'assignment_type': 'date_diff'})
        self.assertContains(response, 'name="start_date_variable"')

    def test_date_diff_contains_end_date_variable_select(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'assignment_type': 'date_diff'})
        self.assertContains(response, 'name="end_date_variable"')

    def test_date_diff_contains_start_date_literal_input(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'assignment_type': 'date_diff'})
        self.assertContains(response, 'name="start_date_literal"')

    def test_date_diff_contains_end_date_literal_input(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'assignment_type': 'date_diff'})
        self.assertContains(response, 'name="end_date_literal"')

    def test_date_diff_contains_column_names(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'assignment_type': 'date_diff'})
        self.assertContains(response, 'dob')

    def test_unknown_type_returns_empty_200(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'assignment_type': 'unknown'})
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# RunAddVarViewTests
# ---------------------------------------------------------------------------

class RunAddVarViewTests(TestCase):

    URL = 'core:run_addvar'

    def _set_session(self, data=None):
        session = self.client.session
        session['data'] = data if data is not None else list(ADDVAR_DATA)
        session['original_data'] = data if data is not None else list(ADDVAR_DATA)
        session['filters'] = []
        session.save()

    def _post(self, **kwargs):
        defaults = {
            'assignment_type': 'date_diff',
            'units': 'years',
            'start_date_variable': 'dob',
            'start_date_literal': '',
            'end_date_variable': '',
            'end_date_literal': ADDVAR_END_DATE,
            'variable_name': 'age',
        }
        defaults.update(kwargs)
        return self.client.post(reverse(self.URL), defaults)

    # --- method guard ---

    def test_get_returns_405(self):
        response = self.client.get(reverse(self.URL))
        self.assertEqual(response.status_code, 405)

    # --- session guard ---

    def test_requires_session_data(self):
        response = self._post()
        self.assertEqual(response.status_code, 400)

    # --- input validation ---

    def test_missing_assignment_type_returns_400(self):
        self._set_session()
        response = self._post(assignment_type='')
        self.assertEqual(response.status_code, 400)

    def test_missing_variable_name_returns_400(self):
        self._set_session()
        response = self._post(variable_name='')
        self.assertEqual(response.status_code, 400)

    def test_date_diff_missing_start_returns_400(self):
        self._set_session()
        response = self._post(start_date_variable='', start_date_literal='')
        self.assertEqual(response.status_code, 400)

    def test_date_diff_missing_end_returns_400(self):
        self._set_session()
        response = self._post(end_date_variable='', end_date_literal='')
        self.assertEqual(response.status_code, 400)

    # --- happy path ---

    def test_valid_run_returns_200(self):
        self._set_session()
        response = self._post()
        self.assertEqual(response.status_code, 200)

    def test_valid_run_uses_status_template(self):
        self._set_session()
        response = self._post()
        self.assertTemplateUsed(response, 'core/partials/addvar_status.html')

    def test_creates_new_variable_in_session(self):
        data = [{'name': 'Alice', 'dob': '1/1/1980 12:00:00 AM'}]
        self._set_session(data)
        self._post(start_date_variable='dob', variable_name='computed_age')
        session = self.client.session
        self.assertIn('computed_age', session['data'][0])

    def test_updates_existing_variable(self):
        data = [{'name': 'Alice', 'dob': '1/1/1980 12:00:00 AM', 'age': 99}]
        self._set_session(data)
        self._post(start_date_variable='dob', variable_name='age')
        session = self.client.session
        # Age should be updated from 99 to the computed value
        self.assertNotEqual(session['data'][0]['age'], 99)

    def test_years_calculation_is_correct(self):
        # Alice born 1/1/1980, end 5/5/2012 -> 32 years
        data = [{'name': 'Alice', 'dob': '1/1/1980 12:00:00 AM'}]
        self._set_session(data)
        self._post(units='years', start_date_variable='dob', variable_name='result')
        session = self.client.session
        self.assertEqual(session['data'][0]['result'], 32)

    def test_months_calculation_is_correct(self):
        # Alice born 1/1/1980, end 5/5/2012 -> 388 months (32*12 + 4)
        data = [{'name': 'Alice', 'dob': '1/1/1980 12:00:00 AM'}]
        self._set_session(data)
        self._post(units='months', start_date_variable='dob', variable_name='result')
        session = self.client.session
        self.assertEqual(session['data'][0]['result'], 388)

    def test_days_calculation_is_correct(self):
        # Alice born 1/1/1980, end 5/5/2012
        from datetime import date
        start = date(1980, 1, 1)
        end = date(2012, 5, 5)
        expected = (end - start).days
        data = [{'name': 'Alice', 'dob': '1/1/1980 12:00:00 AM'}]
        self._set_session(data)
        self._post(units='days', start_date_variable='dob', variable_name='result')
        session = self.client.session
        self.assertEqual(session['data'][0]['result'], expected)

    def test_null_date_value_yields_null(self):
        data = [{'name': 'Carol', 'dob': None}]
        self._set_session(data)
        self._post(start_date_variable='dob', variable_name='result')
        session = self.client.session
        self.assertIsNone(session['data'][0]['result'])

    def test_invalid_date_value_yields_null(self):
        data = [{'name': 'Dave', 'dob': 'not-a-date'}]
        self._set_session(data)
        self._post(start_date_variable='dob', variable_name='result')
        session = self.client.session
        self.assertIsNone(session['data'][0]['result'])

    def test_time_stripped_from_date_values(self):
        # 1/1/2020 11:00 and 1/2/2020 01:00 differ by 1 day not 0
        data = [{'name': 'X', 'start': '1/1/2020 11:00:00 AM', 'end': '1/2/2020 1:00:00 AM'}]
        self._set_session(data)
        self._post(
            units='days',
            start_date_variable='start',
            start_date_literal='',
            end_date_variable='end',
            end_date_literal='',
            variable_name='diff',
        )
        session = self.client.session
        self.assertEqual(session['data'][0]['diff'], 1)

    def test_literal_end_date_applies_to_all_rows(self):
        data = [
            {'dob': '1/1/1980 12:00:00 AM'},
            {'dob': '1/1/1990 12:00:00 AM'},
        ]
        self._set_session(data)
        self._post(
            units='years',
            start_date_variable='dob',
            start_date_literal='',
            end_date_variable='',
            end_date_literal='01/01/2000',
            variable_name='result',
        )
        session = self.client.session
        self.assertEqual(session['data'][0]['result'], 20)
        self.assertEqual(session['data'][1]['result'], 10)

    def test_literal_start_date_applies_to_all_rows(self):
        data = [
            {'end_date': '1/1/2010 12:00:00 AM'},
            {'end_date': '1/1/2020 12:00:00 AM'},
        ]
        self._set_session(data)
        self._post(
            units='years',
            start_date_variable='',
            start_date_literal='01/01/2000',
            end_date_variable='end_date',
            end_date_literal='',
            variable_name='result',
        )
        session = self.client.session
        self.assertEqual(session['data'][0]['result'], 10)
        self.assertEqual(session['data'][1]['result'], 20)

    def test_result_is_rounded_down(self):
        # Born 6/1/1980, end 5/5/2012 -> 31 years (not yet turned 32)
        data = [{'dob': '6/1/1980 12:00:00 AM'}]
        self._set_session(data)
        self._post(units='years', start_date_variable='dob', variable_name='result')
        session = self.client.session
        self.assertEqual(session['data'][0]['result'], 31)

    def test_response_shows_variable_name(self):
        self._set_session()
        response = self._post(variable_name='my_new_var')
        self.assertContains(response, 'my_new_var')

    def test_session_data_is_updated_in_place(self):
        """Other variables in the dataset must remain unchanged."""
        data = [{'name': 'Alice', 'dob': '1/1/1980 12:00:00 AM', 'score': 42}]
        self._set_session(data)
        self._post(start_date_variable='dob', variable_name='age')
        session = self.client.session
        self.assertEqual(session['data'][0]['name'], 'Alice')
        self.assertEqual(session['data'][0]['score'], 42)


# ===========================================================================
# 0.3.0  Add/Update Variable — Salmonellosis integration test
# ===========================================================================

class DateDiffIntegrationTests(TestCase):
    """
    Integration test: loads Salmonellosis.json, runs date diff (DOB → Age,
    end date 05/05/2012, units=years) and verifies against known Age values.

    Only 10 rows have a non-null Age; those 10 should match after the update.
    """

    KNOWN = {
        170: 30,
        178: 41,
        181: 19,
        189: 40,
        219: 44,
        222: 22,
        234: 57,
        252: 36,
        255: 40,
        295: 32,
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(SAMPLE_DATA_PATH) as f:
            cls.original_data = json.load(f)

    def _set_session(self):
        session = self.client.session
        session['data'] = list(self.original_data)
        session['original_data'] = list(self.original_data)
        session['filters'] = []
        session.save()

    def test_date_diff_matches_known_age_values(self):
        """For the 10 rows with known Age, computed age must match."""
        self._set_session()
        self.client.post(reverse('core:run_addvar'), {
            'assignment_type': 'date_diff',
            'units': 'years',
            'start_date_variable': 'DOB',
            'start_date_literal': '',
            'end_date_variable': '',
            'end_date_literal': '05/05/2012',
            'variable_name': 'Age',
        })
        session = self.client.session
        data = session['data']
        for idx, expected_age in self.KNOWN.items():
            with self.subTest(row=idx):
                self.assertEqual(data[idx]['Age'], expected_age)


# ===========================================================================
# 0.3.0.1  Missing-value robustness tests
# ===========================================================================
# All analyses must tolerate rows where the key variables are None/missing.
# The standard approach is list-wise deletion: exclude rows where any variable
# involved in the analysis is null or empty before passing data to epiinfo.
# ===========================================================================

NULL_DATA_BASE = [
    {'outcome': 'Yes', 'exposure': 'High', 'age': '30', 'score': '5.0'},
    {'outcome': 'Yes', 'exposure': 'Low',  'age': '25', 'score': '3.0'},
    {'outcome': 'No',  'exposure': 'High', 'age': '45', 'score': '7.0'},
    {'outcome': 'No',  'exposure': 'Low',  'age': None,  'score': None},
    {'outcome': 'Yes', 'exposure': 'High', 'age': '28', 'score': '4.0'},
    {'outcome': None,  'exposure': 'Low',  'age': '33', 'score': '6.0'},
    {'outcome': 'No',  'exposure': None,   'age': '40', 'score': '8.0'},
]


class MeansNullRobustnessTests(TestCase):
    """Means Analysis must not crash when the means variable contains null values."""

    URL = 'core:run_means'

    def _set_session(self, data):
        session = self.client.session
        session['data'] = data
        session.save()

    def test_means_with_null_means_variable_returns_200(self):
        """run_means must return 200 when the means variable has null values."""
        self._set_session(NULL_DATA_BASE)
        response = self.client.post(reverse(self.URL), {
            'means_variable': 'age',
            'crosstab_variable': '',
        })
        self.assertEqual(response.status_code, 200)

    def test_means_with_null_crosstab_variable_returns_200(self):
        """run_means must return 200 when the crosstab variable has null values."""
        self._set_session(NULL_DATA_BASE)
        response = self.client.post(reverse(self.URL), {
            'means_variable': 'age',
            'crosstab_variable': 'outcome',
        })
        self.assertEqual(response.status_code, 200)

    def test_means_salmonellosis_age_ill_returns_200(self):
        """Means of Age cross-tab by Ill must return 200 on Salmonellosis.json."""
        with open(SAMPLE_DATA_PATH) as f:
            data = json.load(f)
        self._set_session(data)
        response = self.client.post(reverse(self.URL), {
            'means_variable': 'Age',
            'crosstab_variable': 'Ill',
        })
        self.assertEqual(response.status_code, 200)

    def test_means_salmonellosis_uses_results_template(self):
        """Means on Salmonellosis with nulls must render the results template."""
        with open(SAMPLE_DATA_PATH) as f:
            data = json.load(f)
        self._set_session(data)
        response = self.client.post(reverse(self.URL), {
            'means_variable': 'Age',
            'crosstab_variable': 'Ill',
        })
        self.assertTemplateUsed(response, 'core/partials/means_results.html')

    def test_means_salmonellosis_shows_all_10_observations(self):
        """Both crosstab groups must appear; total obs across groups must equal 10."""
        with open(SAMPLE_DATA_PATH) as f:
            data = json.load(f)
        self._set_session(data)
        response = self.client.post(reverse(self.URL), {
            'means_variable': 'Age',
            'crosstab_variable': 'Ill',
        })
        ctx = response.context
        group_stats = ctx['group_stats']
        # Ill=0 has 1 row, Ill=1 has 9 rows → total obs = 10
        total_obs = sum(g['obs'] for g in group_stats)
        self.assertEqual(total_obs, 10)
        self.assertEqual(len(group_stats), 2)


class TablesNullRobustnessTests(TestCase):
    """Tables Analysis must not crash when outcome or exposure variables contain nulls."""

    URL = 'core:run_analysis'

    def _set_session(self, data):
        session = self.client.session
        session['data'] = data
        session.save()

    def test_tables_with_null_outcome_returns_200(self):
        """run_analysis must return 200 when the outcome variable has null values."""
        self._set_session(NULL_DATA_BASE)
        with patch('core.views.TablesAnalysis') as MockTA:
            MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
            response = self.client.post(reverse(self.URL), {
                'outcome_variable': 'outcome',
                'exposure_variables': ['exposure'],
            })
        self.assertEqual(response.status_code, 200)

    def test_tables_with_null_exposure_returns_200(self):
        """run_analysis must return 200 when an exposure variable has null values."""
        self._set_session(NULL_DATA_BASE)
        with patch('core.views.TablesAnalysis') as MockTA:
            MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
            response = self.client.post(reverse(self.URL), {
                'outcome_variable': 'outcome',
                'exposure_variables': ['exposure'],
            })
        self.assertEqual(response.status_code, 200)

    def test_tables_null_rows_excluded_from_epiinfo_call(self):
        """Rows where outcome or exposure is null must be excluded from the data passed to epiinfo."""
        self._set_session(NULL_DATA_BASE)
        with patch('core.views.TablesAnalysis') as MockTA:
            MockTA.return_value.Run.return_value = MOCK_TABLES_RESULT
            self.client.post(reverse(self.URL), {
                'outcome_variable': 'outcome',
                'exposure_variables': ['exposure'],
            })
        call_data = MockTA.return_value.Run.call_args[0][1]
        # Rows with null outcome or null exposure must be excluded
        for row in call_data:
            self.assertIsNotNone(row.get('outcome'))
            self.assertIsNotNone(row.get('exposure'))


class LinearNullRobustnessTests(TestCase):
    """Linear Regression must not crash when outcome or exposure has null values."""

    URL = 'core:run_linear'

    def _set_session(self, data):
        session = self.client.session
        session['data'] = data
        session.save()

    def test_linear_with_null_score_returns_200(self):
        self._set_session(NULL_DATA_BASE)
        with patch('core.views.LinearRegression') as MockLR:
            MockLR.return_value.doRegression.return_value = MOCK_LINEAR_RESULT
            response = self.client.post(reverse(self.URL), {
                'outcome_variable': 'score',
                'exposure_variables': ['age'],
            })
        self.assertEqual(response.status_code, 200)

    def test_linear_null_rows_excluded_from_epiinfo_call(self):
        self._set_session(NULL_DATA_BASE)
        with patch('core.views.LinearRegression') as MockLR:
            MockLR.return_value.doRegression.return_value = MOCK_LINEAR_RESULT
            self.client.post(reverse(self.URL), {
                'outcome_variable': 'score',
                'exposure_variables': ['age'],
            })
        call_data = MockLR.return_value.doRegression.call_args[0][1]
        for row in call_data:
            self.assertIsNotNone(row.get('score'))
            self.assertIsNotNone(row.get('age'))


class LogisticNullRobustnessTests(TestCase):
    """Logistic Regression must not crash when outcome or exposure has null values."""

    URL = 'core:run_logistic'

    def _set_session(self, data):
        session = self.client.session
        session['data'] = data
        session.save()

    def test_logistic_with_nulls_returns_200(self):
        self._set_session(NULL_DATA_BASE)
        with patch('core.views.LogisticRegression') as MockLR:
            MockLR.return_value.doRegression.return_value = MOCK_LOGISTIC_RESULT
            response = self.client.post(reverse(self.URL), {
                'outcome_variable': 'outcome',
                'exposure_variables': ['age'],
            })
        self.assertEqual(response.status_code, 200)

    def test_logistic_null_rows_excluded_from_epiinfo_call(self):
        self._set_session(NULL_DATA_BASE)
        with patch('core.views.LogisticRegression') as MockLR:
            MockLR.return_value.doRegression.return_value = MOCK_LOGISTIC_RESULT
            self.client.post(reverse(self.URL), {
                'outcome_variable': 'outcome',
                'exposure_variables': ['age'],
            })
        call_data = MockLR.return_value.doRegression.call_args[0][1]
        for row in call_data:
            self.assertIsNotNone(row.get('outcome'))
            self.assertIsNotNone(row.get('age'))


class LogBinomialNullRobustnessTests(TestCase):
    """Log-Binomial Regression must not crash when outcome or exposure has null values."""

    URL = 'core:run_logbinomial'

    def _set_session(self, data):
        session = self.client.session
        session['data'] = data
        session.save()

    def test_logbinomial_with_nulls_returns_200(self):
        self._set_session(NULL_DATA_BASE)
        with patch('core.views.LogBinomialRegression') as MockLB:
            MockLB.return_value.doRegression.return_value = MOCK_LOGBINOMIAL_RESULT
            response = self.client.post(reverse(self.URL), {
                'outcome_variable': 'outcome',
                'exposure_variables': ['age'],
            })
        self.assertEqual(response.status_code, 200)

    def test_logbinomial_null_rows_excluded_from_epiinfo_call(self):
        self._set_session(NULL_DATA_BASE)
        with patch('core.views.LogBinomialRegression') as MockLB:
            MockLB.return_value.doRegression.return_value = MOCK_LOGBINOMIAL_RESULT
            self.client.post(reverse(self.URL), {
                'outcome_variable': 'outcome',
                'exposure_variables': ['age'],
            })
        call_data = MockLB.return_value.doRegression.call_args[0][1]
        for row in call_data:
            self.assertIsNotNone(row.get('outcome'))
            self.assertIsNotNone(row.get('age'))


# ===========================================================================
# 0.3.1  Assigned Expression assignment type
# ===========================================================================

EXPR_DATA = [
    {'name': 'Alice', 'score': 10, 'bonus': 5,  'flag': True,  'label': 'yes'},
    {'name': 'Bob',   'score': 20, 'bonus': 3,  'flag': False, 'label': 'no'},
    {'name': 'Carol', 'score': 30, 'bonus': None,'flag': True,  'label': 'yes'},
    {'name': 'Dave',  'score': None,'bonus': 2,  'flag': False, 'label': 'no'},
    {'name': 'Eve',   'score': 15, 'bonus': 4,  'flag': True,  'label': 'yes'},
]


# ---------------------------------------------------------------------------
# AddVarExprTypeViewTests
# ---------------------------------------------------------------------------

class AddVarExprTypeViewTests(TestCase):

    URL = 'core:addvar_type'

    def _set_session(self):
        session = self.client.session
        session['data'] = EXPR_DATA
        session.save()

    def test_expr_type_returns_200(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'assignment_type': 'expr'})
        self.assertEqual(response.status_code, 200)

    def test_expr_type_uses_correct_template(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'assignment_type': 'expr'})
        self.assertTemplateUsed(response, 'core/partials/addvar_type_expr.html')

    def test_expr_type_contains_expression_input(self):
        self._set_session()
        response = self.client.get(reverse(self.URL), {'assignment_type': 'expr'})
        self.assertContains(response, 'name="expression"')


# ---------------------------------------------------------------------------
# AddVarFormExprOptionTests
# ---------------------------------------------------------------------------

class AddVarFormExprOptionTests(TestCase):

    URL = 'core:addvar_form'

    def _set_session(self):
        session = self.client.session
        session['data'] = EXPR_DATA
        session.save()

    def test_assigned_expression_option_present(self):
        self._set_session()
        response = self.client.get(reverse(self.URL))
        self.assertContains(response, 'Assigned Expression')

    def test_assigned_expression_above_date_diff(self):
        """'Assigned Expression' must appear before 'Difference between Two Dates'."""
        self._set_session()
        response = self.client.get(reverse(self.URL))
        content = response.content.decode()
        idx_expr = content.find('Assigned Expression')
        idx_date = content.find('Difference between Two Dates')
        self.assertLess(idx_expr, idx_date)


# ---------------------------------------------------------------------------
# RunAddVarExprTests
# ---------------------------------------------------------------------------

class RunAddVarExprTests(TestCase):

    URL = 'core:run_addvar'

    def _set_session(self, data=None):
        session = self.client.session
        session['data'] = data if data is not None else list(EXPR_DATA)
        session['original_data'] = data if data is not None else list(EXPR_DATA)
        session['filters'] = []
        session.save()

    def _post(self, expression, variable_name='result'):
        return self.client.post(reverse(self.URL), {
            'assignment_type': 'expr',
            'expression': expression,
            'variable_name': variable_name,
        })

    # --- method/session guards ---

    def test_missing_expression_returns_400(self):
        self._set_session()
        response = self.client.post(reverse(self.URL), {
            'assignment_type': 'expr',
            'expression': '',
            'variable_name': 'result',
        })
        self.assertEqual(response.status_code, 400)

    def test_valid_run_returns_200(self):
        self._set_session()
        response = self._post('score + bonus')
        self.assertEqual(response.status_code, 200)

    def test_valid_run_uses_status_template(self):
        self._set_session()
        response = self._post('score + bonus')
        self.assertTemplateUsed(response, 'core/partials/addvar_status.html')

    # --- arithmetic expressions ---

    def test_arithmetic_addition(self):
        self._set_session()
        self._post('score + bonus')
        session = self.client.session
        # Alice: 10+5=15, Bob: 20+3=23
        self.assertEqual(session['data'][0]['result'], 15)
        self.assertEqual(session['data'][1]['result'], 23)

    def test_arithmetic_subtraction(self):
        self._set_session()
        self._post('score - bonus')
        session = self.client.session
        self.assertEqual(session['data'][0]['result'], 5)   # 10-5
        self.assertEqual(session['data'][1]['result'], 17)  # 20-3

    def test_arithmetic_multiplication(self):
        self._set_session()
        self._post('score * bonus')
        session = self.client.session
        self.assertEqual(session['data'][0]['result'], 50)  # 10*5

    def test_arithmetic_division(self):
        self._set_session()
        self._post('score / bonus')
        session = self.client.session
        self.assertAlmostEqual(session['data'][0]['result'], 2.0)  # 10/5

    def test_arithmetic_with_literal(self):
        self._set_session()
        self._post('score + 100')
        session = self.client.session
        self.assertEqual(session['data'][0]['result'], 110)  # 10+100

    def test_arithmetic_with_parens(self):
        self._set_session()
        self._post('(score + bonus) * 2')
        session = self.client.session
        self.assertEqual(session['data'][0]['result'], 30)  # (10+5)*2

    # --- logical expressions ---

    def test_logical_equality(self):
        self._set_session()
        self._post('flag = True')
        session = self.client.session
        self.assertTrue(session['data'][0]['result'])   # Alice: flag=True
        self.assertFalse(session['data'][1]['result'])  # Bob: flag=False

    def test_logical_inequality(self):
        self._set_session()
        self._post('flag != True')
        session = self.client.session
        self.assertFalse(session['data'][0]['result'])  # Alice: flag=True, so flag!=True is False
        self.assertTrue(session['data'][1]['result'])   # Bob: flag=False, so flag!=True is True

    def test_logical_or(self):
        self._set_session()
        self._post('score > 15 OR bonus > 4')
        session = self.client.session
        # Alice: score=10>15=F, bonus=5>4=T → OR → True
        self.assertTrue(session['data'][0]['result'])
        # Bob: score=20>15=T → True
        self.assertTrue(session['data'][1]['result'])

    def test_logical_and(self):
        self._set_session()
        self._post('score > 5 AND bonus > 4')
        session = self.client.session
        self.assertTrue(session['data'][0]['result'])   # Alice: 10>5=T, 5>4=T → T
        self.assertFalse(session['data'][1]['result'])  # Bob: 20>5=T, 3>4=F → F

    def test_logical_not(self):
        self._set_session()
        self._post('NOT flag')
        session = self.client.session
        self.assertFalse(session['data'][0]['result'])  # NOT True = False
        self.assertTrue(session['data'][1]['result'])   # NOT False = True

    def test_logical_comparison_lt(self):
        self._set_session()
        self._post('score < 20')
        session = self.client.session
        self.assertTrue(session['data'][0]['result'])   # 10 < 20
        self.assertFalse(session['data'][1]['result'])  # 20 < 20

    def test_logical_comparison_lte(self):
        self._set_session()
        self._post('score <= 20')
        session = self.client.session
        self.assertTrue(session['data'][1]['result'])   # 20 <= 20

    def test_logical_comparison_gte(self):
        self._set_session()
        self._post('score >= 20')
        session = self.client.session
        self.assertFalse(session['data'][0]['result'])  # 10 >= 20 → False
        self.assertTrue(session['data'][1]['result'])   # 20 >= 20 → True

    def test_string_equality(self):
        self._set_session()
        self._post("label = 'yes'")
        session = self.client.session
        self.assertTrue(session['data'][0]['result'])   # 'yes' = 'yes'
        self.assertFalse(session['data'][1]['result'])  # 'no' = 'yes'

    # --- null/error handling ---

    def test_null_operand_yields_null(self):
        """When a variable is None, arithmetic fails and result is None."""
        self._set_session()
        self._post('score + bonus')
        session = self.client.session
        # Carol: score=30, bonus=None → None
        self.assertIsNone(session['data'][2]['result'])
        # Dave: score=None, bonus=2 → None
        self.assertIsNone(session['data'][3]['result'])

    def test_invalid_expression_yields_null_per_row(self):
        """A syntactically invalid expression yields None for every row."""
        self._set_session()
        self._post('score +* bonus')
        session = self.client.session
        for row in session['data']:
            self.assertIsNone(row['result'])

    def test_unknown_variable_yields_null(self):
        """A variable not in the dataset yields None for every row."""
        self._set_session()
        self._post('nonexistent_variable + 1')
        session = self.client.session
        for row in session['data']:
            self.assertIsNone(row['result'])

    def test_creates_new_variable(self):
        self._set_session()
        self._post('score * 2', variable_name='doubled_score')
        session = self.client.session
        self.assertIn('doubled_score', session['data'][0])

    def test_updates_existing_variable(self):
        self._set_session()
        original = list(EXPR_DATA)
        original[0] = dict(original[0])
        original[0]['score'] = 999
        self._set_session(original)
        self._post('bonus * 2', variable_name='score')
        session = self.client.session
        self.assertEqual(session['data'][0]['score'], 10)   # 5*2


# ---------------------------------------------------------------------------
# AteEggsIntegrationTest
# ---------------------------------------------------------------------------

class AteEggsIntegrationTest(TestCase):
    """
    Integration test: load Salmonellosis.json, compute AteEggs using
    'ChefSalad = True OR EggSaladSandwich = True', verify counts.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(SAMPLE_DATA_PATH) as f:
            cls.data = json.load(f)

    def _set_session(self):
        session = self.client.session
        session['data'] = list(self.data)
        session['original_data'] = list(self.data)
        session['filters'] = []
        session.save()

    def test_ate_eggs_true_count(self):
        """AteEggs True count must equal rows where ChefSalad=True OR EggSaladSandwich=True."""
        self._set_session()
        self.client.post(reverse('core:run_addvar'), {
            'assignment_type': 'expr',
            'expression': 'ChefSalad = True OR EggSaladSandwich = True',
            'variable_name': 'AteEggs',
        })
        session = self.client.session
        data = session['data']
        ate_eggs_true = sum(1 for r in data if r.get('AteEggs') is True)
        ate_eggs_false = sum(1 for r in data if r.get('AteEggs') is False)
        expected_true = sum(1 for r in self.data
                            if r.get('ChefSalad') is True or r.get('EggSaladSandwich') is True)
        expected_false = len(self.data) - expected_true
        self.assertEqual(ate_eggs_true, expected_true)
        self.assertEqual(ate_eggs_false, expected_false)

    def test_ate_eggs_no_nulls(self):
        """AteEggs must have no null values since ChefSalad/EggSaladSandwich have no nulls."""
        self._set_session()
        self.client.post(reverse('core:run_addvar'), {
            'assignment_type': 'expr',
            'expression': 'ChefSalad = True OR EggSaladSandwich = True',
            'variable_name': 'AteEggs',
        })
        session = self.client.session
        nulls = sum(1 for r in session['data'] if r.get('AteEggs') is None)
        self.assertEqual(nulls, 0)

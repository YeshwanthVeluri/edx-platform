"""
Tests for safe_template_checker.py
"""
from ddt import ddt, data
import textwrap
from unittest import TestCase

from ..safe_template_checker import (
    FileResults, MakoTemplateChecker, Rules
)

@ddt
class TestMakoTemplateChecker(TestCase):
    """
    Test MakoTemplateChecker
    """

    @data(
        {'directory': 'lms/templates', 'expected': True},
        {'directory': 'lms/templates/support', 'expected': True},
        {'directory': 'lms/templates/support', 'expected': True},
        {'directory': './test_root/staticfiles/templates', 'expected': False},
        {'directory': './some/random/path', 'expected': False},
    )
    def test_is_mako_directory(self, data):
        """
        Test _is_mako_directory correctly determines mako directories
        """
        checker = MakoTemplateChecker()

        self.assertEqual(checker._is_mako_directory(data['directory']), data['expected'])

    def test_check_page_default_with_default_provided(self):
        """
        Test _check_mako_file_is_safe with default causes no error
        """
        checker = MakoTemplateChecker()
        results = FileResults('')
        mako_template = """
            <%page expression_filter="h"/>
        """

        checker._check_mako_file_is_safe(mako_template, results)

        self.assertEqual(len(results.errors), 0)

    def test_check_page_default_with_no_default_provided(self):
        """
        Test _check_mako_file_is_safe with no default causes error
        """
        checker = MakoTemplateChecker()
        results = FileResults('')
        mako_template = ""

        checker._check_mako_file_is_safe(mako_template, results)

        self.assertEqual(len(results.errors), 1)
        self.assertEqual(results.errors[0].rule, Rules.mako_missing_default)

    def test_check_mako_expressions_in_html(self):
        """
        Test _check_mako_file_is_safe in html context provides appropriate errors
        """
        checker = MakoTemplateChecker()
        results = FileResults('')

        mako_template = textwrap.dedent("""
            <%page expression_filter="h"/>
            ${x}
            ${'{{unbalanced-nested'}
            ${x | n}
            ${x | h}
            ${x | n, dump_html_escaped_json}
            ${x | n, dump_js_escaped_json}
        """)

        checker._check_mako_file_is_safe(mako_template, results)

        self.assertEqual(len(results.errors), 4)
        self.assertEqual(results.errors[0].rule, Rules.mako_unparsable_expression)
        start_index = results.errors[0].expression['start_index']
        self.assertEqual(mako_template[start_index:start_index + 24], "${'{{unbalanced-nested'}")
        self.assertEqual(results.errors[1].rule, Rules.mako_invalid_html_filter)
        self.assertEqual(results.errors[1].expression['expression'], "${x | n}")
        self.assertEqual(results.errors[2].rule, Rules.mako_unwanted_html_filter)
        self.assertEqual(results.errors[2].expression['expression'], "${x | h}")
        self.assertEqual(results.errors[3].rule, Rules.mako_invalid_html_filter)
        self.assertEqual(results.errors[3].expression['expression'], "${x | n, dump_js_escaped_json}")

    def test_check_mako_expressions_in_html_without_default(self):
        """
        Test _check_mako_file_is_safe in html context without the page level
        default h filter suppresses expression level error
        """
        checker = MakoTemplateChecker()
        results = FileResults('')

        mako_template = textwrap.dedent("""
            ${x | h}
        """)

        checker._check_mako_file_is_safe(mako_template, results)

        self.assertEqual(len(results.errors), 1)
        self.assertEqual(results.errors[0].rule, Rules.mako_missing_default)

    def test_check_mako_expressions_in_javascript(self):
        """
        Test _check_mako_file_is_safe in JavaScript script context provides
        appropriate errors
        """
        checker = MakoTemplateChecker()
        results = FileResults('')

        mako_template = textwrap.dedent("""
            <%page expression_filter="h"/>
            <script>
                ${x}
                ${'{{unbalanced-nested'}
                ${x | n}
                ${x | h}
                ${x | n, dump_html_escaped_json}
                ${x | n, dump_js_escaped_json}
                "${x-with-quotes | n, js_escaped_string}"
                '${x-with-quotes | n, js_escaped_string}'
                ${x-missing-quotes | n, js_escaped_string}
            </script>
        """)

        checker._check_mako_file_is_safe(mako_template, results)

        self.assertEqual(len(results.errors), 6)
        self.assertEqual(results.errors[0].rule, Rules.mako_invalid_js_filter)
        self.assertEqual(results.errors[0].expression['expression'], "${x}")
        self.assertEqual(results.errors[1].rule, Rules.mako_unparsable_expression)
        start_index = results.errors[1].expression['start_index']
        self.assertEqual(mako_template[start_index:start_index + 24], "${'{{unbalanced-nested'}")
        self.assertEqual(results.errors[2].rule, Rules.mako_invalid_js_filter)
        self.assertEqual(results.errors[2].expression['expression'], "${x | n}")
        self.assertEqual(results.errors[3].rule, Rules.mako_invalid_js_filter)
        self.assertEqual(results.errors[3].expression['expression'], "${x | h}")
        self.assertEqual(results.errors[4].rule, Rules.mako_invalid_js_filter)
        self.assertEqual(results.errors[4].expression['expression'], "${x | n, dump_html_escaped_json}")
        self.assertEqual(results.errors[5].rule, Rules.mako_js_string_missing_quotes)
        self.assertEqual(results.errors[5].expression['expression'], "${x-missing-quotes | n, js_escaped_string}")

    def test_check_mako_expressions_in_require_js(self):
        """
        Test _check_mako_file_is_safe in JavaScript require context provides
        appropriate errors
        """
        checker = MakoTemplateChecker()
        results = FileResults('')

        mako_template = textwrap.dedent("""
            <%page expression_filter="h"/>
            <%static:require_module module_name="${x}" class_name="TestFactory">
                ${x}
                ${x | n, js_escaped_string}
            </%static:require_module>
        """)

        checker._check_mako_file_is_safe(mako_template, results)

        self.assertEqual(len(results.errors), 2)
        self.assertEqual(results.errors[0].rule, Rules.mako_invalid_js_filter)
        self.assertEqual(results.errors[0].expression['expression'], "${x}")
        self.assertEqual(results.errors[1].rule, Rules.mako_js_string_missing_quotes)
        self.assertEqual(results.errors[1].expression['expression'], "${x | n, js_escaped_string}")

    @data(
        {'media_type': 'text/javascript', 'expected_errors': 0},
        {'media_type': 'text/ecmascript', 'expected_errors': 0},
        {'media_type': 'application/ecmascript', 'expected_errors': 0},
        {'media_type': 'application/javascript', 'expected_errors': 0},
        {'media_type': 'text/template', 'expected_errors': 1},
        {'media_type': 'unknown/type', 'expected_errors': 1},
    )
    def test_check_mako_expressions_in_script_type(self, data):
        """
        Test _check_mako_file_is_safe in script tag with different media types
        """
        checker = MakoTemplateChecker()
        results = FileResults('')

        mako_template = textwrap.dedent("""
            <%page expression_filter="h"/>
            <script type="{}">
                ${{x | n, dump_js_escaped_json}}
            </script>
        """).format(data['media_type'])

        checker._check_mako_file_is_safe(mako_template, results)

        self.assertEqual(len(results.errors), data['expected_errors'])

    def test_check_mako_expressions_in_mixed_contexts(self):
        """
        Test _check_mako_file_is_safe in mixed contexts provides
        appropriate errors
        """
        checker = MakoTemplateChecker()
        results = FileResults('')

        mako_template = textwrap.dedent("""
            <%page expression_filter="h"/>
            ${x | h}
            <script type="text/javascript">
                ${x | h}
            </script>
            ${x | h}
            <%static:require_module module_name="${x}" class_name="TestFactory">
                ${x | h}
            </%static:require_module>
            ${x | h}
        """)

        checker._check_mako_file_is_safe(mako_template, results)

        self.assertEqual(len(results.errors), 5)
        self.assertEqual(results.errors[0].rule, Rules.mako_unwanted_html_filter)
        self.assertEqual(results.errors[1].rule, Rules.mako_invalid_js_filter)
        self.assertEqual(results.errors[2].rule, Rules.mako_unwanted_html_filter)
        self.assertEqual(results.errors[3].rule, Rules.mako_invalid_js_filter)
        self.assertEqual(results.errors[4].rule, Rules.mako_unwanted_html_filter)

    def test_expression_detailed_results(self):
        """
        Test _check_mako_file_is_safe provides detailed results, including line
        numbers, columns, and line
        """
        checker = MakoTemplateChecker()
        results = FileResults('')

        mako_template = textwrap.dedent("""
            ${x | n}
                <div>${(
                    'tabbed-multi-line-expression'
                ) | n}</div>
            ${'{{unbalanced-nested' | n}
        """)

        checker._check_mako_file_is_safe(mako_template, results)

        self.assertEqual(len(results.errors), 4)
        self.assertEqual(results.errors[0].rule, Rules.mako_missing_default)

        self.assertEqual(results.errors[1].start_line, 2)
        self.assertEqual(results.errors[1].start_column, 1)
        self.assertEqual(results.errors[1].end_line, 2)
        self.assertEqual(results.errors[1].end_column, 8)
        self.assertEqual(len(results.errors[1].lines), 1)
        self.assertEqual(results.errors[1].lines[0], "${x | n}")

        self.assertEqual(results.errors[2].start_line, 3)
        self.assertEqual(results.errors[2].start_column, 10)
        self.assertEqual(results.errors[2].end_line, 5)
        self.assertEqual(results.errors[2].end_column, 10)
        self.assertEqual(len(results.errors[2].lines), 3)
        self.assertEqual(results.errors[2].lines[0], "    <div>${(")
        self.assertEqual(results.errors[2].lines[1],
            "        'tabbed-multi-line-expression'"
        )
        self.assertEqual(results.errors[2].lines[2], "    ) | n}</div>")

        self.assertEqual(results.errors[3].start_line, 6)
        self.assertEqual(results.errors[3].start_column, 1)
        self.assertEqual(results.errors[3].end_line, 6)
        self.assertEqual(results.errors[3].end_column, "?")
        self.assertEqual(len(results.errors[3].lines), 1)
        self.assertEqual(results.errors[3].lines[0],
            "${'{{unbalanced-nested' | n}"
        )


    def test_find_mako_expressions(self):
        """
        Test _find_mako_expressions finds appropriate expressions
        """
        checker = MakoTemplateChecker()

        mako_template = textwrap.dedent("""
            ${x}
                ${tabbed-x}
                ${(
                    'tabbed-multi-line-expression'
                )}
            ${'{{unbalanced-nested'}
            ${'{{nested}}'}
                <div>no expression</div>
        """)

        expressions = checker._find_mako_expressions(mako_template)

        self.assertEqual(len(expressions), 5)
        self._validate_expression(mako_template, expressions[0], '${x}')
        self._validate_expression(mako_template, expressions[1], '${tabbed-x}')
        self._validate_expression(mako_template, expressions[2], "${(\n        'tabbed-multi-line-expression'\n    )}")

        # won't parse unbalanced nested {}'s
        unbalanced_expression = "${'{{unbalanced-nested'}"
        self.assertEqual(expressions[3]['end_index'], -1)
        start_index = expressions[3]['start_index']
        self.assertEqual(mako_template[start_index:start_index + len(unbalanced_expression)], unbalanced_expression)
        self.assertEqual(expressions[3]['expression'], None)

        self._validate_expression(mako_template, expressions[4], "${'{{nested}}'}")

    def _validate_expression(self, template_string, expression, expected_expression):
        start_index = expression['start_index']
        end_index = expression['end_index']
        self.assertEqual(template_string[start_index:end_index + 1], expected_expression)
        self.assertEqual(expression['expression'], expected_expression)

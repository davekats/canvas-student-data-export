import unittest

from export import _get_courses_to_export, _student_enrollments_only


class RecordingCanvas:
    def __init__(self):
        self.calls = []

    def get_courses(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs


class StudentEnrollmentsOnlyConfigTests(unittest.TestCase):
    def test_defaults_to_false_when_setting_is_absent(self):
        self.assertFalse(_student_enrollments_only({}))

    def test_accepts_yaml_booleans(self):
        self.assertTrue(_student_enrollments_only({"STUDENT_ENROLLMENTS_ONLY": True}))
        self.assertFalse(_student_enrollments_only({"STUDENT_ENROLLMENTS_ONLY": False}))

    def test_rejects_non_boolean_values(self):
        for value in ("true", "false", 1, None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValueError, "STUDENT_ENROLLMENTS_ONLY must be true or false"
                ):
                    _student_enrollments_only({"STUDENT_ENROLLMENTS_ONLY": value})


class CourseSelectionTests(unittest.TestCase):
    def test_default_query_preserves_all_enrollment_types(self):
        canvas = RecordingCanvas()

        _get_courses_to_export(canvas, student_enrollments_only=False)

        self.assertEqual(
            canvas.calls,
            [
                {"enrollment_state": "active", "include": ["term"]},
                {"enrollment_state": "completed", "include": ["term"]},
            ],
        )

    def test_student_only_query_filters_both_enrollment_states(self):
        canvas = RecordingCanvas()

        _get_courses_to_export(canvas, student_enrollments_only=True)

        self.assertEqual(
            canvas.calls,
            [
                {
                    "enrollment_state": "active",
                    "include": ["term"],
                    "enrollment_type": "student",
                },
                {
                    "enrollment_state": "completed",
                    "include": ["term"],
                    "enrollment_type": "student",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()

from betty.error import ContextError
from betty.tests import TestCase


class ContextErrorTest(TestCase):
    def test__str__(self):
        message = 'Something went wrong!'
        context = 'Somewhere, at some point...'
        expected = 'Something went wrong!\n- Somewhere, at some point...'
        sut = ContextError(message)
        sut.add_context(context)
        self.assertEqual(expected, str(sut))

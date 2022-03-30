import json as stdjson
from pathlib import Path

import jsonschema
from parameterized import parameterized

from betty.asyncio import sync
from betty.openapi import build_specification
from betty.app import App
from betty.tests import TestCase


class BuildSpecificationTest(TestCase):
    @parameterized.expand([
        (True,),
        (False,),
    ])
    @sync
    async def test(self, content_negotiation: str):
        with open(Path(__file__).parent / 'test_openapi_assets' / 'schema.json') as f:
            schema = stdjson.load(f)
            async with App() as app:
                app.project.configuration.content_negotiation = content_negotiation
                specification = build_specification(app)
        jsonschema.validate(specification, schema)

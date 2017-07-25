"""Provides highdim concept ETL for tranSMART."""

import logging

from pandas import DataFrame

from fractalis.data.etl import ETL
from fractalis.data.etls.transmart.shared import extract_data

logger = logging.getLogger(__name__)


class HighdimETL(ETL):
    """HighdimETL implements support for tranSMARTs 'highdim' type."""

    name = 'transmart_highdim_etl'
    produces = 'highdim'

    @staticmethod
    def can_handle(handler: str, descriptor: dict) -> bool:
        return handler == 'transmart' and descriptor['data_type'] == 'highdim'

    def extract(self, server: str, token: str, descriptor: dict) -> dict:
        return extract_data(server=server, descriptor=descriptor, token=token)

    def transform(self, raw_data: dict, descriptor: dict) -> DataFrame:
        rows = []
        for entry in raw_data['cells']:
            idx = entry['dimensionIndexes'][2]
            id = raw_data['dimensionElements']['patient'][idx]['inTrialId']
            value = entry['numericValue']
            rows.append([id, value])
        df = DataFrame(rows, columns=['id', 'value'])
        return df
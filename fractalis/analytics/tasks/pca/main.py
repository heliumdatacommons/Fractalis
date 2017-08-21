"""Module containing analysis code for pca."""

from typing import List, TypeVar
from functools import reduce
import logging

import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import Imputer

from fractalis.analytics.task import AnalyticTask
from fractalis.analytics.tasks.shared import utils


T = TypeVar('T')
logger = logging.getLogger(__name__)


class PCATask(AnalyticTask):
    """PCATask implementing AnalyticsTask. This class is a
    submittable celery task."""

    name = 'compute-pca'

    def main(self,
             features: List[pd.DataFrame],
             categories: List[pd.DataFrame],
             n_components: int,
             whiten: bool,
             id_filter: List[T],
             subsets: List[List[T]]) -> dict:
        # merge input data into single df
        df = reduce(lambda a, b: a.append(b), features)
        if not subsets:
            # empty subsets equals all samples in one subset
            subsets = [df['id'].unique().tolist()]

        # make matrix of data
        df = df.pivot(index='feature', columns='id', values='value')
        df = df.T

        # save ids so we can re-assign them after pca
        ids = df.index.tolist()

        # replace missing values with row medians
        imp = Imputer(missing_values='NaN', strategy='median', axis=0)
        imp.fit(df)
        df = imp.transform(df)

        # PCA
        pca = PCA(n_components=n_components, whiten=whiten)
        pca.fit(df)
        reduced_df = pca.transform(df)

        # re-assign ids
        reduced_df = pd.DataFrame(reduced_df)
        reduced_df['id'] = ids

        # add category and subset column
        reduced_df = utils.apply_subsets(df=reduced_df, subsets=subsets)
        reduced_df = utils.apply_categories(df=reduced_df,
                                            categories=categories)

        return {
            'data': reduced_df.to_json(orient='records')
        }
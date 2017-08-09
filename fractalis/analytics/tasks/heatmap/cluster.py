"""This module provides clustering algorithm for array type data."""

import logging
from typing import List, Tuple
from collections import Counter

import pandas as pd
import numpy as np
from scipy.cluster import hierarchy as hclust
from scipy.cluster.vq import kmeans2

from fractalis.analytics.task import AnalyticTask


logger = logging.getLogger(__name__)


class ClusteringTask(AnalyticTask):

    name = 'compute-clustering'

    def main(self, df: str, cluster_algo: str,
             options: dict) -> dict:
        try:
            df = pd.read_json(df)
        except Exception:
            error = "Failed to parse string to data frame."
            logger.error(error)
            raise ValueError(error)
        # fill NAs with col medians so the clustering algorithms will work
        df = df.T.fillna(df.median(axis=1)).T
        if cluster_algo == 'hclust':
            return self.hclust(df, options)
        elif cluster_algo == 'kmeans':
            return self.kmeans(df, options)
        error = "Algorithm not implemented: '{}'".format(cluster_algo)
        logger.error(error)
        raise ValueError(error)

    def hclust(self, df: pd.DataFrame, options: dict) -> dict:
        try:
            method = options['method']
            metric = options['metric']
            n_row_clusters = options['n_row_clusters']
            n_col_clusters = options['n_col_clusters']
        except KeyError:
            error = "'method', 'metric', 'n_row_clusters', " \
                    "and 'n_col_clusters' are mandatory parameters to " \
                    "perform a hierarchical clustering."
            logger.error(error)
            raise ValueError(error)
        row_names, row_clusters = self._hclust(df.T, method,
                                               metric, n_row_clusters)
        col_names, col_clusters = self._hclust(df, method,
                                               metric, n_col_clusters)
        return {
            'row_names': row_names,
            'col_names': col_names,
            'row_cluster': row_clusters,
            'col_cluster': col_clusters
        }

    def _hclust(self, df: pd.DataFrame,
                method: str, metric: str, n_clusters: int) -> Tuple[List, List]:
        names = list(df)
        series = np.array(df)
        z = hclust.linkage(series, method=method, metric=metric)
        cluster = [x[0] for x in hclust.cut_tree(z,
                                                 n_clusters=[n_clusters])]
        cluster_count = Counter(cluster)
        # sort elements by their cluster size
        sorted_cluster = sorted(zip(names, cluster),
                                key=lambda x: cluster_count[x[1]], reverse=True)
        names = [x[0] for x in sorted_cluster]
        cluster = [x[1] for x in sorted_cluster]
        # relabel cluster, with the biggest cluster being 0
        c = 0
        relabeled_cluster = []
        for i, v in enumerate(cluster):
            if i > 0 and cluster[i] != cluster[i-1]:
                c += 1
            relabeled_cluster.append(c)
        cluster = relabeled_cluster
        return names, cluster

    def kmeans(self, df: pd.DataFrame, options: dict) -> dict:
        try:
            n_row_centroids = options['n_row_centroids']
            n_col_centroids = options['n_col_centroids']
        except KeyError:
            error = "'n_row_centroids' and 'n_col_centroids' are mandatory " \
                    "parameters to perform a kmeans clustering."
            logger.error(error)
            raise ValueError(error)

        row_names, row_clusters = self._kmeans(df.T, n_row_centroids)
        col_names, col_clusters = self._kmeans(df, n_col_centroids)
        return {
            'row_names': row_names,
            'col_names': col_names,
            'row_cluster': row_clusters,
            'col_cluster': col_clusters
        }

    def _kmeans(self, df: pd.DataFrame, n_centroids) -> Tuple[List, List]:
        names = list(df)
        series = np.array(df).astype('float')
        cluster = list(kmeans2(series, k=n_centroids, minit='points')[1])
        cluster_count = Counter(cluster)
        # sort elements by their cluster size
        sorted_cluster = sorted(zip(names, cluster),
                                key=lambda x: cluster_count[x[1]], reverse=True)
        names = [x[0] for x in sorted_cluster]
        cluster = [x[1] for x in sorted_cluster]
        # relabel cluster, with the biggest cluster being 0
        c = 0
        relabeled_cluster = []
        for i, v in enumerate(cluster):
            if i > 0 and cluster[i] != cluster[i-1]:
                c += 1
            relabeled_cluster.append(c)
        cluster = relabeled_cluster
        return names, cluster

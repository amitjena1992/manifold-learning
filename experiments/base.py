import abc
import time

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from scipy.spatial.distance import pdist, squareform
from sklearn import neighbors, decomposition, svm, manifold
from sklearn.cross_validation import train_test_split
from sklearn.grid_search import GridSearchCV
from sklearn.metrics import confusion_matrix

from manifold.infrastructure import Displayer
from manifold.infrastructure import base
from manifold.learning import algorithms


class Experiment(metaclass=abc.ABCMeta):
    title = None
    plotting = False
    data = target = labels = feature_names = None
    _displayer = None

    @property
    def displayer(self):
        self._displayer = self._displayer or Displayer(plotting=self.plotting)
        return self._displayer

    def _load_data(self):
        raise NotImplementedError

    def load_data(self):
        self._load_data()

        self.displayer \
            .load(self.data, self.target, axis_labels=self.feature_names) \
            .save('datasets/%s' % self.title) \
            .dispose()

        print('Data set size: %.2f KB' % (self.data.nbytes / 1024))
        print('Shape: %s' % str(self.data.shape))
        print('Correlation matrix:')
        print(np.corrcoef(self.data, rowvar=0))

    def _run(self):
        raise NotImplementedError

    def _dispose(self):
        pass

    def start(self):
        print('%s\n' % self.title)

        self._run()
        self._dispose()


class LearningExperiment(Experiment, metaclass=abc.ABCMeta):
    learner = svm.SVC
    grid = None
    verbose = False

    learning_parameters = [
        {'C': (1, 10, 100, 1000), 'kernel': ('linear',)},
        {'C': (1, 10, 100, 1000), 'gamma': (.001, .01, .1, 1, 10),
         'kernel': ('rbf', 'sigmoid')}
    ]

    test_after_train = False
    test_size = .2

    def learn(self):
        print('Learning...')
        start = time.time()

        X1, X2, y1, y2 = train_test_split(self.data,
                                          self.target,
                                          test_size=self.test_size) \
            if self.test_after_train \
            else (self.data, None, self.target, None)

        self.grid = GridSearchCV(self.learner(),
                                 self.learning_parameters,
                                 n_jobs=-1,
                                 verbose=self.verbose)
        self.grid.fit(X1, y1)

        print('\tGrid accuracy: %.2f' % self.grid.best_score_)
        print('\tBest parameters: %s' % self.grid.best_params_)
        print('Done. (%.2f s)\n' % (time.time() - start))

        if self.test_after_train:
            y2_predicted = self.grid.predict(X2)
            cm = confusion_matrix(y2, y2_predicted)
            np.set_printoptions(precision=2)

            plt.figure()
            plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
            plt.colorbar()
            plt.tight_layout()
            plt.ylabel('True label')
            plt.xlabel('Predicted label')

            plt.show()


class ReductionExperiment(Experiment, metaclass=abc.ABCMeta):
    original_data = None
    reducer = None
    reduction_method = 'isomap'
    reduction_params = {'k': 4, 'n_components': 3}

    knn = neighbors.KNeighborsClassifier(n_neighbors=1, n_jobs=-1)
    test_size = .2

    def n_neighbors_(self):
        p = self.reduction_params

        if 'n_neighbors' in p:
            return p['n_neighbors']
        if 'k' in p:
            return p['k']

        return 5

    def n_dimensions_(self):
        p = self.reduction_params

        if 'd' in p:
            return p['d']
        if 'n_components' in p:
            return p['n_components']

        return 3

    def load_data(self):
        super().load_data()

        self.original_data = self.data

    def reduce(self, evaluate=False, verbose=True):
        assert self.reduction_method in ('pca', 'mds', 'isomap', 'skisomap'), \
            'Error: unknown reduction method.'

        print('Reducing...')

        to_dimension = self.n_dimensions_()
        data = self.original_data

        print('\tMethod: %s' % self.reduction_method)
        print('\tR^%i --> R^%i' % (data.shape[1], to_dimension))

        start = time.time()

        if self.reduction_method == 'pca':
            self.reducer = decomposition.PCA(**self.reduction_params)
            self.data = self.reducer.fit_transform(data)

        elif self.reduction_method == 'mds':
            self.reducer = algorithms.MDS(verbose=verbose,
                                          **self.reduction_params)
            self.data = self.reducer.transform(data)

        elif self.reduction_method == 'isomap':
            self.reducer = algorithms.Isomap(verbose=verbose,
                                             **self.reduction_params)
            self.data = self.reducer.transform(data)

        elif self.reduction_method == 'skisomap':
            self.reducer = manifold.Isomap(**self.reduction_params)
            self.data = self.reducer.fit_transform(data)

        end = time.time()

        if evaluate:
            self.evaluate()

        self.displayer.load(self.data, self.target)

        print('Done. (%.2f s)\n' % (end - start))

    def plot_nearest_neighbors_graph(self, position='reduced'):
        """Draw Nearest Neighbor Graph.

        Parameters
        ----------
        position
            The position of the samples in the data set.
            Must be 'original' or 'reduced'.
        """
        assert position in (
            'original', 'reduced'), 'Unknown position %s.' % position
        assert self.data is not None or position != 'reduced', \
            'Position cannot be "reduced", as reduction has not ' \
            'been performed yet.'

        print('Plotting Nearest Neighbors...')
        print('\tposition: %s' % position)

        d = algorithms.EuclideanDistancesFromDataSet(self.original_data).run()
        e = algorithms.KNearestNeighbors(d, alpha=10).run()
        g = nx.Graph(e)
        del d, e

        pos = {}

        for n, location in enumerate(
                self.original_data if position == 'original' else self.data):
            location = location[:2]

            if location.shape[0] == 1:
                location = np.array([location[0], 0])

            pos[n] = location

        nx.draw(g, pos=pos, node_size=40, node_color=self.target, alpha=.6,
                width=1, edge_color='#cccccc', with_labels=False)

        print('Done.\n')
        plt.show()

    def evaluate(self):
        if self.reduction_method in ('pca', 'mds'):
            s = base.kruskal_stress(squareform(pdist(self.original_data)),
                               squareform(pdist(self.data)))
        else:
            s = base.partial_kruskal_stress(
                    self.original_data, self.data, self.n_neighbors_())
        print('\tStress: %.2f' % s)

        X1, X2, y1, y2 = train_test_split(self.data,
                                          self.target,
                                          test_size=self.test_size,
                                          random_state=0)

        print('\t1-NN score: %.2f' % self.knn.fit(X1, y1).score(X2, y2))
        print('\tSize: %.2f KB' % (self.data.nbytes / 1024))


class CompleteExperiment(LearningExperiment, ReductionExperiment,
                         metaclass=abc.ABCMeta):
    displaying_cycle_components = (3, 2, 1)
    learning_cycle_components = (3, 2, 1)

    def _run(self):
        self.load_data()
        self.evaluate()
        self.learn()

        for d in self.displaying_cycle_components:
            self.reduction_params['n_components'] = d
            self.reduce()

        self.displayer.save(self.title)

        for d in self.learning_cycle_components:
            self.reduction_params['n_components'] = d
            self.reduce(evaluate=True)
            self.learn()

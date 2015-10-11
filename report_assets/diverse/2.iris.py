from sklearn import datasets

from report_assets.base import ReductionExample, LearningExample


class IrisExample(ReductionExample, LearningExample):
    title = '2. Iris flower example'

    def _run(self):
        iris = datasets.load_iris()

        self.data, self.target = iris.data, iris.target
        print('Data set size: %i' % self.data.nbytes)

        self.learn()

        self.method = 'pca'
        self.params = {'n_components': 2}
        self.reduce()

        self.data = self.reduced_data
        self.learn()

        self.data = iris.data
        self.method = 'pca'
        self.params = {'n_components': 1}
        self.reduce()

        self.data = self.reduced_data
        self.learn()

        self.displayer.render()


if __name__ == '__main__':
    IrisExample().start()

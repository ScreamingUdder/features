import numpy as np


class NXDataWrapper:
    def __init__(self, NXdata):
        self.name = NXdata.name

        # get all the names of the datasets
        datasets = list(NXdata.keys())

        # get the name of the signal from the metadata
        signal = str(NXdata.attrs['signal'][0],"utf-8")
        self.signal = signal

        # remove this from the list so we don't add it to the secondary axes
        datasets.remove(signal)

        # get the h5py data object for the signal
        self.data = NXdata[signal]

        # build indices dict
        self.indecies = {}
        for dataset in datasets:
            self.indecies[dataset] = NXdata.attrs[dataset + "_indices"]

        # now build a list of the primary axes
        self.primary_axes = []
        self.primary_axes_names = []
        for axis in NXdata.attrs['axes']:
            axis = str(axis,"utf-8")
            # if the axis is a . then put a none in the list or the real dataset
            if axis in ['.']:
                self.primary_axes.append(None)
            else:
                self.primary_axes.append(NXdata[axis])
                # remove this so we don't add it to the secondary axes
                datasets.remove(axis)
            self.primary_axes_names.append(axis)

        self.secondary_axes = {}
        for dataset in datasets:
            self.secondary_axes[dataset] = NXdata[dataset]

    def get_shape(self):
        return self.data.shape

    def get_axis_slice(self, name, slicelist, dataset):
        slices = [slice(x, x + 1) if type(x) is not slice else x for x in slicelist]
        indecies = self.indecies[name]
        reduced_slice = np.array(slices)[indecies]
        reduced_slice = tuple(reduced_slice)
        result = dataset[reduced_slice]
        new_shape = np.ones_like(self.data.shape)
        new_shape[indecies] = result.shape
        result = result.reshape(new_shape)
        return result

    def __getitem__(self, val):
        if len(val) > len(self.data.shape):
            raise IndexError("too many dimensions given for slicing")
        result = {}
        result['data'] = self.data[val]
        result['primary_axes'] = []
        for i in range(len(self.primary_axes_names)):
            result['primary_axes'].append(self.get_axis_slice(self.primary_axes_names[i], val, self.primary_axes[i]))
        result['secondary_axes'] = {}
        for axis_name in self.secondary_axes.keys():
            result['secondary_axes'][axis_name] = self.get_axis_slice(axis_name, val, self.secondary_axes[axis_name])
        return result

    def __repr__(self):
        return "{} ({}):: {} ({})".format(self.name, self.signal, str(self.get_shape()), ','.join(self.primary_axes_names))


class recipe:
    """
    Recipe to describe if a file uses the cansas Axis format
    """

    def __init__(self, filedesc, entrypath):
        self.file = filedesc
        self.entry = entrypath
        self.title = "NXData with Cansas NeXus Axis"
        self.failure_comments = []

    def visitor(self, name, obj):
        if "NX_class" not in obj.attrs.keys():
            return
        if str(obj.attrs["NX_class"][0],"utf-8") not in ["NXdata"]:
            return
        datasets = list(obj.keys())
        attributes = obj.attrs.keys()
        if "signal" not in attributes:
            self.failure_comments.append("{} : Signal attribute should be present in NXdata".format(obj.name))
            return
        signal = str(obj.attrs['signal'][0],"utf-8")
        if signal not in datasets:
            self.failure_comments.append(
                "{} : Signal attribute points to a non-existent dataset ({})".format(obj.name, signal))
            return
        if "axes" not in attributes:
            self.failure_comments.append("{} : No 'axes' attribute is present".format(obj.name))
            return
        for axis in obj.attrs['axes']:
            if str(axis,"utf-8") not in datasets + ['.']:
                self.failure_comments.append(
                    "{} : Axis attribute points to a non-existent dataset ({})".format(obj.name, axis))
                return
        datasets.remove(signal)
        for dataset in datasets:
            if dataset + "_indices" not in attributes:
                self.failure_comments.append(
                    "{} : Axis dataset has no corresponding _indices attribute ({})".format(obj.name, dataset))
                return

        self.NXdatas.append(NXDataWrapper(obj))

    def process(self):
        self.NXdatas = []
        self.file[self.entry].visititems(self.visitor)

        if len(self.NXdatas) == 0:
            raise AssertionError('No NXdata with cansas Axis found' + '\n'.join(self.failure_comments))
        return self.NXdatas

from keras.engine.training import _make_batches, _standardize_input_data, _standardize_sample_weights
import numpy as np
import threading


class threadsafe_iter:
    """Takes an iterator/generator and makes it thread-safe by
    serializing call to the `next` method of given iterator/generator.
    """
    def __init__(self, it):
        self.it = it
        self.lock = threading.Lock()

    def __iter__(self):
        return self

    def next(self):
        with self.lock:
            return self.it.next()


def threadsafe_generator(f):
    """A decorator that takes a generator function and makes it thread-safe.
    """
    def g(*a, **kw):
        return threadsafe_iter(f(*a, **kw))
    return g


def _make_batches_overlap(size, batch_size, overlap, filt_length):
    '''Returns a list of batch indices (tuples of indices).
    '''
    nb_batch = int(np.ceil((size - batch_size)/ float(batch_size - overlap))) + 1
    return [(i * (batch_size - overlap), min(size, (i + 1) * batch_size - i*overlap))
            for i in range(0, nb_batch)]


@threadsafe_generator
def time_delay_generator(x, y, delays, batch_size, weights=None, shuffle=True):
    '''A generator to make it easy to fit time-delay regression models,
    i.e. a model where the value of y depends on past values of x

    # Arguments
    x: input data, as a Numpy array
    y: targets, as a Numpy array or None for prediction generation
    delays: number of time-steps to include in model
    weights: Numpy array of weights for the samples
    shuffle: Whether or not to shuffle the data (set True for training)

    # Example
    if X_train is (1000,200), Y_train is (1000,1)
    train_gen = time_delay_generator(X_train, Y_train, delays=10, batch_size=100)

    train_gen is a generator that gives:
    x_batch as size (100,10,200) since each of the 100 samples includes the input
    data at the current and nine previous time steps
    y_batch as size (100,1)
    w_batch as size (100,)

    '''

    if type(delays) is int:
        delays = range(delays)

    if type(x) is not list:
        x = list([x])
    index_array = np.arange(x[0].shape[0])

    tlists = [[1, 0] + list(range(2, np.ndim(xx) + 1)) for xx in x]
    batches = _make_batches(x[0].shape[0], batch_size)
    while 1:
        if shuffle:
            np.random.shuffle(index_array)
        for batch_index, (batch_start, batch_end) in enumerate(batches):
            batch_ids = index_array[batch_start:batch_end]
            batch_ids_delay = [np.minimum(np.maximum(0, batch_ids - d), x[0].shape[0]-1) for d in delays]
            x_batch = _standardize_input_data([xx[batch_ids_delay, :].transpose(tt) for xx,tt in zip(x, tlists)], ['x_batch' + str(i) for i in range(1, len(x)+1)])
            if y is None:
                yield x_batch
            else:
                y_batch = _standardize_input_data(y[batch_ids, :], ['y_batch'])
                if weights is not None:
                    w_batch = weights[batch_ids, :][:, 0]
                else:
                    w_batch = np.ones(x_batch[0].shape[0])
                w_batch[batch_ids < delays[-1]] = 0.
                w_batch = _standardize_sample_weights(w_batch, ['w_batch'])
                yield (x_batch, y_batch, w_batch)


def time_delay_generator_AE(x, delays, batch_size, shuffle=True, conv3d=False):
    '''A generator to make it easy to fit time-delay regression models,
    i.e. a model where the value of y depends on past values of x

    # Arguments
    x: input data, as a Numpy array
    y: targets, as a Numpy array or None for prediction generation
    delays: number of time-steps to include in model
    weights: Numpy array of weights for the samples
    shuffle: Whether or not to shuffle the data (set True for training)

    # Example
    if X_train is (1000,200), Y_train is (1000,1)
    train_gen = time_delay_generator(X_train, Y_train, delays=10, batch_size=100)

    train_gen is a generator that gives:
    x_batch as size (100,10,200) since each of the 100 samples includes the input
    data at the current and nine previous time steps
    y_batch as size (100,1)
    w_batch as size (100,)

    '''
    index_array = np.arange(x.shape[0])
    if conv3d:
        tlist = [1, 2, 0] + range(3, np.ndim(x) + 1)
    else:
        tlist = [1, 0] + range(2, np.ndim(x) + 1)
    batches = _make_batches(x.shape[0], batch_size)
    while 1:
        if shuffle:
            np.random.shuffle(index_array)
        for batch_index, (batch_start, batch_end) in enumerate(batches):
            batch_ids = index_array[batch_start:batch_end]
            batch_ids = [np.maximum(0, batch_ids - d) for d in range(delays)]
            x_batch = _standardize_input_data(x[batch_ids, :].transpose(tlist), ['x_batch'])
            y_batch = _standardize_input_data(np.copy(x_batch[0]).reshape((x_batch[0].shape[0], -1)), ['y_batch'])
            yield (x_batch, y_batch)


def time_delay_generator_conv(x, filt_length, frames_per_TR, TRs_in_model, y=None, weights=None):
    '''A generator to make it easy to fit time-delay regression models,
    i.e. a model where the value of y depends on past values of x

    # Arguments
    x: input data, as a Numpy array
    y: targets, as a Numpy array or None for prediction generation
    delays: number of time-steps to include in model
    weights: Numpy array of weights for the samples
    shuffle: Whether or not to shuffle the data (set True for training)

    # Example
    if X_train is (1000,200), Y_train is (1000,1)
    train_gen = time_delay_generator(X_train, Y_train, delays=10, batch_size=100)

    train_gen is a generator that gives:
    x_batch as size (100,10,200) since each of the 100 samples includes the input
    data at the current and nine previous time steps
    y_batch as size (100,1)
    w_batch as size (100,)

    '''
    batch_size = frames_per_TR*TRs_in_model + filt_length - 1
    x_size_expand = int(np.ceil((x.shape[0] - batch_size)/float(frames_per_TR))*frames_per_TR + batch_size)
    batches = _make_batches_overlap(x_size_expand, batch_size, frames_per_TR*(TRs_in_model-1)+filt_length-1, filt_length)
    print(batches)
    index_array = np.minimum(x.shape[0]-1, np.arange(0, x_size_expand))
    while 1:
        for batch_index, (batch_start, batch_end) in enumerate(batches):
            batch_ids = index_array[batch_start:batch_end]
            x_batch = _standardize_input_data(x[batch_ids, :][None, :], ['x_batch'])
            yield x_batch

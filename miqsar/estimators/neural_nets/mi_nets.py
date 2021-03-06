from torch import nn
from torch.nn import Sequential, Linear, ReLU, Softmax, Sigmoid
from .base_nets import BaseNet, BaseRegressor, BaseClassifier


class MainNet:
    def __new__(cls, ndim):
        inp_dim = ndim[0]
        net = []
        for dim in ndim[1:]:
            net.append(Linear(inp_dim, dim))
            net.append(ReLU())
            inp_dim = dim
        net = Sequential(*net)
        return net


class Pooling(nn.Module):
    def __init__(self, pool='mean'):
        super().__init__()
        self.pool = pool

    def forward(self, x, m):
        x = m * x
        if self.pool == 'mean':
            out = x.sum(axis=1) / m.sum(axis=1)
        elif self.pool == 'max':
            out = x.max(dim=1)[0]
        elif self.pool == 'lse':
            out = x.exp().sum(dim=1).log()
        return out

    def extra_repr(self):
        return 'Pooling(out_dim=1)'


class MINet(BaseNet):
    def __init__(self, ndim=None, pool='mean', init_cuda=False):
        super().__init__(init_cuda=init_cuda)
        self.main_net = MainNet(ndim)
        self.pooling = Pooling(pool)
        self.estimator = Linear(ndim[-1], 1)

        if self.init_cuda:
            self.main_net.cuda()
            self.estimator.cuda()

    def reset_params(self, m):
        if isinstance(m, nn.Linear):
            m.reset_parameters()

    def reset_weights(self):
        self.main_net.apply(self.reset_params)
        self.estimator.apply(self.reset_params)

    def forward(self, x, m):
        out = self.main_net(x)
        out = self.pooling(out, m)
        out = self.estimator(out)
        if isinstance(self, BaseClassifier):
            out = Sigmoid()(out)
        return None, out


class miNet(BaseNet):

    def __init__(self, ndim=None, pool='mean', init_cuda=False):
        super().__init__(init_cuda=init_cuda)
        self.main_net = Sequential(MainNet(ndim), Linear(ndim[-1], 1))
        self.pooling = Pooling(pool)

        if self.init_cuda:
            self.main_net.cuda()

    def forward(self, x, m):
        out = self.main_net(x)
        if isinstance(self, BaseClassifier):
            out = Sigmoid()(out)
        w = Softmax(dim=1)(m * out)
        w = w.view(w.shape[0], w.shape[-1], w.shape[1])
        out = self.pooling(out, m)
        return w, out


class MINetClassifier(MINet, BaseClassifier):

    def __init__(self, ndim=None, pool='mean', init_cuda=False):
        super().__init__(ndim=ndim, pool=pool, init_cuda=init_cuda)


class MINetRegressor(MINet, BaseRegressor):
    def __init__(self, ndim=None, pool='mean', init_cuda=False):
        super().__init__(ndim=ndim, pool=pool, init_cuda=init_cuda)


class miNetClassifier(miNet, BaseClassifier):
    def __init__(self, ndim=None, pool='mean', init_cuda=False):
        super().__init__(ndim=ndim, pool=pool, init_cuda=init_cuda)


class miNetRegressor(miNet, BaseRegressor):
    def __init__(self, ndim=None, pool='mean', init_cuda=False):
        super().__init__(ndim=ndim, pool=pool, init_cuda=init_cuda)

        self.pool = pool

    def name(self):
        return '{}{}'.format(self.__class__.__name__, self.pool.capitalize())
